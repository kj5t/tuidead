"""
Player component using mpv
"""
import asyncio
import json
import subprocess
import os
from pathlib import Path
from typing import List, Optional


class MPVPlayer:
    """Controls mpv playback via JSON IPC"""
    
    def __init__(self, ipc_socket: str = None):
        self.ipc_socket = ipc_socket or f"/tmp/mpv-{os.getpid()}.sock"
        self.process = None
        self._setup_ipc_socket()
    
    def _setup_ipc_socket(self):
        """Create the socket path for IPC"""
        Path(self.ipc_socket).parent.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Start mpv with IPC enabled"""
        if self.process and self.process.poll() is None:
            return
            
        cmd = [
            "mpv",
            "--idle",
            f"--input-ipc-server={self.ipc_socket}",
            "--no-audio-display"
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    async def stop(self):
        """Stop mpv"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
    
    async def load_playlist(self, files: List[str]):
        """Load a playlist into mpv"""
        if not self.process or self.process.poll() is not None:
            await self.start()
        
        # Send command to load playlist
        cmd = {
            "command": ["loadlist", *files, "replace"]
        }
        await self._send_command(cmd)
    
    async def play(self):
        """Start playback"""
        cmd = {"command": ["play"]}
        await self._send_command(cmd)
    
    async def pause(self):
        """Pause playback"""
        cmd = {"command": ["pause"]}
        await self._send_command(cmd)
    
    async def next(self):
        """Skip to next track"""
        cmd = {"command": ["playlist-next"]}
        await self._send_command(cmd)
    
    async def previous(self):
        """Go to previous track"""
        cmd = {"command": ["playlist-prev"]}
        await self._send_command(cmd)
    
    async def seek(self, position: int):
        """Seek to position (seconds)"""
        cmd = {"command": ["seek", position, "absolute"]}
        await self._send_command(cmd)
    
    async def set_volume(self, volume: int):
        """Set volume (0-100)"""
        cmd = {"command": ["set_property", "volume", volume]}
        await self._send_command(cmd)
    
    async def get_state(self):
        """Get current playback state"""
        cmd = {"command": ["get_property", "playlist-pos"]}
        result = await self._send_command(cmd)
        return result
    
    async def _send_command(self, command: dict):
        """Send command to mpv via IPC"""
        if not self.process or self.process.poll() is not None:
            await self.start()
            
        try:
            # Write command to IPC socket
            with open(self.ipc_socket, 'w') as f:
                f.write(json.dumps(command) + '\n')
            
            # Read response
            response = ""
            with open(self.ipc_socket, 'r') as f:
                response = f.readline()
            
            if response:
                return json.loads(response)
        except Exception as e:
            print(f"Error sending command to mpv: {e}")
            return None