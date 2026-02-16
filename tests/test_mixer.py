"""Tests for the AudioMixer class."""

import threading
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from sound_player.audio_config import AudioConfig
from sound_player.common import STATUS
from sound_player.mixer import AudioMixer


@pytest.fixture
def audio_config():
    """Create a test audio configuration."""
    return AudioConfig(
        sample_rate=44100,
        channels=2,
        sample_width=2,
        buffer_size=512,
    )


@pytest.fixture
def mixer(audio_config):
    """Create a test mixer."""
    return AudioMixer(audio_config, volume=1.0)


class MockSound:
    """Mock sound class for testing."""

    def __init__(self, data, status=STATUS.PLAYING, volume=100):
        self._data = data
        self._status = status
        self._volume = volume
        self._loop = None

    def get_next_chunk(self, size):
        if self._status != STATUS.PLAYING:
            return None
        if len(self._data) == 0:
            return None
        if len(self._data) < size:
            result = np.pad(self._data, ((0, size - len(self._data)), (0, 0)), mode="constant")
            self._data = np.array([])
        else:
            result = self._data[:size]
            self._data = self._data[size:]
        return result

    def get_sample_rate(self):
        return 44100

    def get_channels(self):
        return 2

    def get_audio_config(self):
        return AudioConfig()

    def status(self):
        return self._status

    def play(self):
        self._status = STATUS.PLAYING

    def pause(self):
        self._status = STATUS.PAUSED

    def stop(self):
        self._status = STATUS.STOPPED


