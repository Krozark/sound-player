"""Tests for the AudioConfig class."""

import numpy as np
import pytest

from sound_player.audio_config import AudioConfig


class TestAudioConfig:
    """Test suite for AudioConfig."""

    def test_default_initialization(self):
        """Test default values."""
        config = AudioConfig()
        assert config.sample_rate == 44100
        assert config.channels == 2
        assert config.sample_width == 2
        assert config.buffer_size == 1024
        assert config.dtype == np.int16

    def test_custom_initialization(self):
        """Test custom values."""
        config = AudioConfig(
            sample_rate=48000,
            channels=1,
            sample_width=2,
            buffer_size=512,
            dtype=np.int16,
        )
        assert config.sample_rate == 48000
        assert config.channels == 1
        assert config.sample_width == 2
        assert config.buffer_size == 512

    def test_sample_width_validation(self):
        """Test that sample_width is validated."""
        # Valid values - sample_width is synced with dtype
        config = AudioConfig(sample_width=2, dtype=np.int16)
        assert config.sample_width == 2

        config = AudioConfig(sample_width=4, dtype=np.int32)
        assert config.sample_width == 4

        # Invalid value
        with pytest.raises(ValueError):
            AudioConfig(sample_width=3)

    def test_channels_validation(self):
        """Test that channels is validated."""
        # Valid values
        config = AudioConfig(channels=1)
        assert config.channels == 1

        config = AudioConfig(channels=2)
        assert config.channels == 2

        # Invalid value
        with pytest.raises(ValueError):
            AudioConfig(channels=3)

    def test_sample_rate_validation(self):
        """Test that sample_rate is validated."""
        # Valid values
        config = AudioConfig(sample_rate=44100)
        assert config.sample_rate == 44100

        # Invalid value
        with pytest.raises(ValueError):
            AudioConfig(sample_rate=0)

        with pytest.raises(ValueError):
            AudioConfig(sample_rate=-1)

    def test_buffer_size_validation(self):
        """Test that buffer_size is validated."""
        # Valid values
        config = AudioConfig(buffer_size=512)
        assert config.buffer_size == 512

        # Invalid value
        with pytest.raises(ValueError):
            AudioConfig(buffer_size=0)

        with pytest.raises(ValueError):
            AudioConfig(buffer_size=-1)

    def test_dtype_conversion(self):
        """Test that dtype string is converted to numpy dtype."""
        config = AudioConfig(dtype="int16")
        assert config.dtype == np.dtype("int16")

    def test_sample_width_dtype_sync(self):
        """Test that sample_width is synced with dtype."""
        config = AudioConfig(dtype=np.int32)
        assert config.sample_width == 4

        config = AudioConfig(dtype=np.int16)
        assert config.sample_width == 2

    def test_bytes_per_second(self):
        """Test bytes_per_second calculation."""
        config = AudioConfig(sample_rate=44100, channels=2, sample_width=2)
        # 44100 * 2 * 2 = 176400
        assert config.bytes_per_second == 176400

    def test_buffer_duration_ms(self):
        """Test buffer_duration_ms calculation."""
        config = AudioConfig(sample_rate=44100, buffer_size=441)
        # 441 samples at 44100 Hz = 10ms
        assert config.buffer_duration_ms == 10.0

    def test_max_sample_value_int16(self):
        """Test max_sample_value for int16."""
        config = AudioConfig(dtype=np.int16)
        assert config.max_sample_value == 32767

    def test_min_sample_value_int16(self):
        """Test min_sample_value for int16."""
        config = AudioConfig(dtype=np.int16)
        assert config.min_sample_value == -32768

    def test_max_sample_value_int32(self):
        """Test max_sample_value for int32."""
        config = AudioConfig(dtype=np.int32)
        assert config.max_sample_value == 2147483647

    def test_min_sample_value_int32(self):
        """Test min_sample_value for int32."""
        config = AudioConfig(dtype=np.int32)
        assert config.min_sample_value == -2147483648

    def test_different_sample_rates(self):
        """Test various sample rates."""
        for rate in [8000, 16000, 22050, 44100, 48000, 96000]:
            config = AudioConfig(sample_rate=rate)
            assert config.sample_rate == rate

    def test_stereo_configuration(self):
        """Test stereo configuration."""
        config = AudioConfig(channels=2)
        assert config.channels == 2

    def test_mono_configuration(self):
        """Test mono configuration."""
        config = AudioConfig(channels=1)
        assert config.channels == 1
