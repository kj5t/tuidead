"""
Simple test for the store functionality
"""
import asyncio
import sys
from pathlib import Path
from dead.store import Store
from dead.model import Show, Recording, Track


def test_store():
    """Test the store functionality"""
    print("Testing Store functionality")
    print("=" * 30)
    
    # Create store
    from pathlib import Path
    store = Store(Path("/tmp/test_store.db"))
    
    # Test saving and retrieving a show
    show = Show("1977-05-08", "Hicks Stadium", "San Francisco")
    store.save_show(show)
    
    retrieved_show = store.get_show("1977-05-08")
    print(f"Retrieved show: {retrieved_show}")
    
    # Test saving and retrieving a recording
    recording = Recording(
        identifier="gd77-05-08.sbd.hicks",
        source_type="sbd",
        rating=4.78,
        review_count=300,
        best_format="mp3",
        tracks=[
            Track("Jack Straw", "01_jack_straw.mp3", 245, "Set 1", 1),
            Track("Box of Rain", "02_box_of_rain.mp3", 210, "Set 1", 2),
        ]
    )
    
    store.save_recording(recording)
    store.save_tracks(recording)
    
    retrieved_recording = store.get_recording("gd77-05-08.sbd.hicks")
    print(f"Retrieved recording: {retrieved_recording.identifier}")
    
    retrieved_tracks = store.get_tracks("gd77-05-08.sbd.hicks")
    print(f"Retrieved {len(retrieved_tracks)} tracks")
    for track in retrieved_tracks:
        print(f"  {track}")


if __name__ == "__main__":
    test_store()