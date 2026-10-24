"""
Textual UI for Dead Archives
"""
import argparse
import asyncio
from typing import List, Optional

import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input, ListView, ListItem, ProgressBar
from dead.model import Show, Recording, Track
from dead.archive import ArchiveClient
from dead.store import Store
from dead.player import MPVPlayer, PlayerError


def fmt_time(seconds) -> str:
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class ShowItem(ListItem):
    """A show row; carries its Show"""

    def __init__(self, show: Show):
        self.show = show
        count = len(show.recordings)
        label = f"{show.date}  {show.venue}, {show.city}  [dim]({count} src)[/dim]"
        super().__init__(Static(label))


class TrackItem(ListItem):
    """A track row; carries its Track and index into the recording"""

    def __init__(self, track: Track, index: int):
        self.track = track
        self.index = index
        self.label = Static(self._text(False))
        super().__init__(self.label)

    def _text(self, playing: bool) -> str:
        marker = "▶ " if playing else "  "
        length = fmt_time(self.track.length) if self.track.length else ""
        return f"{marker}{self.track.position:>2}. {self.track.title}  [dim]{length}[/dim]"

    def set_playing(self, playing: bool):
        self.label.update(self._text(playing))


class DeadArchivesApp(App):
    """Main application for Dead Archives TUI"""

    CSS_PATH = "app.tcss"
    TITLE = "Dead Archives"

    BINDINGS = [
        Binding("/", "focus_search", "Search"),
        Binding("space", "toggle_pause", "Play/Pause"),
        Binding("n", "next_track", "Next"),
        Binding("p", "previous_track", "Prev"),
        Binding("left", "seek(-10)", "-10s", show=False),
        Binding("right", "seek(10)", "+10s", show=False),
        Binding("s", "next_source", "Source"),
        Binding("f", "toggle_favorite", "Fav"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, audio_device: Optional[str] = None):
        super().__init__()
        self.archive_client = ArchiveClient()
        self.store = Store()
        self.player = MPVPlayer(audio_device=audio_device)
        # Show/recording displayed in the track pane
        self.current_show: Optional[Show] = None
        self.source_index = 0
        self.displayed: Optional[Recording] = None
        # Show/recording loaded into mpv
        self.playing_show: Optional[Show] = None
        self.playing: Optional[Recording] = None
        self.playing_pos: Optional[int] = None

    def compose(self) -> ComposeResult:
        """Create the application layout"""
        yield Header()
        yield Input(placeholder="Search: 1977, 1977-05, 77-05-08, Winterland, Fillmore…", id="search-input")
        yield Horizontal(
            Vertical(
                Static("Shows", id="shows-title", classes="pane-title"),
                ListView(id="show-list"),
                id="shows-pane",
            ),
            Vertical(
                Static("Select a show", id="recording-info", classes="pane-title"),
                ListView(id="track-list"),
                id="tracks-pane",
            ),
            id="main-container",
        )
        yield Container(
            Static("Nothing playing", id="current-track"),
            Horizontal(
                ProgressBar(id="progress-bar", show_eta=False, show_percentage=False),
                Static("", id="time"),
                id="progress-row",
            ),
            id="player-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Called when the app is mounted"""
        self.query_one("#show-list").focus()
        self.set_interval(1.0, self.refresh_status)
        self.load_shows(None)

    async def on_unmount(self) -> None:
        await self.player.stop()
        await self.archive_client.close()

    # --- searching -------------------------------------------------------

    @work(exclusive=True, group="search")
    async def load_shows(self, query: Optional[str]):
        """Load shows into the list; no query means 'this day in history'"""
        title = self.query_one("#shows-title", Static)
        title.update("Searching…")
        try:
            if query:
                shows = await self.archive_client.search(query)
                heading = f"{len(shows)} shows for “{query}”"
            else:
                shows = await self.archive_client.this_day()
                heading = f"This day in history — {len(shows)} shows"
        except httpx.HTTPError as e:
            title.update("Search failed")
            self.notify(f"archive.org search failed: {e}", severity="error")
            return

        title.update(heading)
        list_view = self.query_one("#show-list", ListView)
        await list_view.clear()
        await list_view.extend(ShowItem(show) for show in shows)
        if shows:
            list_view.index = 0
        else:
            self.notify("No shows found", severity="warning")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search input submission"""
        self.load_shows(event.value.strip() or None)
        self.query_one("#show-list").focus()

    def action_focus_search(self):
        self.query_one("#search-input", Input).focus()

    # --- selecting -------------------------------------------------------

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter on a show plays its best source; enter on a track plays from there"""
        item = event.item
        if isinstance(item, ShowItem):
            self.current_show = item.show
            self.source_index = 0
            self.load_recording(play_from=0)
        elif isinstance(item, TrackItem):
            await self.play_track(item.index)

    @work(exclusive=True, group="recording")
    async def load_recording(self, play_from: Optional[int] = None):
        """Fetch tracks for the current show's selected source; optionally start playing"""
        show = self.current_show
        if not show or not show.recordings:
            return
        stub = show.recordings[self.source_index]
        info = self.query_one("#recording-info", Static)
        info.update(f"Loading {stub.identifier}…")
        try:
            recording = await self.archive_client.recording_tracks(stub.identifier)
        except httpx.HTTPError as e:
            info.update("Failed to load recording")
            self.notify(f"archive.org metadata failed: {e}", severity="error")
            return
        # Search results carry archive.org's own rating; prefer it to the reviews sample
        recording.rating, recording.review_count = stub.rating, stub.review_count
        self.displayed = recording
        self.update_recording_info()

        track_list = self.query_one("#track-list", ListView)
        await track_list.clear()
        await track_list.extend(TrackItem(t, i) for i, t in enumerate(recording.tracks))
        if not recording.tracks:
            self.notify("No playable audio in this recording; press s for another source",
                        severity="warning")
            return
        track_list.index = 0
        self.highlight_playing()
        if play_from is not None:
            track_list.focus()
            await self.play_track(play_from)

    def update_recording_info(self):
        rec, show = self.displayed, self.current_show
        if not rec or not show:
            return
        fav = " ★" if rec.identifier in self.store.get_favorites() else ""
        rating = f"{rec.rating:.2f} ({rec.review_count})" if rec.review_count else "unrated"
        self.query_one("#recording-info", Static).update(
            f"[b]{rec.source_type.upper()}[/b] {rating}  "
            f"[dim]{self.source_index + 1}/{len(show.recordings)} {rec.identifier}[/dim]{fav}"
        )

    async def play_track(self, index: int):
        """Play the displayed recording from track index"""
        rec = self.displayed
        if not rec or not rec.tracks:
            return
        try:
            if self.playing is rec:
                await self.player.jump(index)
                await self.player.play()
            else:
                device_ok = await self.player.load_playlist([t.url for t in rec.tracks], start=index)
                if not device_ok:
                    self.notify(f"Audio device “{self.player.audio_device}” not found; "
                                "using the system default", severity="warning")
                self.playing, self.playing_show = rec, self.current_show
                self.store.add_to_history(rec.identifier)
        except (PlayerError, OSError) as e:
            self.notify(f"Playback failed: {e}", severity="error")
            return
        self.playing_pos = index
        self.highlight_playing()

    # --- transport -------------------------------------------------------

    async def _player(self, coro):
        if not self.playing:
            return
        try:
            await coro
        except (PlayerError, OSError) as e:
            self.notify(f"Player error: {e}", severity="error")
        await self.refresh_status()

    async def action_toggle_pause(self):
        await self._player(self.player.toggle_pause())

    async def action_next_track(self):
        await self._player(self.player.next())

    async def action_previous_track(self):
        await self._player(self.player.previous())

    async def action_seek(self, seconds: int):
        await self._player(self.player.seek(seconds, "relative"))

    def action_next_source(self):
        """Show the next-best recording of the current show"""
        if self.current_show and len(self.current_show.recordings) > 1:
            self.source_index = (self.source_index + 1) % len(self.current_show.recordings)
            self.load_recording()

    def action_toggle_favorite(self):
        if not self.displayed:
            return
        ident = self.displayed.identifier
        if ident in self.store.get_favorites():
            self.store.remove_favorite(ident)
            self.notify("Removed from favorites")
        else:
            self.store.add_favorite(ident)
            self.notify("Added to favorites")
        self.update_recording_info()

    # --- status ----------------------------------------------------------

    async def refresh_status(self) -> None:
        """Poll mpv and update the now-playing panel"""
        if not self.playing:
            return
        try:
            state = await self.player.get_state()
        except (PlayerError, OSError, TimeoutError):
            state = {}
        current = self.query_one("#current-track", Static)
        bar = self.query_one("#progress-bar", ProgressBar)
        pos = state.get("playlist-pos")
        if not state or pos is None or pos < 0 or state.get("idle-active"):
            current.update("Nothing playing")
            bar.update(total=None, progress=0)
            self.query_one("#time", Static).update("")
            if self.playing_pos is not None:
                self.playing_pos = None
                self.highlight_playing()
            return

        if pos != self.playing_pos:
            self.playing_pos = pos
            self.highlight_playing()
        track = self.playing.tracks[pos] if pos < len(self.playing.tracks) else None
        show = self.playing_show
        icon = "⏸" if state.get("pause") else "▶"
        title = track.title if track else "?"
        current.update(f"{icon}  [b]{title}[/b]  [dim]{show.date} {show.venue}, {show.city}[/dim]")
        elapsed, duration = state.get("time-pos") or 0, state.get("duration") or 0
        bar.update(total=duration or None, progress=elapsed)
        self.query_one("#time", Static).update(f"{fmt_time(elapsed)} / {fmt_time(duration)}")

    def highlight_playing(self):
        """Mark the playing track in the track list, if that recording is displayed"""
        same = self.playing is not None and self.playing is self.displayed
        for item in self.query_one("#track-list", ListView).query(TrackItem):
            item.set_playing(same and item.index == self.playing_pos)


async def print_audio_devices():
    player = MPVPlayer()
    try:
        devices = await player.list_audio_devices()
    finally:
        await player.stop()
    for d in devices:
        print(f"{d['name']}\t{d.get('description', '')}")


def main() -> None:
    """Console-script entry point"""
    parser = argparse.ArgumentParser(prog="tuidead", description="Terminal player for the Dead's archive.org recordings")
    parser.add_argument("--audio-device", metavar="DEVICE",
                        help="output device: an mpv device name or its description, e.g. Office "
                             "(default: $TUIDEAD_AUDIO_DEVICE, else the system default)")
    parser.add_argument("--list-audio-devices", action="store_true",
                        help="print available output devices and exit")
    args = parser.parse_args()
    if args.list_audio_devices:
        asyncio.run(print_audio_devices())
        return
    DeadArchivesApp(audio_device=args.audio_device).run()
