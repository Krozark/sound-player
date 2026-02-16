"""Tests for the LinuxPCMSound class."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sound_player.core.audio_config import AudioConfig
from sound_player.core.state import STATUS
from sound_player.platform.linux import LinuxPCMSound


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
def mock_audio_file(tmp_path):
    """Create a mock audio file for testing."""
    audio_file = tmp_path / "test_audio.wav"
    # Create a simple WAV file with 1 second of silence
    import wave

    with wave.open(str(audio_file), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        # Write 1 second of silence
        data = b"\x00\x00" * 2 * 44100
        wav.writeframes(data)

    return str(audio_file)


@pytest.fixture
def linux_sound(mock_audio_file, audio_config):
    """Create a LinuxPCMSound for testing."""
    return LinuxPCMSound(mock_audio_file, config=audio_config)


class TestLinuxPCMSound:
    """Test suite for LinuxPCMSound."""

    def test_initialization(self, mock_audio_file, audio_config):
        """Test sound initialization."""
        sound = LinuxPCMSound(mock_audio_file, config=audio_config)
        assert sound._filepath == mock_audio_file
        assert sound._config is audio_config
        assert sound.status() == STATUS.STOPPED

    def test_get_audio_config(self, linux_sound, audio_config):
        """Test get_audio_config returns correct config."""
        assert linux_sound.get_audio_config() is audio_config

    def test_get_sample_rate(self, linux_sound, audio_config):
        """Test get_sample_rate returns correct rate."""
        assert linux_sound.get_sample_rate() == audio_config.sample_rate

    def test_get_channels(self, linux_sound, audio_config):
        """Test get_channels returns correct channel count."""
        assert linux_sound.get_channels() == audio_config.channels

    def test_play(self, linux_sound):
        """Test play method."""
        linux_sound.play()
        assert linux_sound.status() == STATUS.PLAYING
        assert linux_sound._sound_file is not None

    def test_pause(self, linux_sound):
        """Test pause method."""
        linux_sound.play()
        linux_sound.pause()
        assert linux_sound.status() == STATUS.PAUSED

    def test_stop(self, linux_sound):
        """Test stop method."""
        linux_sound.play()
        linux_sound.stop()
        assert linux_sound.status() == STATUS.STOPPED
        assert linux_sound._sound_file is None

    def test_stop_cleanup(self, linux_sound):
        """Test that stop cleans up resources."""
        linux_sound.play()
        linux_sound.stop()
        assert linux_sound._resample_buffer is None
        assert linux_sound._resample_position == 0

    def test_get_next_chunk_when_stopped(self, linux_sound):
        """Test get_next_chunk returns None when stopped."""
        chunk = linux_sound.get_next_chunk(512)
        assert chunk is None

    def test_get_next_chunk_when_paused(self, linux_sound):
        """Test get_next_chunk returns None when paused."""
        linux_sound.play()
        linux_sound.pause()
        chunk = linux_sound.get_next_chunk(512)
        assert chunk is None

    def test_get_next_chunk_when_playing(self, linux_sound):
        """Test get_next_chunk returns data when playing."""
        linux_sound.play()
        chunk = linux_sound.get_next_chunk(512)
        assert chunk is not None
        assert chunk.shape == (512, 2)

    def test_loop_configuration(self, mock_audio_file, audio_config):
        """Test loop configuration."""
        sound = LinuxPCMSound(mock_audio_file, config=audio_config, loop=3)
        assert sound._loop == 3

        sound.set_loop(-1)
        assert sound._loop == -1

    def test_volume_configuration(self, mock_audio_file, audio_config):
        """Test volume configuration."""
        sound = LinuxPCMSound(mock_audio_file, config=audio_config, volume=0.5)
        assert sound._volume == 0.5

        sound.set_volume(0.75)
        assert sound._volume == 0.75

    def test_seek(self, mock_audio_file, audio_config):
        """Test seek functionality."""
        sound = LinuxPCMSound(mock_audio_file, config=audio_config)
        sound.play()
        sound.seek(0.5)  # Seek to 0.5 seconds
        # Position should be advanced
        assert sound._position > 0

    def test_convert_channels_mono_to_stereo(self, linux_sound):
        """Test mono to stereo conversion."""
        # linux_sound has stereo config (2 channels)
        mono_data = np.array([[1000], [2000], [3000]], dtype=np.int16)
        result = linux_sound._convert_channels(mono_data)
        assert result.shape == (3, 2)
        assert np.all(result[:, 0] == mono_data[:, 0])
        assert np.all(result[:, 1] == mono_data[:, 0])

    def test_convert_channels_stereo_to_mono(self, mock_audio_file):
        """Test stereo to mono conversion."""
        mono_config = AudioConfig(sample_rate=44100, channels=1, buffer_size=512)
        sound = LinuxPCMSound(mock_audio_file, config=mono_config)
        stereo_data = np.array([[1000, 2000], [3000, 4000]], dtype=np.int16)
        result = sound._convert_channels(stereo_data)
        assert result.shape == (2, 1)
        # Average of 1000 and 2000 is 1500
        assert result[0, 0] == 1500

    def test_convert_channels_no_conversion(self, linux_sound):
        """Test no conversion when channels match."""
        data = np.array([[1000, 2000], [3000, 4000]], dtype=np.int16)
        result = linux_sound._convert_channels(data)
        assert np.array_equal(result, data)

    @patch("sound_player.platform.linux.sound.sf.SoundFile")
    def test_resample(self, mock_soundfile, linux_sound):
        """Test resampling functionality."""
        # Create test data
        data = np.array([[1000, 2000]] * 100, dtype=np.int16)
        result = linux_sound._resample(data)
        assert result is not None
        assert result.shape[1] == 2  # Should maintain channels

    def test_check_loop_infinite(self, linux_sound):
        """Test infinite looping."""
        linux_sound._loop = -1
        assert linux_sound._check_loop() is True

    def test_check_loop_finite(self, linux_sound):
        """Test finite looping.

        With _loop = 3, we want to play 3 times total.
        The _check_loop method is called after each play completes.
        """
        linux_sound._loop = 3

        # After 1st play completes, count becomes 1, should continue
        linux_sound._loop_count = 0
        assert linux_sound._check_loop() is True
        assert linux_sound._loop_count == 1

        # After 2nd play completes, count becomes 2, should continue
        linux_sound._loop_count = 1
        assert linux_sound._check_loop() is True
        assert linux_sound._loop_count == 2

        # After 3rd play completes, count becomes 3, should stop
        linux_sound._loop_count = 2
        assert linux_sound._check_loop() is False
        assert linux_sound._loop_count == 3

    def test_file_info_extraction(self, mock_audio_file, audio_config):
        """Test that file info is extracted correctly."""
        sound = LinuxPCMSound(mock_audio_file, config=audio_config)
        assert sound._file_info is not None
        assert sound._file_sample_rate == 44100
        assert sound._file_channels == 2

    @patch("sound_player.platform.linux.sound.sf.info")
    def test_different_file_formats(self, mock_info, tmp_path, audio_config):
        """Test handling different file formats."""
        # Mock different file info
        mock_info.return_value = MagicMock(
            samplerate=48000,
            channels=1,
            frames=22050,
        )

        test_file = tmp_path / "test.ogg"
        test_file.touch()

        sound = LinuxPCMSound(str(test_file), config=audio_config)
        assert sound._file_sample_rate == 48000
        assert sound._file_channels == 1
