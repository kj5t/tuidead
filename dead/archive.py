"""
Archive client for Dead Archives
"""
import asyncio
import datetime
import httpx
import json
import os
import re
from dataclasses import asdict
from typing import List, Dict, Optional
from urllib.parse import quote
from dead.model import Show, Recording, Track
from pathlib import Path


SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{name}"
COLLECTION = "GratefulDead"
FIRST_YEAR, LAST_YEAR = 1965, 1995

# Streamable formats, most preferred first
FORMAT_PREFERENCE = [
    ("VBR MP3", "mp3"),
    ("Ogg Vorbis", "ogg"),
    ("Flac", "flac"),
    ("24bit Flac", "flac"),
    ("64Kbps MP3", "mp3"),
]
SOURCE_RANK = {"sbd": 0, "mtx": 1, "aud": 2, "?": 3}


def source_type(identifier: str, source: str = "") -> str:
    """Classify a recording as sbd, mtx or aud from its identifier, then its lineage"""
    for text in (identifier.lower(), source.lower()):
        if "mtx" in text or "matrix" in text:
            return "mtx"
        if "sbd" in text or "soundboard" in text:
            return "sbd"
        if "aud" in text or "audience" in text:
            return "aud"
    return "?"


def parse_length(value) -> int:
    """Parse '381.1' or '06:21' or '1:02:03' into whole seconds"""
    if not value:
        return 0
    try:
        if ":" in str(value):
            seconds = 0
            for part in str(value).split(":"):
                seconds = seconds * 60 + float(part)
            return int(seconds)
        return int(float(value))
    except ValueError:
        return 0


def build_query(text: str) -> str:
    """Turn user input into an archive.org advanced search query.

    Accepts a year (1977), month (1977-05), date (1977-05-08 or 77-05-08),
    or free text matched against venue, city and title.
    """
    text = text.strip()
    base = f"collection:{COLLECTION}"
    m = re.fullmatch(r"(\d{2}|\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?", text)
    if m:
        year = m.group(1)
        if len(year) == 2:
            year = "19" + year
        if m.group(3):
            day = f"{year}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            return f"{base} AND date:[{day} TO {day}]"
        if m.group(2):
            month = int(m.group(2))
            return f"{base} AND date:[{year}-{month:02d}-01 TO {year}-{month:02d}-31]"
        return f"{base} AND date:[{year}-01-01 TO {year}-12-31]"
    words = re.sub(r"[^\w\s'-]", " ", text).split()
    if not words:
        return base
    terms = " AND ".join(words)
    return f"{base} AND (venue:({terms}) OR coverage:({terms}) OR title:({terms}))"


def this_day_query(today: Optional[datetime.date] = None) -> str:
    """Query for every show played on today's month/day in any year"""
    today = today or datetime.date.today()
    md = f"{today.month:02d}-{today.day:02d}"
    days = " OR ".join(
        f"date:[{y}-{md} TO {y}-{md}]" for y in range(FIRST_YEAR, LAST_YEAR + 1)
    )
    return f"collection:{COLLECTION} AND ({days})"


def rank_recordings(recordings: List[Recording]) -> List[Recording]:
    """Sort recordings best first: Bayesian-weighted rating, then sbd > mtx > aud"""
    def score(rec: Recording):
        prior, weight = 3.5, 3
        bayes = (rec.rating * rec.review_count + prior * weight) / (rec.review_count + weight)
        return (-bayes, SOURCE_RANK.get(rec.source_type, 3), -rec.review_count)
    return sorted(recordings, key=score)


