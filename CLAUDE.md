# Sound Player - AI Agent Guide

This guide contains essential information for AI agents working on the **sound-player** project.

## Project Overview

**sound-player** is a Python library for playing multiple sound files with professional audio mixing support. It provides real-time PCM audio mixing with multiple audio layers, configurable audio formats, and volume controls at multiple levels.

- **Repository**: https://github.com/Krozark/sound-player
- **License**: BSD 2-Clause
- **Author**: Maxime Barbier
- **Current Version**: 1.0.0
- **Python**: >=3.11

## Key Features

- **Real-time audio mixing** using NumPy
- **Multiple audio layers** with independent volume control
- **Concurrent playback** with configurable limits
- **PCM buffer interface** for integrating with any audio output
- **Cross-platform** architecture (Linux, Android, with more planned)

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
│   ├── audio_config.py    # AudioConfig dataclass
│   ├── mixer.py           # AudioMixer for mixing streams
│   ├── audiolayer.py      # AudioLayer class with mixer
│   ├── player.py          # SoundPlayer for managing layers
│   ├── sound.py           # BaseSound abstract class
│   ├── common.py          # STATUS enum and StatusObject
│   ├── linux_pcm.py       # Linux PCM implementation
│   └── android_pcm.py     # Android PCM implementation
├── tests/                 # Unit tests
│   ├── conftest.py        # Pytest fixtures
│   ├── test_common.py     # Tests for common.py
│   ├── test_sound.py      # Tests for sound.py
│   ├── test_audiolayer.py # Tests for audiolayer.py
│   ├── test_player.py     # Tests for player.py
│   ├── test_audio_config.py  # Tests for AudioConfig
│   ├── test_mixer.py      # Tests for AudioMixer
│   └── test_linux_pcm.py  # Tests for LinuxPCMSound
├── data/                  # Test audio files
│   ├── music.ogg
│   └── coin.wav
├── example.py             # Usage examples
└── pyproject.toml         # Project metadata and configuration
```

## Core Architecture

### Audio Mixing Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                      SoundPlayer                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Master Mixer                              │   │
│  │  - Mixes all active AudioLayers                       │   │
│  │  - Applies master volume                              │   │
│  │  - Outputs to audio device                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│           ┌───────────────┼───────────────┐                 │
│           ▼               ▼               ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ AudioLayer  │  │ AudioLayer  │  │ AudioLayer  │       │
│  │  (music)    │  │   (sfx)     │  │  (voice)    │       │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤       │
│  │   Mixer     │  │   Mixer     │  │   Mixer     │       │
│  │ - Layer vol │  │ - Layer vol │  │ - Layer vol │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│         │                │                │                │
│         ▼                ▼                ▼                │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐           │
│  │   Sound   │   │   Sound   │   │   Sound   │           │
│  │           │   │           │   │           │           │
│  │ - Sound vol│   │ - Sound vol│   │ - Sound vol│           │
│  │ - Loop    │   │ - Loop    │   │ - Loop    │           │
│  └───────────┘   └───────────┘   └───────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### Volume Hierarchy

```
Final Output = (Sound1 × sound_vol1 + Sound2 × sound_vol2 + ...) × layer_vol × master_vol
```

### Key Classes

#### AudioConfig (`audio_config.py`)

Configuration for PCM audio processing:

```python
@dataclass
class AudioConfig:
    sample_rate: int = 44100  # Hz
    channels: int = 2          # 1=mono, 2=stereo
    sample_width: int = 2      # bytes (2=int16, 4=int32)
    buffer_size: int = 1024    # samples per buffer
    dtype: np.dtype = np.int16
