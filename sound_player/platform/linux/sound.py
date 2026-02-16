"""Linux PCM audio implementation using soundfile.

This module provides the LinuxPCMSound class which implements PCM-based
audio decoding on Linux using:
- soundfile for audio file decoding

Note: For audio output, use sounddevice which is an optional dependency.
Install it with: pip install sound-player[linux]
"""

import logging

import numpy as np
import soundfile as sf

from sound_player.core.base_sound import BaseSound

logger = logging.getLogger(__name__)

__all__ = [
    "LinuxPCMSound",
]


class LinuxPCMSound(BaseSound):
    """Linux PCM sound implementation using soundfile.

    This implementation:
    - Decodes audio files using soundfile (supports many formats)
    - Provides PCM audio chunks for mixing via get_next_chunk()
    - Supports real-time mixing through the AudioMixer

    For audio output, you can use the get_next_chunk() method with
    sounddevice or any other audio output library.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the LinuxPCMSound.

        Args:
            filepath: Path to the audio file
            config: AudioConfig for output format (uses file's native format if None)
            loop: Number of times to loop (-1 for infinite)
            volume: Volume level (0-100)
        """
        super().__init__(*args, **kwargs)

        # Audio file info
        self._file_info = sf.info(self._filepath)
        self._file_sample_rate = self._file_info.samplerate
        self._file_channels = self._file_info.channels

        # Playback state
        self._sound_file: sf.SoundFile | None = None
        self._position = 0  # Current position in samples
        self._loop_count = 0

        # Resampling buffers
        self._resample_buffer: np.ndarray | None = None
        self._resample_position = 0

    def _do_play(self):
        """Start or resume playback."""
        logger.debug("LinuxPCMSound._do_play()")

        if self._sound_file is None:
            # Open the sound file
            self._sound_file = sf.SoundFile(self._filepath)
            self._position = 0
            self._loop_count = 0
            self._resample_buffer = None
            self._resample_position = 0

            # If sample rate or channels don't match config, we need resampling/conversion
            if self._file_sample_rate != self._config.sample_rate or self._file_channels != self._config.channels:
                logger.debug(
                    f"File format mismatch: file={self._file_sample_rate}Hz/{self._file_channels}ch, "
                    f"config={self._config.sample_rate}Hz/{self._config.channels}ch"
                )

    def _do_pause(self):
        """Pause playback."""
        logger.debug("LinuxPCMSound._do_pause()")
        # Position is preserved, we just stop reading

    def _do_stop(self):
        """Stop playback and reset position."""
        logger.debug("LinuxPCMSound._do_stop()")
        if self._sound_file is not None:
            self._sound_file.close()
            self._sound_file = None
        self._position = 0
        self._loop_count = 0
        self._resample_buffer = None
        self._resample_position = 0

    def _do_get_next_chunk(self, size: int) -> np.ndarray | None:
        """Get the next chunk of audio data.

        Args:
            size: Number of samples to return

        Returns:
            Audio data as numpy array with shape (size, config.channels)
            Returns None if sound has ended and no more loops
        """
        if self._sound_file is None:
            return None

        # Check if we need resampling or channel conversion
        needs_conversion = (
            self._file_sample_rate != self._config.sample_rate or self._file_channels != self._config.channels
        )

        if needs_conversion:
            return self._get_converted_chunk(size)
        else:
            return self._get_raw_chunk(size)

    def _get_raw_chunk(self, size: int) -> np.ndarray | None:
        """Get a chunk without format conversion."""
        if self._sound_file is None:
            return None

        # Read samples from file
        data = self._sound_file.read(size, dtype=self._config.dtype)
        self._position += len(data)

        # Handle end of file and looping
        if len(data) < size:
            if self._check_loop():
                # Seek to beginning and read remaining samples
                self._sound_file.seek(0)
                remaining = size - len(data)
                extra = self._sound_file.read(remaining, dtype=self._config.dtype)
                if len(extra) > 0:
                    data = np.concatenate([data, extra])
                    self._position = len(extra)
            else:
                # No more loops - sound is finished
                self.stop()
                return None

        # Ensure shape is (size, channels)
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        return data

    def _get_converted_chunk(self, size: int) -> np.ndarray | None:
        """Get a chunk with sample rate and/or channel conversion."""
        if self._sound_file is None:
            return None

        result = np.zeros((size, self._config.channels), dtype=self._config.dtype)
        result_pos = 0

        while result_pos < size:
            # Check if we need to read more data
            if self._resample_buffer is None or self._resample_position >= len(self._resample_buffer):
                # Calculate how many file samples we need for the output
                ratio = self._file_sample_rate / self._config.sample_rate
                file_samples_needed = int((size - result_pos) * ratio) + 1

                # Read from file
                data = self._sound_file.read(file_samples_needed, dtype=self._config.dtype)
                self._position += len(data)

                # Handle EOF
                if len(data) < file_samples_needed:
                    if self._check_loop():
                        self._sound_file.seek(0)
                        # Read remaining for this block
                        extra = self._sound_file.read(file_samples_needed - len(data), dtype=self._config.dtype)
                        if len(extra) > 0:
                            data = np.concatenate([data, extra])
                            self._position = len(extra)
                    else:
                        # No more loops - sound is finished
                        self.stop()
                        break

                # Convert channels if needed
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                if self._file_channels != self._config.channels:
                    data = self._convert_channels(data)

                # Resample if needed
                if self._file_sample_rate != self._config.sample_rate:
                    data = self._resample(data)

                self._resample_buffer = data
                self._resample_position = 0

            # Copy from resample buffer to result
            if self._resample_buffer is not None:
                available = len(self._resample_buffer) - self._resample_position
                needed = size - result_pos
                to_copy = min(available, needed)

                result[result_pos : result_pos + to_copy] = self._resample_buffer[
                    self._resample_position : self._resample_position + to_copy
                ]
                result_pos += to_copy
                self._resample_position += to_copy

        return result

    def _convert_channels(self, data: np.ndarray) -> np.ndarray:
        """Convert audio data to target channel count."""
        input_channels = data.shape[1] if len(data.shape) > 1 else 1
        target_channels = self._config.channels

        if input_channels == target_channels:
            return data

        if input_channels == 1 and target_channels == 2:
            # Mono to stereo
            if len(data.shape) == 1:
                data = data.reshape(-1, 1)
            return np.repeat(data, 2, axis=1)
        elif input_channels == 2 and target_channels == 1:
            # Stereo to mono
            return np.mean(data, axis=1, keepdims=True).astype(data.dtype)
        else:
            return data

    def _resample(self, data: np.ndarray) -> np.ndarray:
        """Resample audio data to target sample rate.

        Uses simple linear interpolation for resampling.
        """
        if self._file_sample_rate == self._config.sample_rate:
            return data

        ratio = self._file_sample_rate / self._config.sample_rate
        output_length = int(len(data) / ratio)

        # Use numpy's linear interpolation
        indices = np.linspace(0, len(data) - 1, output_length)
        resampled = np.zeros((output_length, data.shape[1]), dtype=data.dtype)

        for channel in range(data.shape[1]):
            resampled[:, channel] = np.interp(indices, np.arange(len(data)), data[:, channel]).astype(data.dtype)

        return resampled

    def _check_loop(self) -> bool:
        """Check if we should loop and update loop counter.

        Returns:
            True if looping should continue, False otherwise
        """
        self._loop_count += 1

        if self._loop == -1:
            # Infinite loop
            return True
        # Return True if we should continue looping
        return self._loop is not None and self._loop_count < self._loop

    def _do_seek(self, position: float) -> None:
        """Seek to position in seconds.

        Args:
            position: Position in seconds
        """
        if self._sound_file is not None:
            sample_position = int(position * self._file_sample_rate)
            self._sound_file.seek(sample_position)
            self._position = sample_position
            self._resample_buffer = None
            self._resample_position = 0

    def __del__(self):
        """Cleanup on deletion."""
        self._do_stop()
