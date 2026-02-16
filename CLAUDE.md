# Sound Player - AI Agent Guide

This guide contains essential information for AI agents working on the **sound-player** project.

## Project Overview

**sound-player** is a Python library for playing multiple sound files with support for audio layers and concurrent playback. It provides a simple API to play, pause, and stop sounds individually or in audio layers.

- **Repository**: https://github.com/Krozark/sound-player
- **License**: BSD 2-Clause
- **Author**: Maxime Barbier
- **Current Version**: 0.5.0
- **Python**: >=3.11

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
│   ├── audiolayer.py      # AudioLayer class
│   ├── player.py          # SoundPlayer class
│   ├── sound.py           # BaseSound abstract class
│   ├── common.py          # STATUS enum and StatusObject base
│   ├── linux.py           # Linux implementation (FFMpegSound)
│   ├── android.py         # Android implementation (AndroidSound)
│   └── vlc_sound.py       # VLC-based implementation (optional)
├── tests/                 # Unit tests
│   ├── conftest.py        # Pytest fixtures
│   ├── test_common.py     # Tests for common.py
│   ├── test_sound.py      # Tests for sound.py
│   ├── test_audiolayer.py # Tests for audiolayer.py
│   └── test_player.py     # Tests for player.py
├── data/                  # Test audio files
│   ├── music.ogg
│   └── coin.wav
├── example.py             # Usage examples
├── pyproject.toml         # Project metadata and Ruff configuration
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

### AudioLayer System (`audiolayer.py`, `player.py`)

- **AudioLayer** (`audiolayer.py`): Manages a queue of sounds with concurrent playback
  - `concurrency`: Max number of sounds playing simultaneously
  - `replace`: If True, stops old sounds when adding new ones beyond concurrency limit
  - `loop`: Loop count for the audio layer (infinite if -1)
  - `volume`: Volume for sounds in the audio layer
  - Methods: `enqueue()`, `play()`, `pause()`, `stop()`, `clear()`

- **SoundPlayer**: Manages multiple audio layers
  - `create_audio_layer(id, **kwargs)`: Create a new audio layer
  - `enqueue(sound, layer_id)`: Add sound to specific audio layer
  - `play/pause/stop(layer_id)`: Control specific or all audio layers

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

### Building

The project uses PEP 621 with `pyproject.toml` for package configuration.

```bash
# Build the package
python -m build

# Install in development mode
pip install -e .
```

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

1. **Threading**: `AudioLayer` uses a daemon thread to manage the sound queue. The thread polls every 0.1s to:
   - Remove stopped sounds
   - Start new sounds from the waiting queue
   - Handle the `replace` mode

2. **Locking**: Uses `threading.RLock()` for thread-safe operations in `AudioLayer` and `SoundPlayer`

3. **Logging**: Extensive debug logging using Python's `logging` module. Use `logger.debug()` for tracing.

4. **Loop convention**:
  - `-1` means infinite loop
  - `0` or positive numbers are finite loops

## Testing

The project uses **pytest** for unit testing with 89 tests covering all core functionality.

Run tests:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=sound_player --cov-report=html
```

### Test Structure

- `tests/test_common.py` - Tests for STATUS enum and StatusObject
- `tests/test_sound.py` - Tests for BaseSound abstract class
- `tests/test_audiolayer.py` - Tests for AudioLayer class
- `tests/test_player.py` - Tests for SoundPlayer class
- `tests/conftest.py` - Pytest fixtures and configuration

### Manual Testing

Run the example file for manual functional testing:
```bash
python example.py
```

The example tests:
1. Individual sound playback (play, pause, stop)
2. AudioLayer with concurrency
3. Multiple audio layers via SoundPlayer
4. Loop functionality

## Dependencies

- `krozark-current-platform`: Platform detection
- (Android only) `jnius`, `android`: Android platform APIs
- System: `ffplay` or `avplay` for Linux

## Common Tasks

- **Add a new platform**: Create a new `<platform>.py` file with a `*Sound` class extending `BaseSound`, then add platform detection in `__init__.py`
- **Modify audio layer behavior**: Edit `audiolayer.py`, specifically the `_thread_task` method
- **Add new sound features**: Extend `BaseSound` interface, then implement in platform-specific classes

## Notes

- The library is designed for games and applications that need multiple concurrent sounds
- Thread-safe operations are important due to the daemon thread in AudioLayer
- Platform-specific code should be isolated to platform-specific modules
