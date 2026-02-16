"""Example usage of the sound-player library with audio mixing support.

This example demonstrates:
1. Basic sound playback with play/pause/stop controls
2. AudioLayer with concurrent sound playback and mixing
3. SoundPlayer with multiple audio layers
4. Volume controls at sound, layer, and master levels
5. Loop functionality
"""

import argparse
import logging
import time

from sound_player import AudioConfig, AudioLayer, Sound, SoundPlayer


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

    sound = Sound("data/music.ogg")

    print("Playing sound...")
    sound.play()
    time.sleep(3)

    print("Pausing sound...")
    sound.pause()
    time.sleep(2)

    print("Resuming sound...")
    sound.play()
    time.sleep(3)

    print("Stopping sound...")
    sound.stop()
    time.sleep(1)


def test_audio_layer_concurrency():
    """Test AudioLayer with concurrent sound playback."""
    print("\n" + "=" * 50)
    print("Test 2: AudioLayer with Concurrency")
    print("=" * 50)

    # Create an AudioLayer that allows up to 3 concurrent sounds
    layer = AudioLayer(concurrency=3, replace=False)

    # Enqueue multiple sounds
    layer.enqueue(Sound("data/coin.wav"))
    layer.enqueue(Sound("data/music.ogg"))
    layer.enqueue(Sound("data/coin.wav"))
    layer.enqueue(Sound("data/coin.wav"))

    print("Playing layer with 3 concurrent sounds...")
    layer.play()
    time.sleep(5)

    print("Stopping layer...")
    layer.stop()
    time.sleep(1)


def test_audio_layer_replace_mode():
    """Test AudioLayer with replace mode."""
    print("\n" + "=" * 50)
    print("Test 3: AudioLayer with Replace Mode")
    print("=" * 50)

    # Create an AudioLayer with replace mode
    # When limit is exceeded, oldest sounds are stopped
    layer = AudioLayer(concurrency=2, replace=True)

    layer.enqueue(Sound("data/music.ogg"))
    layer.enqueue(Sound("data/coin.wav"))

    print("Playing with 2 sounds...")
    layer.play()
    time.sleep(2)

    # Adding more sounds will replace the oldest ones
    print("Adding more sounds (replace mode)...")
    layer.enqueue(Sound("data/coin.wav"))
    layer.enqueue(Sound("data/coin.wav"))
    time.sleep(3)

    layer.stop()
    time.sleep(1)


def test_sound_player_multiple_layers():
    """Test SoundPlayer with multiple audio layers."""
    print("\n" + "=" * 50)
    print("Test 4: SoundPlayer with Multiple Layers")
    print("=" * 50)

    player = SoundPlayer()

    # Create a music layer with background music
    player.create_audio_layer("music", concurrency=1, volume=0.7)
    player["music"].enqueue(Sound("data/music.ogg"))

    # Create a sound effects layer
    player.create_audio_layer("sfx", concurrency=1, volume=1.0)
    player["sfx"].enqueue(Sound("data/coin.wav"))
    player["sfx"].enqueue(Sound("data/coin.wav"))

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
    player.create_audio_layer("music", volume=1)  # 100% volume

    player["music"].enqueue(Sound("data/music.ogg"))

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

    # Test sound-level looping
    sound = Sound("data/coin.wav")
    sound.set_loop(3)  # Play 3 times

    print("Playing sound 3 times...")
    sound.play()
    sound.wait()
    time.sleep(1)

    # Test layer-level looping
    layer = AudioLayer(loop=2)  # All sounds play 2 times by default
    layer.enqueue(Sound("data/coin.wav"))
    layer.enqueue(Sound("data/coin.wav"))

    print("Playing layer with loop=2...")
    layer.play()
    time.sleep(5)

    layer.stop()
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
    player.create_audio_layer("music", config=config, volume=0.8)
    player["music"].enqueue(Sound("data/music.ogg"))

    print(f"Playing with config: {config.sample_rate}Hz, {config.channels}ch...")
    player.play()
    time.sleep(3)

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

    # test_basic_sound()
    # test_audio_layer_concurrency()
    # test_audio_layer_replace_mode()
    # test_sound_player_multiple_layers()
    # test_volume_controls()
    test_loop_functionality()
    # test_audio_configuration()

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
