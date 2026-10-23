"""
Textual UI for Dead Archives
"""
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import (
    Header, Footer, 
    Static, Button, 
    Input, ProgressBar,
    ListView, ListItem
)
from textual import events
from dead.model import Show, Recording, Track
from dead.archive import ArchiveClient
from dead.store import Store
from dead.player import MPVPlayer
import asyncio


class DeadArchivesApp(App):
    """Main application for Dead Archives TUI"""
    
    CSS_PATH = "app.tcss"
    
    def __init__(self):
        super().__init__()
        self.archive_client = ArchiveClient()
        self.store = Store()
        self.player = MPVPlayer()
        
    def compose(self) -> ComposeResult:
        """Create the application layout"""
        yield Header()
        yield Container(
            Static("Dead Archives TUI", id="title"),
            Input(placeholder="Search shows...", id="search-input"),
            ListView(id="show-list"),
            id="main-container"
        )
        yield Container(
            Static("Now Playing:", id="now-playing-title"),
            Static("No track playing", id="current-track"),
            ProgressBar(id="progress-bar"),
            Button("Play/Pause", id="play-pause"),
            Button("Next", id="next"),
            Button("Previous", id="previous"),
            id="player-container"
        )
        yield Footer()
    
    async def on_mount(self) -> None:
        """Called when the app is mounted"""
        await self.load_shows()
    
    async def load_shows(self):
        """Load shows into the list"""
        shows = await self.archive_client.search("dead")
        list_view = self.query_one("#show-list")
        
        # Clear existing items
        list_view.clear()
        
        # Add shows to the list
        for show in shows:
            list_view.append(ListItem(Static(str(show)), id=f"show-{show.date}"))
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "play-pause":
            await self.toggle_playback()
        elif event.button.id == "next":
            await self.next_track()
        elif event.button.id == "previous":
            await self.previous_track()
    
    async def toggle_playback(self):
        """Toggle play/pause"""
        # In a real implementation, this would communicate with mpv
        pass
    
    async def next_track(self):
        """Skip to next track"""
        # In a real implementation, this would communicate with mpv
        pass
    
    async def previous_track(self):
        """Go to previous track"""
        # In a real implementation, this would communicate with mpv
        pass
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search input submission"""
        search_text = event.input.value
        if search_text:
            shows = await self.archive_client.search(search_text)
            list_view = self.query_one("#show-list")
            list_view.clear()
            
            for show in shows:
                list_view.append(ListItem(Static(str(show)), id=f"show-{show.date}"))