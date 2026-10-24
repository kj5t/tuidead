"""
CLI test for Dead Archives
"""
import asyncio
import sys
from pathlib import Path
from dead.archive import ArchiveClient


async def main():
    """CLI test for Dead Archives"""
    print("Dead Archives CLI Test")
    print("=" * 30)
    
    # Create archive client
    client = ArchiveClient()
    
    # Test search
    print("Searching for shows...")
    shows = await client.search("1977-05-08")
    
    if shows:
        show = shows[0]
        print(f"Found show: {show}")
        
        # Test getting recording tracks
        recording = await client.recording_tracks(show.recordings[0].identifier)
        print(f"Recording: {recording.identifier}")
        print(f"Source: {recording.source_type}")
        print(f"Rating: {recording.rating} ({recording.review_count} reviews)")
        print(f"Best format: {recording.best_format}")
        
        print("\nTracks:")
        for track in recording.tracks:
            print(f"  {track}")
    else:
        print("No shows found")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())