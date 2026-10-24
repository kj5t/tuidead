"""
Player component using mpv
"""
import asyncio
import itertools
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


class PlayerError(Exception):
    """mpv is missing, failed to start, or rejected a command"""


class MPVPlayer:
    """Controls mpv playback via JSON IPC over a Unix socket"""

    def __init__(self, ipc_socket: str = None, audio_device: str = None):
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self.ipc_socket = ipc_socket or str(Path(runtime_dir) / f"tuidead-mpv-{os.getpid()}.sock")
        self.process: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._read_task: Optional[asyncio.Task] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._request_ids = itertools.count(1)
        self._start_lock: Optional[asyncio.Lock] = None
        # Preferred output: an mpv device name (pipewire/bluez_output...) or its description (Office)
        self.audio_device = audio_device or os.environ.get("TUIDEAD_AUDIO_DEVICE") or None
        self.active_device: Optional[str] = None
        self._setup_ipc_socket()

    def _setup_ipc_socket(self):
        """Create the socket directory for IPC"""
        Path(self.ipc_socket).parent.mkdir(parents=True, exist_ok=True)

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.returncode is None and self._writer is not None

    async def start(self):
        """Start mpv with IPC enabled and connect to its socket"""
        if self._start_lock is None:
            self._start_lock = asyncio.Lock()
        async with self._start_lock:
            if self.running:
                return
            if shutil.which("mpv") is None:
                raise PlayerError("mpv not found on PATH")
            if self.process and self.process.returncode is None:
                self.process.kill()
            Path(self.ipc_socket).unlink(missing_ok=True)

            cmd = [
                "mpv",
                "--idle=yes",
                "--no-video",
                "--no-terminal",
                "--gapless-audio=yes",
                "--prefetch-playlist=yes",
                "--audio-client-name=tuidead",
                f"--input-ipc-server={self.ipc_socket}",
            ]
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # mpv creates the socket shortly after starting
            for _ in range(50):
                if self.process.returncode is not None:
                    raise PlayerError(f"mpv exited with code {self.process.returncode}")
                try:
                    self._reader, self._writer = await asyncio.open_unix_connection(self.ipc_socket)
                    break
                except (FileNotFoundError, ConnectionRefusedError):
                    await asyncio.sleep(0.1)
            else:
                raise PlayerError("timed out waiting for mpv IPC socket")
            self._read_task = asyncio.create_task(self._read_loop())

    async def stop(self):
        """Stop mpv"""
        if self.running:
            try:
                await asyncio.wait_for(self._send_command({"command": ["quit"]}, check=False), 1)
            except (asyncio.TimeoutError, PlayerError, ConnectionError):
                pass
            if self.process:
                try:
                    await asyncio.wait_for(self.process.wait(), 2)
                except asyncio.TimeoutError:
                    pass
        if self._read_task:
            self._read_task.cancel()
        if self._writer:
            self._writer.close()
        self._reader = self._writer = self._read_task = None
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except asyncio.TimeoutError:
                self.process.kill()
        Path(self.ipc_socket).unlink(missing_ok=True)

    async def list_audio_devices(self) -> List[Dict[str, str]]:
        """mpv's audio outputs, as [{'name': ..., 'description': ...}]"""
        return await self.get_property("audio-device-list") or []

    def _match_device(self, devices: List[Dict[str, str]]) -> Optional[str]:
        wanted = self.audio_device.strip()
        for d in devices:
            if d["name"] == wanted:
                return d["name"]
        for d in devices:
            if d["name"].split("/", 1)[-1] == wanted or d.get("description", "").lower() == wanted.lower():
                return d["name"]
        return None

    async def apply_audio_device(self) -> bool:
        """Point mpv at the preferred output if it is present, else the system default.

        Returns False when a preferred device is configured but not available
        (e.g. a Bluetooth speaker that isn't connected).
        """
        if not self.audio_device:
            return True
        device = self._match_device(await self.list_audio_devices())
        target = device or "auto"
        if target != self.active_device:
            await self.set_property("audio-device", target)
            self.active_device = target
        return device is not None

    async def load_playlist(self, files: List[str], start: int = 0) -> bool:
        """Replace the playlist with files and start playing at index start.

        Returns False if the preferred audio device was missing and the default was used.
        """
        if not files:
            return True
        # Re-check each time so a speaker connected mid-session gets picked up
        device_ok = await self.apply_audio_device()
        await self._send_command({"command": ["playlist-clear"]})
        for i, url in enumerate(files):
            await self._send_command({"command": ["loadfile", url, "replace" if i == 0 else "append"]})
        if start:
            await self.jump(start)
        await self.play()
        return device_ok

    async def play(self):
        """Start playback"""
        await self.set_property("pause", False)

    async def pause(self):
        """Pause playback"""
        await self.set_property("pause", True)

    async def toggle_pause(self):
        """Toggle between playing and paused"""
        await self._send_command({"command": ["cycle", "pause"]})

    async def next(self):
        """Skip to next track"""
        await self._send_command({"command": ["playlist-next"]}, check=False)

    async def previous(self):
        """Go to previous track"""
        await self._send_command({"command": ["playlist-prev"]}, check=False)

    async def jump(self, index: int):
        """Play the playlist entry at index"""
        await self.set_property("playlist-pos", index)

    async def seek(self, position: float, mode: str = "absolute"):
        """Seek to position (seconds); mode is 'absolute' or 'relative'"""
        await self._send_command({"command": ["seek", position, mode]}, check=False)

    async def set_volume(self, volume: int):
        """Set volume (0-100)"""
        await self.set_property("volume", volume)

    async def set_property(self, name: str, value: Any):
        await self._send_command({"command": ["set_property", name, value]})

    async def get_property(self, name: str) -> Any:
        """Read an mpv property; None if it is currently unavailable"""
        result = await self._send_command({"command": ["get_property", name]}, check=False)
        if result and result.get("error") == "success":
            return result.get("data")
        return None

    async def get_state(self) -> Dict[str, Any]:
        """Get current playback state; empty if mpv isn't running"""
        if not self.running:
            return {}
        names = ["playlist-pos", "time-pos", "duration", "pause", "idle-active"]
        values = await asyncio.gather(*(self.get_property(n) for n in names))
        return dict(zip(names, values))

    async def _read_loop(self):
        """Dispatch replies from mpv to the commands waiting on them; ignore events"""
        try:
            while self._reader:
                line = await self._reader.readline()
                if not line:
                    break
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                future = self._pending.pop(message.get("request_id"), None)
                if future and not future.done():
                    future.set_result(message)
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(PlayerError("mpv connection closed"))
            self._pending.clear()
            self._writer = None

    async def _send_command(self, command: dict, check: bool = True) -> Optional[dict]:
        """Send command to mpv via IPC and wait for its reply"""
        if not self.running:
            await self.start()
        request_id = next(self._request_ids)
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            self._writer.write((json.dumps({**command, "request_id": request_id}) + "\n").encode())
            await self._writer.drain()
            result = await asyncio.wait_for(future, 5)
        finally:
            self._pending.pop(request_id, None)
        if check and result.get("error") != "success":
            raise PlayerError(f"{command['command'][0]}: {result.get('error')}")
        return result
