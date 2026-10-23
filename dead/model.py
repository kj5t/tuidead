"""
Data models for Dead Archives
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Show:
    """A show with date, venue, and city"""
    date: str  # YYYY-MM-DD
    venue: str
    city: str
    
    def __str__(self):
        return f"{self.date} - {self.venue}, {self.city}"


@dataclass
class Recording:
    """A recording belonging to a show"""
    identifier: str
    source_type: str  # sbd, aud, mtx
    rating: float
    review_count: int
    best_format: str  # mp3, ogg, flac
    tracks: List['Track'] = None
    
    def __post_init__(self):
        if self.tracks is None:
            self.tracks = []


@dataclass
class Track:
    """A track in a recording"""
    title: str
    filename: str
    length: int  # seconds
    set: str
    position: int
    
    def __str__(self):
        return f"{self.position}. {self.title}"