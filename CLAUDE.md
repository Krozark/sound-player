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
- **Fade effects** with configurable curves (linear, exponential, logarithmic, S-curve)
- **Crossfade support** for smooth transitions between sounds in replace mode
- **PCM buffer interface** for integrating with any audio output
- **Cross-platform** architecture (Linux, Windows, Android, with more planned)
- **Mixin architecture** - Reusable mixins for status, volume, fade, and configuration management

## Supported Platforms

- [x] Linux
- [x] Windows (shares Linux sounddevice/soundfile implementation)
- [x] Android
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
│   │   ├── constants.py   # Audio format constants (MAX_INT16, etc.)
│   │   ├── mixins/        # Mixin package
│   │   │   ├── __init__.py    # Mixin exports
│   │   │   ├── lock.py        # LockMixin
│   │   │   ├── volume.py      # VolumeMixin
│   │   │   ├── status.py      # StatusMixin, STATUS enum
│   │   │   ├── fade.py        # FadeMixin, FadeState, FadeCurve
│   │   │   └── audio_config.py # AudioConfigMixin
│   │   ├── base_sound.py  # BaseSound abstract class
│   │   └── base_player.py # BaseSoundPlayer abstract class
│   ├── platform/          # Platform-specific implementations
│   │   ├── __init__.py    # Platform detection and exports
│   │   ├── linux/         # Linux/Windows implementation
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
│   ├── test_common.py     # Tests for StatusMixin/VolumeMixin
│   ├── test_sound.py      # Tests for BaseSound
│   ├── test_audiolayer.py # Tests for AudioLayer
│   ├── test_player.py     # Tests for BaseSoundPlayer
│   ├── test_audio_config.py  # Tests for AudioConfig
│   ├── test_mixer.py      # Tests for AudioMixer
│   ├── test_fade_mixin.py # Tests for FadeMixin
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
├── VolumeMixin (extends LockMixin)
│   └── FadeMixin (extends VolumeMixin)
└── StatusMixin (extends LockMixin)

AudioConfigMixin (standalone)
```

#### Mixin Classes

**LockMixin** (`core/mixins/lock.py`)
- Provides `threading.RLock()` for thread-safe operations
- Base mixin for all other mixins

**VolumeMixin** (`core/mixins/volume.py`)
- Extends `LockMixin`
- Manages volume with `_volume` attribute
- Provides `set_volume()` and `volume` property
- Clamps values to 0.0-1.0 range
- Thread-safe via inherited lock

**StatusMixin** (`core/mixins/status.py`)
- Extends `LockMixin` (inherits lock for thread safety)
- Manages playback status with `_status` attribute
- Provides `play()`, `pause()`, `stop()` methods
- Thread-safe status transitions
- Hooks for subclasses: `_do_play()`, `_do_pause()`, `_do_stop()`
- **Critical**: Status is set BEFORE calling hooks to avoid race conditions

**FadeMixin** (`core/mixins/fade.py`)
- Extends `VolumeMixin` (inherits volume management and lock)
- Manages fade state with sample-accurate timing
- Provides `fade_in(duration)`, `fade_out(duration)` convenience methods
- Provides `start_fade_in(duration, target_volume)`, `start_fade_out(duration, target_volume)` for fine control
- Configurable fade curves: `LINEAR`, `EXPONENTIAL`, `LOGARITHMIC`, `SCURVE` (default)
- `_get_fade_multiplier_array(size)` generates per-sample fade multipliers for a chunk
- Properties: `fade_state`, `fade_curve`, `is_fading`

**AudioConfigMixin** (`core/mixins/audio_config.py`)
- Manages `AudioConfig` object
- Provides `config` property
- Used in combination with other mixins

#### Mixin Usage Example

```python
# AudioLayer inherits from StatusMixin, VolumeMixin, and AudioConfigMixin
class AudioLayer(StatusMixin, VolumeMixin, AudioConfigMixin):
    def __init__(self, ...):
        super().__init__(*args, **kwargs)  # Cooperative inheritance
        # StatusMixin provides: _status, play(), pause(), stop(), _lock
        # VolumeMixin provides: _volume, set_volume(), volume property
        # AudioConfigMixin provides: config

# BaseSound inherits from StatusMixin, AudioConfigMixin, and FadeMixin
class BaseSound(StatusMixin, AudioConfigMixin, FadeMixin):
    # StatusMixin provides: _status, play(), pause(), stop(), _lock
    # FadeMixin provides: _volume (via VolumeMixin), fade_in(), fade_out(), _get_fade_multiplier_array()
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

**Inheritance:** `StatusMixin, AudioConfigMixin, FadeMixin`

**Core Methods:**
- `play()`, `pause()`, `stop()`, `wait()` - Inherited from `StatusMixin`
- `set_loop(loop)` - Custom loop management
- `set_volume(volume)` - Volume from `VolumeMixin` (via `FadeMixin`)
- `fade_in(duration)`, `fade_out(duration)` - Inherited from `FadeMixin`
- `get_next_chunk(size)` - Returns faded audio chunk (handles fade math automatically)

**PCM Interface (must be implemented by subclasses):**
- `_do_get_next_chunk(size)` - Return next raw audio chunk as numpy array
- `get_sample_rate()` - Return sample rate
- `get_channels()` - Return channel count
- `seek(position)` - Seek to position in seconds

#### AudioLayer (`audiolayer.py`)

Manages a queue of sounds with mixing:

**Inheritance:** `StatusMixin, VolumeMixin, AudioConfigMixin`

