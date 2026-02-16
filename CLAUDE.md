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
- **Mixin architecture** - Reusable mixins for status, volume, and configuration management

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
│   ├── core/              # Core module with base classes
│   │   ├── __init__.py    # Core exports
│   │   ├── audio_config.py # AudioConfig dataclass
│   │   ├── mixins.py      # StatusMixin, VolumeMixin, LockMixin, AudioConfigMixin
│   │   ├── base_sound.py  # BaseSound abstract class
│   │   └── base_player.py # BaseSoundPlayer abstract class
│   ├── platform/          # Platform-specific implementations
│   │   ├── __init__.py    # Platform detection and exports
│   │   ├── linux/         # Linux implementation
│   │   │   ├── __init__.py
│   │   │   ├── sound.py   # LinuxPCMSound (soundfile decoding)
│   │   │   └── player.py  # LinuxSoundPlayer (sounddevice output)
│   │   └── android/       # Android implementation
│   │       ├── __init__.py
│   │       ├── sound.py   # AndroidPCMSound
│   │       └── player.py  # AndroidSoundPlayer
│   ├── mixer.py           # AudioMixer for mixing streams
│   └── audiolayer.py      # AudioLayer class with mixer
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

**Note:** All volume values use the 0.0-1.0 float range consistently across all levels (sound, layer, master).

### Mixin Architecture

The library uses a cooperative mixin-based inheritance pattern to provide reusable functionality:

```
LockMixin
    └── VolumeMixin (extends LockMixin)
            └── StatusMixin (extends VolumeMixin)

AudioConfigMixin (standalone, used with StatusMixin)
```

#### Mixin Classes

**LockMixin** (`core/mixins.py`)
- Provides `threading.RLock()` for thread-safe operations
- Base mixin for all other mixins

**VolumeMixin** (`core/mixins.py`)
- Extends `LockMixin`
- Manages volume with `_volume` attribute
- Provides `set_volume()` and `volume` property
- Clamps values to 0.0-1.0 range
- Thread-safe via inherited lock

**StatusMixin** (`core/mixins.py`)
- Extends `VolumeMixin` (inherits volume management and lock)
- Manages playback status with `_status` attribute
- Provides `play()`, `pause()`, `stop()` methods
- Thread-safe status transitions
- Hooks for subclasses: `_do_play()`, `_do_pause()`, `_do_stop()`
- **Critical**: Status is set BEFORE calling hooks to avoid race conditions

**AudioConfigMixin** (`core/mixins.py`)
- Manages `AudioConfig` object
- Provides `config` property
- Used in combination with `StatusMixin`

#### Mixin Usage Example

```python
# AudioLayer inherits from both StatusMixin and AudioConfigMixin
class AudioLayer(StatusMixin, AudioConfigMixin):
    def __init__(self, ...):
        super().__init__(*args, **kwargs)  # Cooperative inheritance
        # StatusMixin provides: _status, volume, play(), pause(), stop(), _lock
        # AudioConfigMixin provides: config
```

### Key Classes

#### AudioConfig (`core/audio_config.py`)

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
- Takes `owner` parameter for config/volume delegation
- `add_sound(sound)` - Add a sound to the mixer
- `remove_sound(sound)` - Remove a sound
- `get_next_chunk()` - Get the next mixed buffer
- `sound_count` property - Number of sounds in mixer
- Thread-safe with inherited `LockMixin`

**Owner Pattern:** The mixer delegates `config` and `volume` properties to its owner (typically an `AudioLayer` or `SoundPlayer`).

#### BaseSound (`core/base_sound.py`)

Abstract base class with PCM buffer interface:

**Inheritance:** `StatusMixin, AudioConfigMixin`

**Core Methods:**
- `play()`, `pause()`, `stop()`, `wait()` - Inherited from `StatusMixin`
- `set_loop(loop)`, `set_volume(volume)` - Volume from `StatusMixin`, loop is custom

**PCM Interface (must be implemented by subclasses):**
- `get_next_chunk(size)` - Return next audio chunk as numpy array
- `get_sample_rate()` - Return sample rate
- `get_channels()` - Return channel count
- `seek(position)` - Seek to position in seconds

#### AudioLayer (`audiolayer.py`)

Manages a queue of sounds with mixing:

**Inheritance:** `StatusMixin, AudioConfigMixin`

