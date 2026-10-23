"""
SQLite storage for cache, favorites, and history
"""
import sqlite3
from pathlib import Path
from typing import List, Optional
from dead.model import Show, Recording, Track


class Store:
    """SQLite database for caching and state"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Path.home() / ".local" / "share" / "tuidead" / "store.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Shows table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shows (
                date TEXT PRIMARY KEY,
                venue TEXT,
                city TEXT
            )
        """)
        
        # Recordings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recordings (
                identifier TEXT PRIMARY KEY,
                show_date TEXT,
                source_type TEXT,
                rating REAL,
                review_count INTEGER,
                best_format TEXT,
                FOREIGN KEY (show_date) REFERENCES shows (date)
            )
        """)
        
        # Tracks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recording_identifier TEXT,
                title TEXT,
                filename TEXT,
                length INTEGER,
                track_set TEXT,
                position INTEGER,
                FOREIGN KEY (recording_identifier) REFERENCES recordings (identifier)
            )
        """)
        
        # Favorites table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                identifier TEXT PRIMARY KEY,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # History table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (identifier) REFERENCES recordings (identifier)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_show(self, show: Show):
        """Save a show to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO shows (date, venue, city)
            VALUES (?, ?, ?)
        """, (show.date, show.venue, show.city))
        conn.commit()
        conn.close()
    
    def save_recording(self, recording: Recording):
        """Save a recording to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO recordings (identifier, show_date, source_type, rating, review_count, best_format)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (recording.identifier, recording.identifier.split('.')[0], 
              recording.source_type, recording.rating, recording.review_count, recording.best_format))
        conn.commit()
        conn.close()
    
    def save_tracks(self, recording: Recording):
        """Save tracks for a recording"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete existing tracks for this recording
        cursor.execute("DELETE FROM tracks WHERE recording_identifier = ?", (recording.identifier,))
        
        # Insert new tracks
        for track in recording.tracks:
            cursor.execute("""
                INSERT INTO tracks (recording_identifier, title, filename, length, track_set, position)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (recording.identifier, track.title, track.filename, track.length, track.set, track.position))
        
        conn.commit()
        conn.close()
    
    def get_show(self, date: str) -> Optional[Show]:
        """Get a show by date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT date, venue, city FROM shows WHERE date = ?", (date,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Show(row[0], row[1], row[2])
        return None
    
    def get_recording(self, identifier: str) -> Optional[Recording]:
        """Get a recording by identifier"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT identifier, show_date, source_type, rating, review_count, best_format FROM recordings WHERE identifier = ?", (identifier,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Recording(row[0], row[1], row[2], row[3], row[4], row[5])
        return None
    
    def get_tracks(self, recording_identifier: str) -> List[Track]:
        """Get tracks for a recording"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, filename, length, track_set, position
            FROM tracks
            WHERE recording_identifier = ?
            ORDER BY position
        """, (recording_identifier,))
        rows = cursor.fetchall()
        conn.close()
        
        return [Track(row[0], row[1], row[2], row[3], row[4]) for row in rows]
    
    def add_favorite(self, identifier: str):
        """Add a recording to favorites"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO favorites (identifier)
            VALUES (?)
        """, (identifier,))
        conn.commit()
        conn.close()
    
    def remove_favorite(self, identifier: str):
        """Remove a recording from favorites"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorites WHERE identifier = ?", (identifier,))
        conn.commit()
        conn.close()
    
    def get_favorites(self) -> List[str]:
        """Get all favorite identifiers"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT identifier FROM favorites ORDER BY added_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    
    def add_to_history(self, identifier: str):
        """Add a recording to playback history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO history (identifier)
            VALUES (?)
        """, (identifier,))
        conn.commit()
        conn.close()
    
    def get_recent_history(self, limit: int = 10) -> List[str]:
        """Get recent playback history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT identifier FROM history 
            ORDER BY played_at DESC 
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]