#!/usr/bin/env python3
"""
Test script to verify Dead Archives functionality without TUI
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_archive_client():
    """Test the archive client functionality"""
    try:
        from dead.archive import ArchiveClient
        client = ArchiveClient()
        print("✅ ArchiveClient created successfully")
        
        # Test that we can at least create the client
        # (We won't actually call search since that requires network)
        return True
    except Exception as e:
        print(f"❌ ArchiveClient test failed: {e}")
        return False

def test_models():
    """Test data models"""
    try:
        from dead.model import Show, Recording, Track
        
        # Test Show model
        show = Show(date='1977-05-08', venue='Hicks Stadium', city='San Francisco')
        print(f"✅ Show model works: {show}")
        
        # Test Recording model  
        recording = Recording(
            identifier="test-id",
            source_type="official",
            rating=4.5,
            review_count=100,
            best_format="mp3",
            tracks=[]
        )
        print(f"✅ Recording model works: {recording.identifier}")
        
        # Test Track model
        track = Track(
            title="Test Track",
            filename="test.mp3",
            length=180,
            set="Set 1",
            position=1
        )
        print(f"✅ Track model works: {track.title}")
        
        return True
    except Exception as e:
        print(f"❌ Models test failed: {e}")
        return False

def test_store():
    """Test store/database functionality"""
    try:
        from dead.store import Store
        store = Store()
        print("✅ Store created successfully")
        return True
    except Exception as e:
        print(f"❌ Store test failed: {e}")
        return False

def test_player():
    """Test player functionality"""
    try:
        from dead.player import MPVPlayer
        player = MPVPlayer()
        print("✅ MPVPlayer created successfully")
        return True
    except Exception as e:
        print(f"❌ Player test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Dead Archives components...")
    print("=" * 50)
    
    tests = [
        test_models,
        test_archive_client,
        test_store,
        test_player
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The application components are working correctly.")
    else:
        print("❌ Some tests failed. Check the error messages above.")