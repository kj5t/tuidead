#!/usr/bin/env python3
"""
Dead Archives TUI - A terminal-based player for the Dead's recordings
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from dead.app import DeadArchivesApp

if __name__ == "__main__":
    app = DeadArchivesApp()
    app.run()