**Properties:**
- `concurrency` - Max concurrent sounds
- `replace` - Stop old sounds when limit exceeded
- `loop` - Default loop count for sounds
- `volume` - Layer volume (0.0-1.0, from `VolumeMixin`)
- `mixer` - Internal AudioMixer instance

**Methods:**
- `enqueue(sound, fade_in=None, fade_out=None)` - Add sound to waiting queue, applies layer defaults for loop, fade curve, and fade durations
- `play()`, `pause()`, `stop()` - Inherited from `StatusMixin`
- `clear()` - Clear all queues
- `set_concurrency(n)`, `set_replace(bool)`, `set_loop(n)`
- `set_fade_in_duration(duration)`, `set_fade_out_duration(duration)`, `set_fade_curve(curve)` - Fade defaults for enqueued sounds
- `get_next_chunk()` - Get mixed audio from current sounds

**Crossfade Support:**
- When `replace=True` and `fade_out_duration` is set, replaced sounds fade out instead of stopping immediately
- Fading-out sounds are tracked in `_fading_out_sounds` and removed once the fade completes

**Threading:**
- Daemon thread manages sound lifecycle
- Polls every 100ms to update queues
- Thread-safe via inherited `LockMixin` (through `StatusMixin`)

#### BaseSoundPlayer (`core/base_player.py`)

Abstract base class for platform-specific audio output:

**Inheritance:** `StatusMixin, VolumeMixin, AudioConfigMixin, ABC`

**Methods:**
- `create_audio_layer(id, force=False, **kwargs)` - Create new audio layer (use `force=True` to overwrite existing)
- `delete_audio_layer(id)` - Delete an audio layer
- `enqueue(sound, layer_id)` - Add sound to layer
- `play(layer_id)`, `pause(layer_id)`, `stop(layer_id)` - Control playback
- `set_volume(volume)` - Master volume (from `VolumeMixin`)
- `get_next_chunk()` - Get mixed output from all layers
- `get_audio_layers()` - Get all layer names
- `clear(layer_id)` - Clear queues
- `__getitem__(layer_id)` - Access layer by ID

**Abstract Methods** (platform-specific):
- `_create_output_stream()` - Create platform audio stream
- `_close_output_stream()` - Close audio stream

### Platform Implementations

#### LinuxPCMSound (`platform/linux/sound.py`)

Linux/Windows implementation using:
- **soundfile** for audio decoding (supports many formats)
- Implements PCM buffer interface via `_do_get_next_chunk()`
- Supports sample rate conversion and channel conversion
- Float-to-int conversion for float-format audio files (Vorbis, OPUS, MP3, FLAC)

#### LinuxSoundPlayer (`platform/linux/player.py`)

Linux/Windows audio output using:
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

**Optional (Linux/Windows):**
- `sounddevice~=0.4` - Audio output (install with `pip install sound-player[linux]` or `pip install sound-player[windows]`)

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

The project uses **pytest** for unit testing with 169 tests covering all core functionality.

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

if platform in ("linux", "windows"):
    # Linux and Windows share the same sounddevice/soundfile-based implementation
    from .linux import LinuxPCMSound as Sound
    from .linux import LinuxSoundPlayer as SoundPlayer
elif platform == "android":
    from .android import AndroidPCMSound as Sound
    from .android import AndroidSoundPlayer as SoundPlayer
else:
    raise NotImplementedError(f"No implementation available for platform: {platform}")
```

## Important Patterns

1. **PCM Buffer Interface**: All sounds implement `_do_get_next_chunk(size)` which returns numpy arrays for mixing. The public `get_next_chunk(size)` in `BaseSound` handles fade math and thread safety.
2. **Mixin Cooperative Inheritance**: All mixins use `*args, **kwargs` to pass through to parent classes
3. **Status-First Hook Pattern**: In `StatusMixin`, status is set BEFORE calling hooks to avoid race conditions
4. **Threading**: `AudioLayer` uses a daemon thread that polls every 100ms
5. **Locking**: Uses `threading.RLock()` for thread-safe operations via `LockMixin`
6. **Logging**: Extensive debug logging using Python's `logging` module
7. **Loop convention**: `-1` means infinite loop, positive numbers are finite loops
8. **Volume hierarchy**: All volumes use 0.0-1.0 float range consistently
   - Sound volume × Layer volume × Master volume = Final output
9. **Fade integration**: `BaseSound.get_next_chunk()` applies per-sample fade multipliers from `FadeMixin` after getting raw data from `_do_get_next_chunk()`. Auto-stops playback when a fade-out completes to volume 0.

## Common Tasks

- **Add a new platform**: Create new `platform/<platform>/` directory with:
  - `sound.py` containing `*PCMSound` class extending `BaseSound`
  - `player.py` containing `*SoundPlayer` class extending `BaseSoundPlayer`
  - `__init__.py` to export the classes
  - Add platform detection in `platform/__init__.py`
- **Modify audio mixing behavior**: Edit `mixer.py`, specifically the `get_next_chunk()` method
- **Add new sound features**: Extend `BaseSound` interface in `core/base_sound.py`, then implement in platform-specific classes
- **Add new mixin**: Create mixin in `core/mixins/` package with cooperative inheritance pattern

## Notes

- The library is designed for games and applications that need multiple concurrent sounds with real-time mixing
- Thread-safe operations are important due to the daemon thread in AudioLayer
- Platform-specific code should be isolated to platform-specific modules
- Audio output is integrated via `BaseSoundPlayer` subclasses (Linux/Windows use sounddevice, Android uses AudioTrack)
- All volume values consistently use 0.0-1.0 float range for predictable behavior
- Status hooks (`_do_play`, `_do_pause`, `_do_stop`) are called WITH the lock held - keep them lightweight
