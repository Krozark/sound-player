"""Example usage of the sound-player library with audio mixing support.

This example demonstrates:
1. Basic sound playback with play/pause/stop controls
2. AudioLayer with concurrent sound playback and mixing
3. SoundPlayer with multiple audio layers
4. Volume controls at sound, layer, and master levels
5. Loop functionality
6. Fade-in/fade-out and crossfade effects
"""

import argparse
import logging
import time

from sound_player import Sound, SoundPlayer
from sound_player.core import AudioConfig, FadeCurve


def setup_logging(verbosity: int = 0):
    """Setup logging for the example.

    Args:
        verbosity: Logging level (0=WARNING, 1=INFO, 2=DEBUG)
    """
    level = logging.WARNING
    if verbosity >= 1:
        level = logging.INFO
    if verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def test_basic_sound():
    """Test basic sound playback with play/pause/stop controls."""
    print("=" * 50)
    print("Test 1: Basic Sound Playback")
    print("=" * 50)

    player = SoundPlayer()
    layer = player.create_audio_layer("main", concurrency=1)

    sound = Sound("data/music.ogg")
    layer.enqueue(sound)

    print("Playing sound...")
    player.play()
    time.sleep(3)

    print("Pausing sound...")
    player.pause()
    time.sleep(2)

    print("Resuming sound...")
    player.play()
    time.sleep(3)

    print("Stopping sound...")
    player.stop()
    time.sleep(1)


def test_change_sound_volume():
    """Test basic sound playback with play/pause/stop controls."""
    print("=" * 50)
    print("Test 1: Basic Sound Playback")
    print("=" * 50)

    player = SoundPlayer()
    layer = player.create_audio_layer("main", concurrency=1)

    sound = Sound("data/music.ogg")
    layer.enqueue(sound)

    print("Playing sound...")
    player.play()
    time.sleep(3)

    print("setting volume to 50%...")
    sound.set_volume(0.5)
    time.sleep(3)

    print("setting volume to 20%...")
    sound.set_volume(0.2)
    time.sleep(3)

    print("setting volume to 100%...")
    sound.set_volume(1.0)
    time.sleep(3)

    print("Stopping sound...")
    player.stop()
    time.sleep(1)


def test_change_layer_volume():
    print("=" * 50)
    print("Test 1: Layer volume Change")
    print("=" * 50)

    player = SoundPlayer()
    layer = player.create_audio_layer("main", concurrency=1)
    sound = Sound("data/music.ogg")
    layer.enqueue(sound)

    print("Playing sound...")
    player.play()
    time.sleep(3)

    print("setting volume to 50%...")
    layer.set_volume(0.5)
    time.sleep(3)

    print("setting volume to 20%...")
    layer.set_volume(0.2)
    time.sleep(3)

    print("setting volume to 100%...")
    layer.set_volume(1.0)
    time.sleep(3)

    print("Stopping sound...")
    player.stop()
    time.sleep(1)


def test_audio_layer_concurrency():
    """Test AudioLayer with concurrent sound playback."""
    print("\n" + "=" * 50)
    print("Test 2: AudioLayer with Concurrency")
    print("=" * 50)

    player = SoundPlayer()

    # Create an AudioLayer that allows up to 2 concurrent sounds
    layer = player.create_audio_layer("main", concurrency=2, replace=False)

    # Enqueue multiple sounds
    layer.enqueue(Sound("data/coin.wav"))
    layer.enqueue(Sound("data/music.ogg"))
    layer.enqueue(Sound("data/coin.wav"))
    layer.enqueue(Sound("data/coin.wav"))

    print("Playing layer with 2 concurrent sounds...")
    player.play()
    time.sleep(5)

    print("Stopping layer...")
    player.stop()
    time.sleep(1)


