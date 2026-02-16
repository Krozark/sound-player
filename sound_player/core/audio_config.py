"""Audio configuration for the sound player library.

This module provides the AudioConfig dataclass which defines the audio format
parameters used throughout the library for PCM audio processing.
"""

from dataclasses import dataclass

import numpy as np

from .constants import MAX_INT16, MAX_INT32, MIN_INT16, MIN_INT32

__all__ = [
    "AudioConfig",
]


@dataclass
class AudioConfig:
    """Configuration for PCM audio processing.

    Attributes:
        sample_rate: Sample rate in Hz (e.g., 44100, 48000)
        channels: Number of audio channels (1=mono, 2=stereo)
        sample_width: Bytes per sample (2=int16, 4=int32)
        buffer_size: Number of samples per buffer
        dtype: NumPy dtype for audio samples
    """

    sample_rate: int = 44100
    channels: int = 2
    sample_width: int = 2
    buffer_size: int = 1024
    dtype: np.dtype = np.int16

    def __post_init__(self):
        """Validate and normalize configuration parameters."""
        # Ensure dtype is a numpy dtype
        if not isinstance(self.dtype, np.dtype):
            self.dtype = np.dtype(self.dtype)

        # Validate channels
        if self.channels not in (1, 2):
            raise ValueError(f"channels must be 1 or 2, got {self.channels}")

        # Validate sample_rate
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")

        # Validate buffer_size
        if self.buffer_size <= 0:
            raise ValueError(f"buffer_size must be positive, got {self.buffer_size}")

        # Validate sample_width before syncing with dtype
        if self.sample_width not in (2, 4):
            raise ValueError(f"sample_width must be 2 or 4, got {self.sample_width}")

        # Sync sample_width with dtype if they match expected sizes
        expected_width = self.dtype.itemsize
        if expected_width in (2, 4) and self.sample_width != expected_width:
            # Auto-correct sample_width to match dtype
            self.sample_width = expected_width

    @property
    def bytes_per_second(self) -> int:
        """Calculate bytes per second for this configuration."""
        return self.sample_rate * self.channels * self.sample_width

    @property
    def buffer_duration_ms(self) -> float:
        """Calculate buffer duration in milliseconds."""
        return (self.buffer_size / self.sample_rate) * 1000

    @property
    def max_sample_value(self) -> int:
        """Get the maximum positive sample value for this format."""
        if self.dtype == np.int16:
            return MAX_INT16
        elif self.dtype == np.int32:
            return MAX_INT32
        return 0

    @property
    def min_sample_value(self) -> int:
        """Get the minimum negative sample value for this format."""
        if self.dtype == np.int16:
            return MIN_INT16
        elif self.dtype == np.int32:
            return MIN_INT32
        return 0
