#!/usr/bin/env python3
"""Debug script to test components individually"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dead.model import Show
from dead.archive import ArchiveClient
from dead.store import Store
from dead.player import MPVPlayer

def test_components():
    print("Testing components...")
    
    # Test Show model
    show = Show("1977-05-08", "Hicks Stadium", "San Francisco")
    print(f"Show: {show}")
    
    # Test ArchiveClient
    try:
        client = ArchiveClient()
        print("ArchiveClient created successfully")
    except Exception as e:
        print(f"Error creating ArchiveClient: {e}")
    
    # Test Store
    try:
        store = Store()
        print("Store created successfully")
    except Exception as e:
        print(f"Error creating Store: {e}")
    
    # Test MPVPlayer
    try:
        player = MPVPlayer()
        print("MPVPlayer created successfully")
    except Exception as e:
        print(f"Error creating MPVPlayer: {e}")

if __name__ == "__main__":
    test_components()