def test_audio_layer_replace_mode():
    """Test AudioLayer with replace mode."""
    print("\n" + "=" * 50)
    print("Test 3: AudioLayer with Replace Mode")
    print("=" * 50)

    player = SoundPlayer()

    # Create an AudioLayer with replace mode
    # When limit is exceeded, oldest sounds are stopped
    layer = player.create_audio_layer("main", concurrency=2, replace=True)

    layer.enqueue(Sound("data/music.ogg"))
    layer.enqueue(Sound("data/coin.wav"))

    print("Playing with 2 sounds...")
    player.play()
    time.sleep(2)

    # Adding more sounds will replace the oldest ones
    print("Adding more sounds (replace mode)...")
    layer.enqueue(Sound("data/coin.wav"))
    layer.enqueue(Sound("data/coin.wav"))
    time.sleep(3)

    player.stop()
    time.sleep(1)


def test_sound_player_multiple_layers():
    """Test SoundPlayer with multiple audio layers."""
    print("\n" + "=" * 50)
    print("Test 4: SoundPlayer with Multiple Layers")
    print("=" * 50)

    player = SoundPlayer()

    # Create a music layer with background music
    layer = player.create_audio_layer("music", concurrency=1, volume=0.7)
    layer.enqueue(Sound("data/music.ogg"))

    # Create a sound effects layer
    layer2 = player.create_audio_layer("sfx", concurrency=1, volume=1.0)
    layer2.enqueue(Sound("data/coin.wav"))
    layer2.enqueue(Sound("data/coin.wav"))

    print("Playing all layers...")
    player.play()
    time.sleep(5)

    # Pause only the music
    print("Pausing music layer...")
    player.pause("music")
    time.sleep(3)

    # Resume music
    print("Resuming music layer...")
    player.play("music")
    time.sleep(3)

    player.stop()
    time.sleep(1)


def test_volume_controls():
    """Test volume controls at different levels."""
    print("\n" + "=" * 50)
    print("Test 5: Volume Controls")
    print("=" * 50)

    player = SoundPlayer()

    # Create layers with different volumes
    layer = player.create_audio_layer("music", volume=1.0)  # 100% volume

    layer.enqueue(Sound("data/music.ogg"))

    print("Playing with music at 100% volume...")
    player.play()
    time.sleep(3)

    # Change layer volume
    print("setting volume to 50%...")
    player.set_volume(0.5)
    time.sleep(2)

    # Change master volume
    print("Setting volume to 20%...")
    player.set_volume(0.2)
    time.sleep(2)

    player.stop()
    time.sleep(1)


def test_loop_functionality():
    """Test loop functionality at sound and layer levels."""
    print("\n" + "=" * 50)
    print("Test 6: Loop Functionality")
    print("=" * 50)

    # Test sound-level looping with a player
    player = SoundPlayer()
    layer = player.create_audio_layer("test", concurrency=1)

    sound = Sound("data/coin.wav")
    sound.set_loop(3)  # Play 3 times
    layer.enqueue(sound)

    print("Playing sound 3 times...")
    player.play()
    time.sleep(2)  # Wait for sound to play
    player.stop()
    time.sleep(1)

    # Delete the first layer and test layer-level looping
    player.delete_audio_layer("test")
    layer2 = player.create_audio_layer("loop_test", loop=2, concurrency=1)
    layer2.enqueue(Sound("data/coin.wav"))
    layer2.enqueue(Sound("data/coin.wav"))

    print("Playing layer with loop=2...")
    player.play()
    time.sleep(3)

    player.stop()
    time.sleep(1)


def test_audio_configuration():
    """Test custom audio configuration."""
    print("\n" + "=" * 50)
    print("Test 7: Custom Audio Configuration")
    print("=" * 50)

    # Create a custom audio configuration
    config = AudioConfig(
        sample_rate=48000,
        channels=2,
        buffer_size=1024,
    )

    player = SoundPlayer(config=config)
    layer = player.create_audio_layer("music", config=config, volume=0.8)
    layer.enqueue(Sound("data/music.ogg"))

    print(f"Playing with config: {config.sample_rate}Hz, {config.channels}ch...")
    player.play()
    time.sleep(5)

    player.stop()
    time.sleep(1)


