# sound-player

A Python library for playing multiple sound files with professional real-time audio mixing support. Perfect for games and applications that need concurrent audio playback with multiple layers.

## Features

- **Real-time Audio Mixing** - Mix multiple audio streams simultaneously using NumPy
- **Multiple Audio Layers** - Organize sounds into independent layers (music, SFX, voice, etc.)
- **Volume Control** - Fine-grained volume at sound, layer, and master levels (all 0.0-1.0 float range)
- **Fade Effects** - Sample-accurate fade-in/fade-out with configurable curves (linear, exponential, logarithmic, S-curve)
- **Crossfade Support** - Smooth transitions between sounds in replace mode
- **Concurrent Playback** - Configure how many sounds can play simultaneously per layer
- **Loop Control** - Set sounds to loop infinitely or a specific number of times
- **Replace Mode** - Optionally stop or crossfade oldest sounds when concurrency limit is reached
- **Cross-Platform** - Support for Linux, Windows, Android (macOS/iOS planned)
- **Mixin Architecture** - Reusable mixins for status, volume, fade, and configuration management

## Installation

```bash
pip install sound-player
```

For Linux audio output support:
```bash
pip install sound-player[linux]
```

For Windows audio output support:
```bash
pip install sound-player[windows]
```

## Supported Platforms

- [x] Linux
- [x] Windows
- [x] Android
- [ ] macOS (planned)
- [ ] iOS (planned)

## Quick Start

```python
from sound_player import Sound, SoundPlayer

# Create a player with multiple audio layers
player = SoundPlayer()

# Create a music layer with background music
player.create_audio_layer("music", concurrency=1, volume=0.7)
player["music"].enqueue(Sound("background_music.ogg"))

# Create a sound effects layer
player.create_audio_layer("sfx", concurrency=3, volume=1.0)
player["sfx"].enqueue(Sound("coin.wav"))

# Start playback
player.play()
```

## Usage Examples

### Basic Sound Playback