class ArchiveClient:
    """Client for interacting with archive.org API"""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "tuidead"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            headers={"User-Agent": "tuidead/0.1"},
            timeout=30.0,
            follow_redirects=True,
        )

    async def search(self, query: str) -> List[Show]:
        """Search for shows; one Show per date with its recordings ranked best first"""
        return await self._search_query(build_query(query))

    async def this_day(self) -> List[Show]:
        """Shows played on this day in history"""
        return await self._search_query(this_day_query())

    async def _search_query(self, q: str) -> List[Show]:
        params = [
            ("q", q),
            *[("fl[]", f) for f in ("identifier", "date", "venue", "coverage",
                                    "source", "avg_rating", "num_reviews")],
            ("sort[]", "date asc"),
            ("rows", "5000"),
            ("output", "json"),
        ]
        response = await self.client.get(SEARCH_URL, params=params)
        response.raise_for_status()
        docs = response.json()["response"]["docs"]
        return self._parse_search_results(docs)

    def _parse_search_results(self, data: List[Dict]) -> List[Show]:
        """Group search docs into shows by date"""
        shows: Dict[str, Show] = {}
        docs_by_id: Dict[str, Dict] = {}
        for item in data:
            date = str(item.get("date", ""))[:10]
            if not date:
                continue
            docs_by_id[item["identifier"]] = item
            source = item.get("source") or ""
            if isinstance(source, list):
                source = " ".join(source)
            recording = Recording(
                identifier=item["identifier"],
                source_type=source_type(item["identifier"], source),
                rating=float(item.get("avg_rating") or 0),
                review_count=int(item.get("num_reviews") or 0),
                best_format="",
                source=source,
            )
            show = shows.get(date)
            if show is None:
                show = shows[date] = Show(date=date, venue="", city="")
            show.recordings.append(recording)
        for show in shows.values():
            show.recordings = rank_recordings(show.recordings)
            # Spellings vary between tapers; use the best-ranked recording's venue/city
            for rec in show.recordings:
                doc = docs_by_id[rec.identifier]
                show.venue = show.venue or doc.get("venue") or ""
                show.city = show.city or doc.get("coverage") or ""
            show.venue = show.venue or "Unknown venue"
        return sorted(shows.values(), key=lambda s: s.date)

    async def recording_tracks(self, identifier: str) -> Recording:
        """Get recording metadata and tracks (cached on disk)"""
        cache_file = self.cache_dir / "meta" / f"{identifier}.json"
        if cache_file.exists():
            try:
                return self._parse_recording_data(json.loads(cache_file.read_text()))
            except (ValueError, KeyError, TypeError):
                pass  # stale or corrupt cache, refetch

        response = await self.client.get(METADATA_URL.format(identifier=identifier))
        response.raise_for_status()
        recording = self._parse_metadata(identifier, response.json())

        if recording.tracks:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(asdict(recording)))
        return recording

    def _parse_metadata(self, identifier: str, data: Dict) -> Recording:
        """Build a Recording from an archive.org /metadata response"""
        meta = data.get("metadata", {})
        files = data.get("files", [])
        by_name = {f["name"]: f for f in files}

        chosen_format, ext = None, ""
        for fmt, fmt_ext in FORMAT_PREFERENCE:
            if any(f.get("format") == fmt for f in files):
                chosen_format, ext = fmt, fmt_ext
                break

        entries = []
        for f in files:
            if f.get("format") != chosen_format:
                continue
            # Derivatives often lack title/track; fall back to the original file
            original = by_name.get(f.get("original") or "", {})
            title = f.get("title") or original.get("title") or Path(f["name"]).stem
            num = re.match(r"\d+", str(f.get("track") or original.get("track") or ""))
            disc = re.search(r"d(\d+)t\d+", f["name"], re.I)
            track = Track(
                title=title,
                filename=f["name"],
                length=parse_length(f.get("length") or original.get("length")),
                set=f"Disc {int(disc.group(1))}" if disc else "",
                position=0,
                url=DOWNLOAD_URL.format(identifier=identifier, name=quote(f["name"])),
            )
            entries.append(((int(num.group()) if num else 10**6, f["name"]), track))

        tracks = [track for _, track in sorted(entries, key=lambda e: e[0])]
        for i, track in enumerate(tracks, 1):
            track.position = i

        reviews = data.get("reviews") or []
        ratings = [float(r["stars"]) for r in reviews if r.get("stars")]
        source = meta.get("source") or ""
        if isinstance(source, list):
            source = " ".join(source)
        return Recording(
            identifier=identifier,
            source_type=source_type(identifier, source),
            rating=round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
            review_count=len(reviews),
            best_format=ext,
            tracks=tracks,
            source=source,
        )

    def _parse_recording_data(self, data: Dict) -> Recording:
        """Parse recording data from cache"""
        return Recording(
            identifier=data['identifier'],
            source_type=data['source_type'],
            rating=data['rating'],
            review_count=data['review_count'],
            best_format=data['best_format'],
            tracks=[Track(**track) for track in data['tracks']],
            source=data.get('source', ''),
        )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