def test_manual_fade():
    """Test manual fade-in/fade-out effects with different curves."""
    print("\n" + "=" * 50)
    print("Test 8: Manual Fade Effects")
    print("=" * 50)

    player = SoundPlayer()
    layer = player.create_audio_layer("music", concurrency=1)
    player.play()

    # Create a single sound that we'll reuse
    music = Sound("data/music.ogg")
    layer.enqueue(music)

    # Test fade-in with linear curve
    print("Testing fade-in with LINEAR curve...")
    layer.set_fade_curve(FadeCurve.LINEAR)
    music.fade_in(duration=4.0)
    time.sleep(8)

    # Test fade-in with exponential curve
    print("\nTesting fade-in with EXPONENTIAL curve...")
    layer.set_fade_curve(FadeCurve.EXPONENTIAL)
    music.fade_in(duration=4.0)
    time.sleep(8)

    # Test fade-in with log
    print("\nTesting fade-in with LOGARITHMIC...")
    layer.set_fade_curve(FadeCurve.LOGARITHMIC)
    music.fade_in(duration=4.0)
    time.sleep(8)

    # Test fade-in with s-curve
    print("\nTesting fade-in with S-CURVE...")
    layer.set_fade_curve(FadeCurve.SCURVE)
    music.fade_in(duration=4.0)
    time.sleep(8)

    # Test fade-out
    print("\nTesting fade-out...")
    music.fade_out(duration=3.0)
    time.sleep(4)

    player.stop()
    time.sleep(1)


def test_crossfade():
    """Test crossfade between ambient sounds."""
    print("\n" + "=" * 50)
    print("Test 9: Crossfade Between Ambience Sounds")
    print("=" * 50)

    player = SoundPlayer()

    # Create an ambience layer with crossfade enabled
    # When a new sound is enqueued, the old one fades out while the new one fades in
    layer = player.create_audio_layer(
        "ambience",
        concurrency=1,
        replace=True,
        fade_in_duration=4.0,  # 4-second crossfade
        fade_out_duration=4.0,  # 4-second crossfade
        volume=0.8,
    )

    print("Playing music ambience...")
    night = Sound("data/music.ogg")
    layer.enqueue(night)
    player.play()
    time.sleep(10)

    print("Crossfading to dark ship ambience (4 seconds)...")
    print("(The night sound fades out while the ship sound fades in)")
    dark_ship = Sound("data/dark-ship.wav")
    layer.enqueue(dark_ship)
    time.sleep(10)

    print("Crossfading back to night ambience (4 seconds)...")
    night2 = Sound("data/night-ambience.wav")
    layer.enqueue(night2)
    time.sleep(10)

    print("Fading out over 3 seconds...")
    night2.fade_out(duration=3.0)
    time.sleep(6)

    player.stop()
    time.sleep(1)


def main(verbosity: int = 0):
    """Run all examples.

    Args:
        verbosity: Logging level (0=WARNING, 1=INFO, 2=DEBUG)
    """
    setup_logging(verbosity)
    print("\n" + "=" * 50)
    print("SOUND PLAYER LIBRARY - EXAMPLES")
    print("=" * 50)

    test_basic_sound()
    test_change_layer_volume()
    test_change_sound_volume()
    test_audio_layer_concurrency()
    test_audio_layer_replace_mode()
    test_sound_player_multiple_layers()
    test_volume_controls()
    test_loop_functionality()
    test_audio_configuration()
    test_manual_fade()
    test_crossfade()

    print("\n" + "=" * 50)
    print("All examples completed!")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sound Player Library - Examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        type=int,
        default=0,
        choices=[0, 1, 2],
        help="Logging verbosity: 0=WARNING (default), 1=INFO, 2=DEBUG",
    )

    args = parser.parse_args()
    main(args.verbosity)