```

#### AudioMixer (`mixer.py`)

Mixes multiple audio streams using NumPy:
- `add_sound(sound)` - Add a sound to the mixer
- `remove_sound(sound)` - Remove a sound
- `get_next_chunk()` - Get the next mixed buffer
- Thread-safe with `RLock`

#### BaseSound (`sound.py`)

Abstract base class with PCM buffer interface:

**Core Methods:**
- `play()`, `pause()`, `stop()`, `wait()`
- `set_loop(loop)`, `set_volume(volume)`

**PCM Interface (must be implemented by subclasses):**
- `get_next_chunk(size)` - Return next audio chunk as numpy array
- `get_sample_rate()` - Return sample rate
- `get_channels()` - Return channel count
- `get_audio_config()` - Return audio configuration
- `seek(position)` - Seek to position in seconds

#### AudioLayer (`audiolayer.py`)

Manages a queue of sounds with mixing:

**Properties:**
- `concurrency` - Max concurrent sounds
- `replace` - Stop old sounds when limit exceeded
- `loop` - Default loop count for sounds
- `volume` - Layer volume (0-100)
- `mixer` - Internal AudioMixer instance

**Methods:**
- `enqueue(sound)` - Add sound to waiting queue
- `play()`, `pause()`, `stop()`, `clear()`
- `get_next_chunk()` - Get mixed audio from current sounds

**Threading:**
- Daemon thread manages sound lifecycle
- Polls every 100ms to update queues
- Thread-safe with `RLock`

#### SoundPlayer (`player.py`)

Manages multiple audio layers:

**Methods:**
- `create_audio_layer(id, **kwargs)` - Create new layer
- `enqueue(sound, layer_id)` - Add sound to layer
- `play(layer_id)`, `pause(layer_id)`, `stop(layer_id)` - Control playback
- `set_master_volume(volume)` - Set master volume (0.0-1.0)
- `get_next_chunk()` - Get mixed output from all layers

### Platform Implementations

#### LinuxPCMSound (`linux_pcm.py`)

Linux implementation using:
- **soundfile** for audio decoding (supports many formats)
- Implements PCM buffer interface via `get_next_chunk()`
- Supports sample rate conversion and channel conversion

Audio output is handled by the user (e.g., with sounddevice).

#### AndroidPCMSound (`android_pcm.py`)

Android implementation (placeholder for future development):
- Will use AudioTrack for PCM output
- Will use Android media APIs for decoding

## Dependencies

**Required:**
- `krozark-current-platform` - Platform detection
- `numpy>=1.24` - Audio mixing
- `soundfile~=0.12` - Audio file decoding

**Optional (Linux):**
- `sounddevice~=0.4` - Audio output (install with `pip install sound-player[linux]`)

**Android:**
- `jnius`, `android` - Android platform APIs (already available on Android)

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

### Testing

The project uses **pytest** for unit testing with 151 tests covering all core functionality.

Run tests:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=sound_player --cov-report=html
```

### Manual Testing

Run the example file:
```bash
python example.py
```

## Platform Detection

Platform detection uses the `krozark-current-platform` package:

```python
from currentplatform import platform

if platform == "linux":
    from .linux_pcm import LinuxPCMSound as Sound
elif platform == "android":
    from .android_pcm import AndroidPCMSound as Sound
else:
    raise NotImplementedError()
```

## Important Patterns

1. **PCM Buffer Interface**: All sounds implement `get_next_chunk(size)` which returns numpy arrays for mixing
2. **Threading**: `AudioLayer` uses a daemon thread that polls every 100ms
3. **Locking**: Uses `threading.RLock()` for thread-safe operations
4. **Logging**: Extensive debug logging using Python's `logging` module
5. **Loop convention**: `-1` means infinite loop, positive numbers are finite loops
6. **Volume hierarchy**: Sound volume (0-100) → Layer volume (0-100) → Master volume (0.0-1.0)

## Common Tasks

- **Add a new platform**: Create a new `<platform>_pcm.py` file with a `*PCMSound` class extending `BaseSound`, implement the PCM interface methods, then add platform detection in `__init__.py`
- **Modify audio mixing behavior**: Edit `mixer.py`, specifically the `get_next_chunk()` method
- **Add new sound features**: Extend `BaseSound` interface in `sound.py`, then implement in platform-specific classes

## Notes

- The library is designed for games and applications that need multiple concurrent sounds with real-time mixing
- Thread-safe operations are important due to the daemon thread in AudioLayer
- Platform-specific code should be isolated to platform-specific modules
- Audio output is decoupled from mixing - users can choose any audio output library