class TestAudioMixer:
    """Test suite for AudioMixer."""

    def test_mixer_initialization(self, mixer, audio_config):
        """Test mixer initialization."""
        assert mixer.config is audio_config
        assert mixer.volume == 1.0
        assert mixer.sound_count == 0

    def test_set_volume(self, mixer):
        """Test setting volume."""
        mixer.set_volume(0.5)
        assert mixer.volume == 0.5

        # Test clamping
        mixer.set_volume(1.5)
        assert mixer.volume == 1.0

        mixer.set_volume(-0.5)
        assert mixer.volume == 0.0

    def test_add_sound(self, mixer):
        """Test adding a sound to the mixer."""
        sound = MagicMock()
        sound.status.return_value = STATUS.STOPPED

        mixer.add_sound(sound)
        assert mixer.sound_count == 1

    def test_add_duplicate_sound(self, mixer):
        """Test that duplicate sounds are not added."""
        sound = MagicMock()
        sound.status.return_value = STATUS.PLAYING

        mixer.add_sound(sound)
        mixer.add_sound(sound)
        assert mixer.sound_count == 1

    def test_remove_sound(self, mixer):
        """Test removing a sound from the mixer."""
        sound = MagicMock()
        sound.status.return_value = STATUS.PLAYING

        mixer.add_sound(sound)
        assert mixer.sound_count == 1

        mixer.remove_sound(sound)
        assert mixer.sound_count == 0

    def test_remove_all_sounds(self, mixer):
        """Test removing all sounds."""
        sound1 = MagicMock()
        sound2 = MagicMock()
        sound1.status.return_value = STATUS.PLAYING
        sound2.status.return_value = STATUS.PLAYING

        mixer.add_sound(sound1)
        mixer.add_sound(sound2)
        assert mixer.sound_count == 2

        mixer.remove_all_sounds()
        assert mixer.sound_count == 0

    def test_get_active_sounds(self, mixer):
        """Test getting only active sounds."""
        playing = MagicMock()
        playing.status.return_value = STATUS.PLAYING
        stopped = MagicMock()
        stopped.status.return_value = STATUS.STOPPED

        mixer.add_sound(playing)
        mixer.add_sound(stopped)

        active = mixer.get_active_sounds()
        assert len(active) == 1
        assert active[0] is playing

    def test_silence_when_no_sounds(self, mixer):
        """Test that silence is returned when no sounds."""
        chunk = mixer.get_next_chunk()
        assert chunk is not None
        assert chunk.shape == (mixer.config.buffer_size, mixer.config.channels)
        assert np.all(chunk == 0)

    def test_single_sound_passthrough(self, mixer, audio_config):
        """Test that a single sound passes through unchanged (except for volume)."""
        data = np.random.randint(-1000, 1000, size=(audio_config.buffer_size, 2), dtype=np.int16)
        sound = MockSound(data.copy())

        mixer.add_sound(sound)
        chunk = mixer.get_next_chunk()

        assert chunk is not None
        assert chunk.shape == (audio_config.buffer_size, 2)
        # With volume 1.0, output should match input
        # Allow some tolerance for float conversion
        np.testing.assert_array_almost_equal(chunk, data, decimal=0)

    def test_multiple_sounds_mixing(self, mixer, audio_config):
        """Test that multiple sounds are mixed together."""
        data1 = np.full((audio_config.buffer_size, 2), 1000, dtype=np.int16)
        data2 = np.full((audio_config.buffer_size, 2), 2000, dtype=np.int16)

        sound1 = MockSound(data1)
        sound2 = MockSound(data2)

        mixer.add_sound(sound1)
        mixer.add_sound(sound2)
        chunk = mixer.get_next_chunk()

        assert chunk is not None
        # With both sounds, we should get 1000 + 2000 = 3000
        assert np.all(chunk == 3000)

    def test_volume_application(self, mixer, audio_config):
        """Test that sound volume is applied correctly."""
        data = np.full((audio_config.buffer_size, 2), 1000, dtype=np.int16)
        sound = MockSound(data, volume=50)  # 50% volume

        mixer.add_sound(sound)
        chunk = mixer.get_next_chunk()

        assert chunk is not None
        # 1000 * 0.5 = 500
        assert np.all(chunk == 500)

    def test_master_volume(self, mixer, audio_config):
        """Test that master volume is applied."""
        data = np.full((audio_config.buffer_size, 2), 1000, dtype=np.int16)
        sound = MockSound(data)

        mixer.set_volume(0.5)
        mixer.add_sound(sound)
        chunk = mixer.get_next_chunk()

        assert chunk is not None
        # 1000 * 0.5 (master) = 500
        assert np.all(chunk == 500)

    def test_clipping_prevention(self, mixer, audio_config):
        """Test that clipping is prevented."""
        # Create data that will overflow when mixed
        max_val = audio_config.max_sample_value
        data = np.full((audio_config.buffer_size, 2), max_val, dtype=np.int16)

        sound1 = MockSound(data.copy())
        sound2 = MockSound(data.copy())

        mixer.add_sound(sound1)
        mixer.add_sound(sound2)
        chunk = mixer.get_next_chunk()

        assert chunk is not None
        # Result should be clipped to max value
        assert np.all(chunk <= max_val)

    def test_mono_to_stereo_conversion(self, mixer, audio_config):
        """Test conversion from mono to stereo."""
        data = np.full((512, 1), 1000, dtype=np.int16)

        sound = MockSound(data)
        sound.get_channels = lambda: 1

        mixer.add_sound(sound)
        chunk = mixer.get_next_chunk()

        assert chunk is not None
        assert chunk.shape == (512, 2)
        # Mono should be duplicated to both channels
        assert np.all(chunk == 1000)

    def test_stereo_to_mono_conversion(self, mixer, audio_config):
        """Test conversion from stereo to mono."""
        mono_config = AudioConfig(sample_rate=44100, channels=1, buffer_size=512)
        mixer_mono = AudioMixer(mono_config)

        data = np.full((512, 2), 1000, dtype=np.int16)
        sound = MockSound(data)
        sound.get_channels = lambda: 2

        mixer_mono.add_sound(sound)
        chunk = mixer_mono.get_next_chunk()

        assert chunk is not None
        assert chunk.shape == (512, 1)
        # Stereo should be averaged to mono
        assert np.all(chunk == 1000)

    def test_chunk_length_adjustment(self, mixer, audio_config):
        """Test that chunks are adjusted to correct length."""
        # Create data that's shorter than buffer
        data = np.full((256, 2), 1000, dtype=np.int16)
        sound = MockSound(data)

        mixer.add_sound(sound)
        chunk = mixer.get_next_chunk()

        assert chunk is not None
        assert chunk.shape == (512, 2)
        # Should be padded with zeros
        assert np.all(chunk[:256] == 1000)
        assert np.all(chunk[256:] == 0)

    def test_thread_safety(self, mixer, audio_config):
        """Test that mixer is thread-safe."""
        data = np.full((audio_config.buffer_size, 2), 1000, dtype=np.int16)
        sounds = [MockSound(data.copy()) for _ in range(10)]

        errors = []
        results = []

        def add_sounds():
            try:
                for sound in sounds:
                    mixer.add_sound(sound)
                    results.append(mixer.sound_count)
            except Exception as e:
                errors.append(e)

        def remove_sounds():
            try:
                time.sleep(0.01)
                for sound in sounds[:5]:
                    mixer.remove_sound(sound)
                    results.append(mixer.sound_count)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=add_sounds)
        t2 = threading.Thread(target=remove_sounds)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0
        # Final count should be 5 (10 added - 5 removed)
        assert mixer.sound_count == 5
