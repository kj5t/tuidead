"""
Archive client for Dead Archives
"""
import asyncio
import httpx
import json
import os
from typing import List, Dict, Optional
from dead.model import Show, Recording, Track
from pathlib import Path


class ArchiveClient:
    """Client for interacting with archive.org API"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "tuidead"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            headers={"User-Agent": "tuidead/0.1"},
            timeout=30.0
        )
    
    async def search(self, query: str) -> List[Show]:
        """Search for shows using advanced search"""
        # This would make an API call to archive.org
        # For now, we'll return mock data
        # Just return mock data without caching for now to simplify testing
        shows = [
            Show("1977-05-08", "Hicks Stadium", "San Francisco"),
            Show("1977-05-09", "Hicks Stadium", "San Francisco"),
            Show("1978-05-08", "Hicks Stadium", "San Francisco"),
        ]
        return shows
    
    def _parse_search_results(self, data: List[Dict]) -> List[Show]:
        """Parse search results from cache"""
        shows = []
        for item in data:
            shows.append(Show(
                date=item['date'],
                venue=item['venue'],
                city=item['city']
            ))
        return shows
    
    async def recording_tracks(self, identifier: str) -> Recording:
        """Get recording metadata and tracks"""
        # For now, return mock data without caching
        recording = Recording(
            identifier=identifier,
            source_type="sbd",
            rating=4.78,
            review_count=300,
            best_format="mp3",
            tracks=[
                Track("Jack Straw", "01_jack_straw.mp3", 245, "Set 1", 1),
                Track("Box of Rain", "02_box_of_rain.mp3", 210, "Set 1", 2),
                Track("Scarlet Begonias > Fire on the Mountain", "03_scarlet_begonias.mp3", 320, "Set 1", 3),
            ]
        )
        return recording
    
    def _parse_recording_data(self, data: Dict) -> Recording:
        """Parse recording data from cache"""
        return Recording(
            identifier=data['identifier'],
            source_type=data['source_type'],
            rating=data['rating'],
            review_count=data['review_count'],
            best_format=data['best_format'],
            tracks=[Track(**track) for track in data['tracks']]
        )
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()