> **Note:** A `Sound` on its own only manages PCM data and playback state. To actually hear audio, you need a `SoundPlayer` with an audio layer (see [Sound Player with Multiple Layers](#sound-player-with-multiple-layers)).

```python
from sound_player import Sound, SoundPlayer

player = SoundPlayer()
player.create_audio_layer("music", concurrency=1)

sound = Sound("music.ogg")
player["music"].enqueue(sound)

player.play()       # Start audio output
player.pause()      # Pause playback
player.play()       # Resume playback
player.stop()       # Stop and reset
```

### Sound with Loop and Volume

```python
from sound_player import Sound, SoundPlayer

player = SoundPlayer()
player.create_audio_layer("music", concurrency=1)

sound = Sound("music.ogg")
sound.set_loop(3)      # Play 3 times (use -1 for infinite)
sound.set_volume(0.8)   # Set volume to 80% (0.0-1.0 range)

player["music"].enqueue(sound)
player.play()
```

### Audio Layer with Concurrency

```python
from sound_player import AudioLayer, Sound

# Allow up to 3 sounds playing at once
layer = AudioLayer(concurrency=3, volume=0.8)

layer.enqueue(Sound("music.ogg"))
layer.enqueue(Sound("coin.wav"))
layer.enqueue(Sound("explosion.wav"))
layer.enqueue(Sound("powerup.wav"))  # Will wait for a free slot

layer.play()
```

### Sound Player with Multiple Layers

```python
from sound_player import SoundPlayer, Sound

player = SoundPlayer()

# Create different audio layers
player.create_audio_layer("music", concurrency=1, volume=0.6)
player.create_audio_layer("sfx", concurrency=4, volume=1.0)
player.create_audio_layer("voice", concurrency=1, volume=0.8)

# Add sounds to each layer
player["music"].enqueue(Sound("background.ogg"))
player["sfx"].enqueue(Sound("jump.wav"))
player["voice"].enqueue(Sound("dialogue.wav"))

# Control individual layers
player.play("sfx")      # Play only SFX
player.pause("music")   # Pause music
player.stop("voice")    # Stop voice layer

# Or control all at once
player.play()           # Play all layers
player.stop()           # Stop all layers
```

### Volume Hierarchy

The library supports volume control at three levels (all using 0.0-1.0 float range):

```python
from sound_player import AudioConfig, AudioLayer, Sound, SoundPlayer

player = SoundPlayer()
player.set_volume(0.7)  # Master volume: 0.0 to 1.0

layer = AudioLayer(volume=0.8)     # Layer volume: 0.0 to 1.0
sound = Sound("music.ogg")
sound.set_volume(0.5)              # Sound volume: 0.0 to 1.0

# Final volume = sound_vol × layer_vol × master_vol
# Final = 0.5 × 0.8 × 0.7 = 0.28 (28%)
```

### Custom Audio Configuration

```python
from sound_player import AudioConfig, SoundPlayer, Sound

config = AudioConfig(
    sample_rate=48000,    # Sample rate in Hz
    channels=2,           # 1=mono, 2=stereo
    buffer_size=1024,     # Buffer size in samples
)

player = SoundPlayer(config=config)
player.create_audio_layer("music", config=config)
player["music"].enqueue(Sound("music.ogg"))
player.play()
```

### Fade Effects

```python
from sound_player import Sound, SoundPlayer

player = SoundPlayer()
player.create_audio_layer("music", concurrency=1)

sound = Sound("music.ogg")
sound.fade_in(2.0)     # Fade in over 2 seconds

player["music"].enqueue(sound)
player.play()

# Later...
sound.fade_out(3.0)    # Fade out over 3 seconds (auto-stops when done)
```

### Replace Mode

When `replace=True`, adding sounds beyond the concurrency limit will stop the oldest sounds:

```python
from sound_player import AudioLayer, Sound

layer = AudioLayer(concurrency=2, replace=True)

layer.enqueue(Sound("music1.ogg"))
layer.enqueue(Sound("sfx1.wav"))
layer.enqueue(Sound("sfx2.wav"))  # Stops music1.ogg
layer.enqueue(Sound("sfx3.wav"))  # Stops sfx1.wav

layer.play()
```

### Crossfade with Replace Mode

When `replace=True` with a `fade_out_duration`, replaced sounds crossfade smoothly:

```python
from sound_player import AudioLayer, Sound

layer = AudioLayer(concurrency=1, replace=True, fade_in_duration=1.0, fade_out_duration=2.0)

layer.enqueue(Sound("track1.ogg"))
layer.play()
# When track2 is enqueued, track1 fades out over 2s while track2 fades in over 1s
layer.enqueue(Sound("track2.ogg"))
```

## Architecture

The library uses a mixin-based architecture with the following key components:

### Core Classes

- **`StatusMixin`** - Manages playback status (STOPPED, PLAYING, PAUSED) with thread-safe `play()`, `pause()`, `stop()` methods
- **`VolumeMixin`** - Provides volume control with clamping (0.0-1.0) and thread-safe `set_volume()`, `get_volume()` methods
- **`FadeMixin`** - Sample-accurate fade-in/fade-out with configurable curves (linear, exponential, logarithmic, S-curve)
- **`LockMixin`** - Provides thread-safe RLock for concurrent operations
- **`AudioConfigMixin`** - Manages audio configuration (sample rate, channels, buffer size, etc.)

### Main Classes

- **`BaseSound`** - Base class for all sounds with PCM buffer interface
- **`AudioLayer`** - Manages sound queues with mixing and concurrency control
- **`BaseSoundPlayer`** - Abstract base class for platform-specific audio output
- **`AudioMixer`** - Mixes multiple audio streams with volume control

### Volume Hierarchy

```
sound_data × sound_volume × layer_volume × player_volume = final_output
```

Each level uses the 0.0-1.0 float range for consistent computations.

## API Reference

### SoundPlayer

Main class for managing multiple audio layers.

| Method | Description |
|--------|-------------|
| `create_audio_layer(id, force=False, **kwargs)` | Create a new audio layer |
| `enqueue(sound, layer_id)` | Add sound to a layer |
| `play(layer_id=None)` | Start playback (all layers or specific) |
| `pause(layer_id=None)` | Pause playback |
| `stop(layer_id=None)` | Stop playback |
| `set_volume(volume)` | Set master volume (0.0-1.0) |
| `get_volume()` | Get master volume (0.0-1.0) |
| `clear(layer_id=None)` | Clear queues |

### AudioLayer

Manages a queue of sounds with mixing.

| Constructor | Description |
|------------|-------------|
| `AudioLayer(concurrency=1, replace=False, loop=None, fade_in_duration=None, fade_out_duration=None, fade_curve=None, volume=1.0, config=None)` | Create audio layer |

| Method | Description |
|--------|-------------|
| `enqueue(sound, fade_in=None, fade_out=None)` | Add sound to waiting queue |
| `play()` / `pause()` / `stop()` | Control playback |
| `clear()` | Clear all queues |
| `set_concurrency(n)` | Set max concurrent sounds |
| `set_replace(bool)` | Enable/disable replace mode |
| `set_loop(n)` | Set default loop count (-1=infinite) |
| `set_volume(v)` | Set layer volume (0.0-1.0) |
| `set_fade_in_duration(d)` | Set default fade-in duration for enqueued sounds |
| `set_fade_out_duration(d)` | Set default fade-out duration for enqueued sounds |
| `set_fade_curve(curve)` | Set default fade curve for enqueued sounds |

### Sound

Represents a single sound file.

| Method | Description |
|--------|-------------|
| `play()` / `pause()` / `stop()` | Control playback |
| `wait(timeout=None)` | Wait for playback to finish |
| `set_loop(n)` | Set loop count (-1=infinite) |
| `set_volume(v)` | Set volume (0.0-1.0) |
| `fade_in(duration)` | Fade in over duration seconds |
| `fade_out(duration)` | Fade out over duration seconds |
| `seek(position)` | Seek to position (seconds) |

### AudioConfig

Configuration for audio format.

| Parameter | Description |
|-----------|-------------|
| `sample_rate` | Sample rate in Hz (default: 44100) |
| `channels` | Number of channels (1=mono, 2=stereo) |
| `sample_width` | Bytes per sample (2=int16, 4=int32) |
| `buffer_size` | Samples per buffer (default: 1024) |
| `dtype` | NumPy dtype (default: np.int16) |

## Android

### Buildozer / python-for-android

Add the following to your `buildozer.spec` requirements:

```
requirements = ..., sound-player[android]~=1.0
```

The `[android]` extra pulls in `pyjnius` and `android`; `numpy` and
`krozark-current-platform` are pulled in automatically as hard dependencies.
`soundfile` and `sounddevice` are **not** needed — the library uses
`MediaExtractor` / `MediaCodec` / `AudioTrack` directly via `pyjnius`.

### Choosing the Android decoder

Two decoder implementations are available.  Select one at **runtime** by
setting the `SOUND_PLAYER_ANDROID_DECODER` environment variable **before the
first import** of `sound_player`:

```python
import os
os.environ["SOUND_PLAYER_ANDROID_DECODER"] = "sync"   # default
# or
os.environ["SOUND_PLAYER_ANDROID_DECODER"] = "async"

import sound_player
```

| Value | Class | How it works |
|-------|-------|--------------|
| `sync` *(default)* | `AndroidPCMSound` | Background Python thread polls `dequeueInputBuffer` / `dequeueOutputBuffer`. Backpressure pauses the thread when the PCM buffer holds > 2 s of audio. Simple and easy to debug. |
| `async` | `AndroidPCMSoundAsync` | Registers a `MediaCodec.Callback`; Android's internal thread calls into Python when buffers are ready. Event-driven, no polling. |

**Recommendation:** use `sync` (the default) for most cases, especially when
playing many sounds concurrently (~10+).  The `async` mode is provided for
experimentation; its backpressure currently blocks MediaCodec's internal
thread, which is an anti-pattern at scale.

## Dependencies

**Required:**
- `numpy>=1.24` - Audio mixing
- `krozark-current-platform` - Platform detection

**Optional (Linux/Windows):**
- `sounddevice~=0.4` - Audio output
- `soundfile~=0.12` - Audio file decoding

Install both with:
```bash
pip install sound-player[linux]   # Linux
pip install sound-player[windows] # Windows
```

**Android:**
- `pyjnius`, `android` - Android platform APIs (already available in python-for-android environments)

```bash
pip install sound-player[android]
```

## License

BSD 2-Clause

## Author

Maxime Barbier
