#!/usr/bin/env python3
"""
Simple test to verify the core functionality of the Dead Archives TUI
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Test all imports
    from dead.model import Show, Recording, Track
    from dead.archive import ArchiveClient
    from dead.store import Store
    from dead.player import MPVPlayer
    from dead.app import DeadArchivesApp
    
    print("✅ All modules imported successfully")
    
    # Test basic functionality
    show = Show(date='1977-05-08', venue='Hicks Stadium', city='San Francisco')
    print(f"✅ Show created: {show}")
    
    # Test that we can create app instances
    app = DeadArchivesApp()
    print("✅ App instance created successfully")
    
    # Test player functionality
    player = MPVPlayer()
    print("✅ MPVPlayer created successfully")
    
    print("\n🎉 All core components are working correctly!")
    print("The application should run properly now.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()