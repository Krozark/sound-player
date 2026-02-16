# sound-player

A Python library for playing multiple sound files with professional real-time audio mixing support. Perfect for games and applications that need concurrent audio playback with multiple layers.

## Features

- **Real-time Audio Mixing** - Mix multiple audio streams simultaneously using NumPy
- **Multiple Audio Layers** - Organize sounds into independent layers (music, SFX, voice, etc.)
- **Volume Control** - Fine-grained volume at sound, layer, and master levels
- **Concurrent Playback** - Configure how many sounds can play simultaneously per layer
- **Loop Control** - Set sounds to loop infinitely or a specific number of times
- **Replace Mode** - Optionally stop oldest sounds when concurrency limit is reached
- **Cross-Platform** - Support for Linux, Android (Windows/macOS/iOS planned)
- **PCM Buffer Interface** - Integrate with any audio output library

## Installation

```bash
pip install sound-player
```

For Linux audio output support:
```bash
pip install sound-player[linux]
```

## Supported Platforms

- [x] Linux
- [x] Android
- [ ] Windows (planned)
- [ ] macOS (planned)
- [ ] iOS (planned)

## Quick Start

```python
from sound_player import Sound, SoundPlayer

# Create a player with multiple audio layers
player = SoundPlayer()

# Create a music layer with background music
player.create_audio_layer("music", concurrency=1, volume=70)
player["music"].enqueue(Sound("background_music.ogg"))

# Create a sound effects layer
player.create_audio_layer("sfx", concurrency=3, volume=100)
player["sfx"].enqueue(Sound("coin.wav"))

# Start playback
player.play()
```

## Usage Examples

### Basic Sound Playback

```python
from sound_player import Sound

sound = Sound("music.ogg")

sound.play()    # Start playback
sound.pause()   # Pause playback
sound.stop()    # Stop and reset
sound.wait()    # Wait for playback to finish
```

### Sound with Loop and Volume

```python
from sound_player import Sound

sound = Sound("music.ogg")
sound.set_loop(3)      # Play 3 times (use -1 for infinite)
sound.set_volume(80)   # Set volume to 80%

sound.play()
sound.wait()
```

### Audio Layer with Concurrency

```python
from sound_player import AudioLayer, Sound

# Allow up to 3 sounds playing at once
layer = AudioLayer(concurrency=3, volume=80)

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
player.create_audio_layer("music", concurrency=1, volume=60)
player.create_audio_layer("sfx", concurrency=4, volume=100)
player.create_audio_layer("voice", concurrency=1, volume=80)

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

The library supports volume control at three levels:

```python
from sound_player import AudioConfig, AudioLayer, Sound, SoundPlayer

player = SoundPlayer()
player.set_master_volume(0.7)  # Master volume: 0.0 to 1.0

layer = AudioLayer(volume=80)     # Layer volume: 0 to 100
sound = Sound("music.ogg")
sound.set_volume(50)              # Sound volume: 0 to 100

# Final volume = sound_vol × layer_vol × master_vol
# Final = 0.50 × 0.80 × 0.70 = 0.28 (28%)
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

## API Reference

### SoundPlayer

Main class for managing multiple audio layers.

| Method | Description |
|--------|-------------|
| `create_audio_layer(id, **kwargs)` | Create a new audio layer |
| `enqueue(sound, layer_id)` | Add sound to a layer |
| `play(layer_id=None)` | Start playback (all layers or specific) |
| `pause(layer_id=None)` | Pause playback |
| `stop(layer_id=None)` | Stop playback |
| `set_master_volume(volume)` | Set master volume (0.0-1.0) |
| `clear(layer_id=None)` | Clear queues |

### AudioLayer

Manages a queue of sounds with mixing.

| Constructor | Description |
|------------|-------------|
| `AudioLayer(concurrency=1, replace=False, loop=None, volume=100, config=None)` | Create audio layer |

| Method | Description |
|--------|-------------|
| `enqueue(sound)` | Add sound to waiting queue |
| `play()` / `pause()` / `stop()` | Control playback |
| `clear()` | Clear all queues |
| `set_concurrency(n)` | Set max concurrent sounds |
| `set_replace(bool)` | Enable/disable replace mode |
| `set_loop(n)` | Set default loop count (-1=infinite) |
| `set_volume(n)` | Set layer volume (0-100) |

### Sound

Represents a single sound file.

| Method | Description |
|--------|-------------|
| `play()` / `pause()` / `stop()` | Control playback |
| `wait(timeout=None)` | Wait for playback to finish |
| `set_loop(n)` | Set loop count (-1=infinite) |
| `set_volume(n)` | Set volume (0-100) |
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

## Dependencies

**Required:**
- `numpy>=1.24` - Audio mixing
- `soundfile~=0.12` - Audio file decoding
- `krozark-current-platform` - Platform detection

**Optional (Linux):**
- `sounddevice~=0.4` - Audio output (install with `[linux]` extra)

**Android:**
- `jnius`, `android` - Available on Android platform

## License

BSD 2-Clause

## Author

Maxime Barbier
