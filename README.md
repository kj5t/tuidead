# Dead Archives TUI

A terminal-based player for the Dead's recordings from archive.org.

## Features

- Browse shows by date
- Play recordings with gapless playback
- Track listing with progress bar
- Favorites and playback history
- Local caching for fast access

## Installation

```bash
pip install .
```

## Usage

```bash
tuidead
```

## Development

To run the CLI test:

```bash
python dead/cli_test.py
```

## Project Structure

- `dead/` - Main application code
  - `archive.py` - Archive.org API client
  - `model.py` - Data models
  - `player.py` - MPV player integration
  - `store.py` - SQLite storage
  - `app.py` - Textual UI
  - `cli_test.py` - CLI test script