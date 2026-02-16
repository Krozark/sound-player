# Sound Player - AI Agent Guide

This guide contains essential information for AI agents working on the **sound-player** project.

## Project Overview

**sound-player** is a Python library for playing multiple sound files with support for playlists and concurrent playback. It provides a simple API to play, pause, and stop sounds individually or in playlists.

- **Repository**: https://github.com/Krozark/sound-player
- **License**: BSD 2-Clause
- **Author**: Maxime Barbier
- **Current Version**: 0.4.10
- **Python**: >=3.6

## Supported Platforms

- [x] Linux
- [x] Android
- [ ] Windows (planned)
- [ ] macOS (planned)
- [ ] iOS (planned)

## Project Structure

```
sound-player/
├── sound_player/          # Main package
│   ├── __init__.py        # Platform detection and exports
│   ├── player.py          # Playlist and SoundPlayer classes
│   ├── sound.py           # BaseSound abstract class
│   ├── common.py          # STATUS enum and StatusObject base
│   ├── linux.py           # Linux implementation (FFMpegSound)
│   ├── android.py         # Android implementation (AndroidSound)
│   └── vlc_sound.py       # VLC-based implementation (optional)
├── data/                  # Test audio files
│   ├── music.ogg
│   └── coin.wav
├── example.py             # Usage examples
├── setup.py               # Package setup
├── pyproject.toml         # Ruff configuration
└── .pre-commit-config.yaml # Pre-commit hooks
```

## Key Classes and Architecture

### Status System (`common.py`)

The library uses a status enum to track playback state:

```python
class STATUS(Enum):
    ERROR = -1
    STOPPED = 1
    PLAYING = 2
    PAUSED = 3
```

`StatusObject` is the base class for anything that has a playback status.

### Sound Classes

- **BaseSound** (`sound.py`): Abstract base class defining the sound interface
  - Methods: `play()`, `pause()`, `stop()`, `wait()`, `set_loop()`, `set_volume()`
  - Platform-specific implementations override `_do_play()`, `_do_pause()`, `_do_stop()`

- **LinuxSound/FFMpegSound** (`linux.py`): Linux implementation using ffplay/avplay
  - Uses subprocess to control ffplay/avplay processes
  - Signals: SIGCONT for resume, SIGSTOP for pause

- **AndroidSound** (`android.py`): Android implementation using MediaPlayer
  - Uses JNIus (PyJNIus) to call Android's MediaPlayer API
  - Handles completion callbacks for loop functionality

### Playlist System (`player.py`)

- **Playlist**: Manages a queue of sounds with concurrent playback
  - `concurrency`: Max number of sounds playing simultaneously
  - `replace`: If True, stops old sounds when adding new ones beyond concurrency limit
  - `loop`: Loop count for the playlist (infinite if -1)
  - `volume`: Volume for sounds in the playlist
  - Methods: `enqueue()`, `play()`, `pause()`, `stop()`, `clear()`

- **SoundPlayer**: Manages multiple playlists
  - `create_playlist(id, **kwargs)`: Create a new playlist
  - `enqueue(sound, playlist_id)`: Add sound to specific playlist
  - `play/pause/stop(playlist_id)`: Control specific or all playlists

## Development Workflow

### Code Quality Tools

The project uses:
- **Ruff** for linting and formatting (configured in `pyproject.toml`)
- **Pre-commit hooks** to run Ruff automatically

Run manually:
```bash
ruff check .
ruff format .
```

### Configuration

From `pyproject.toml`:
- Line length: 120 characters
- Target Python: 3.12
- Quote style: double quotes
- Excluded: `data/*` directory

## Platform Detection

Platform detection uses the `krozark-current-platform` package:

```python
from currentplatform import platform

if platform == "linux":
    from .linux import LinuxSound as Sound
elif platform == "android":
    from .android import AndroidSound as Sound
```

## Important Patterns

1. **Threading**: `Playlist` uses a daemon thread to manage the sound queue. The thread polls every 0.1s to:
   - Remove stopped sounds
   - Start new sounds from the waiting queue
   - Handle the `replace` mode

2. **Locking**: Uses `threading.RLock()` for thread-safe operations in `Playlist` and `SoundPlayer`

3. **Logging**: Extensive debug logging using Python's `logging` module. Use `logger.debug()` for tracing.

4. **Loop convention**:
  - `-1` means infinite loop
  - `0` or positive numbers are finite loops

## Testing

Run the example file to test functionality:
```bash
python example.py
```

The example tests:
1. Individual sound playback (play, pause, stop)
2. Playlist with concurrency
3. Multiple playlists via SoundPlayer
4. Loop functionality

## Dependencies

- `krozark-current-platform`: Platform detection
- (Android only) `jnius`, `android`: Android platform APIs
- System: `ffplay` or `avplay` for Linux

## Common Tasks

- **Add a new platform**: Create a new `<platform>.py` file with a `*Sound` class extending `BaseSound`, then add platform detection in `__init__.py`
- **Modify playlist behavior**: Edit `player.py`, specifically the `_thread_task` method
- **Add new sound features**: Extend `BaseSound` interface, then implement in platform-specific classes

## Notes

- The library is designed for games and applications that need multiple concurrent sounds
- Thread-safe operations are important due to the daemon thread in Playlist
- Platform-specific code should be isolated to platform-specific modules