**Properties:**
- `concurrency` - Max concurrent sounds
- `replace` - Stop old sounds when limit exceeded
- `loop` - Default loop count for sounds
- `volume` - Layer volume (0.0-1.0, inherited from `StatusMixin`)
- `mixer` - Internal AudioMixer instance

**Methods:**
- `enqueue(sound)` - Add sound to waiting queue
- `play()`, `pause()`, `stop()` - Inherited from `StatusMixin`
- `clear()` - Clear all queues
- `set_concurrency(n)`, `set_replace(bool)`, `set_loop(n)`
- `get_next_chunk()` - Get mixed audio from current sounds

**Threading:**
- Daemon thread manages sound lifecycle
- Polls every 100ms to update queues
- Thread-safe via inherited `LockMixin` (through `StatusMixin`)

#### BaseSoundPlayer (`core/base_player.py`)

Abstract base class for platform-specific audio output:

**Inheritance:** `StatusMixin, AudioConfigMixin`

**Methods:**
- `create_audio_layer(id, **kwargs)` - Create new audio layer
- `enqueue(sound, layer_id)` - Add sound to layer
- `play(layer_id)`, `pause(layer_id)`, `stop(layer_id)` - Control playback
- `set_volume(volume)`, `get_volume()` - Master volume (inherited from `StatusMixin`)
- `get_next_chunk()` - Get mixed output from all layers
- `__getitem__(layer_id)` - Access layer by ID

**Abstract Methods** (platform-specific):
- `_create_output_stream()` - Create platform audio stream
- `_write_audio(data)` - Write audio to output
- `_close_output_stream()` - Close audio stream

### Platform Implementations

### Platform Implementations

#### LinuxPCMSound (`platform/linux/sound.py`)

Linux implementation using:
- **soundfile** for audio decoding (supports many formats)
- Implements PCM buffer interface via `get_next_chunk()`
- Supports sample rate conversion and channel conversion

#### LinuxSoundPlayer (`platform/linux/player.py`)

Linux audio output using:
- **sounddevice** for audio output (blocking write mode)
- Continuously pulls mixed audio and writes to device
- Inherits from `BaseSoundPlayer`

#### AndroidPCMSound (`platform/android/sound.py`)

Android implementation (placeholder for future development):
- Will use AudioTrack for PCM output
- Will use Android media APIs for decoding

#### AndroidSoundPlayer (`platform/android/player.py`)

Android audio output using AudioTrack (placeholder):
- Uses JNIus to access Android AudioTrack
- Implements blocking write mode

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
2. **Mixin Cooperative Inheritance**: All mixins use `*args, **kwargs` to pass through to parent classes
3. **Status-First Hook Pattern**: In `StatusMixin`, status is set BEFORE calling hooks to avoid race conditions
4. **Threading**: `AudioLayer` uses a daemon thread that polls every 100ms
5. **Locking**: Uses `threading.RLock()` for thread-safe operations via `LockMixin`
6. **Logging**: Extensive debug logging using Python's `logging` module
7. **Loop convention**: `-1` means infinite loop, positive numbers are finite loops
8. **Volume hierarchy**: All volumes use 0.0-1.0 float range consistently
   - Sound volume × Layer volume × Master volume = Final output

## Common Tasks

- **Add a new platform**: Create new `platform/<platform>/` directory with:
  - `sound.py` containing `*PCMSound` class extending `BaseSound`
  - `player.py` containing `*SoundPlayer` class extending `BaseSoundPlayer`
  - `__init__.py` to export the classes
  - Add platform detection in `platform/__init__.py`
- **Modify audio mixing behavior**: Edit `mixer.py`, specifically the `get_next_chunk()` method
- **Add new sound features**: Extend `BaseSound` interface in `core/base_sound.py`, then implement in platform-specific classes
- **Add new mixin**: Create mixin in `core/mixins.py` with cooperative inheritance pattern

## Notes

- The library is designed for games and applications that need multiple concurrent sounds with real-time mixing
- Thread-safe operations are important due to the daemon thread in AudioLayer
- Platform-specific code should be isolated to platform-specific modules
- Audio output is integrated via `BaseSoundPlayer` subclasses (Linux uses sounddevice, Android uses AudioTrack)
- All volume values consistently use 0.0-1.0 float range for predictable behavior
- Status hooks (`_do_play`, `_do_pause`, `_do_stop`) are called WITH the lock held - keep them lightweight
