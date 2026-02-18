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
from sound_player.core.constants import MAX_INT16, MAX_INT32
from sound_player.core.mixins import STATUS

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

        # Check if file is in float format (which has conversion issues in soundfile)
        self._file_is_float = self._file_info.subtype in ("FLOAT", "DOUBLE", "VORBIS", "OPUS", "MP3", "FLAC")

        # Playback state
        self._sound_file: sf.SoundFile | None = None
        self._position = 0  # Current position in samples
        self._loop_count = 0

        # Resampling buffers
        self._resample_buffer: np.ndarray | None = None
        self._resample_position = 0

        # File's native dtype for reading
        self._file_dtype = None

        # Cache whether conversion is needed (avoids recalculating every chunk)
        config = self.config
        self._needs_conversion = self._file_sample_rate != config.sample_rate or self._file_channels != config.channels

        # Cache whether float-to-int conversion is needed for _safe_read
        self._needs_float_conversion = self._file_is_float and config.dtype in (
            np.dtype(np.int16),
            np.dtype(np.int32),
        )
        self._is_int16 = config.dtype == np.int16

    def _get_file_dtype(self) -> str:
        """Get the file's native dtype for safe reading.

        Returns:
            The numpy dtype string that matches the file's format
        """
        if not self._file_is_float:
            # For integer formats, we can read directly to target dtype
            return self.config.dtype
        # For float formats, read as float32/float64 first
        return "float32"

    def _safe_read(self, frames: int) -> np.ndarray:
        """Read from file with proper format conversion.

        For float files, reads as float32 first then converts to target dtype.
        For integer files, reads directly to target dtype.

        Args:
            frames: Number of frames to read

        Returns:
            Audio data as numpy array
        """
        if self._needs_float_conversion:
            # Read as float first, then convert to integer range
            data = self._sound_file.read(frames, dtype="float32")
            if self._is_int16:
                return (data * MAX_INT16).astype(np.int16)
            else:  # int32
                return (data * MAX_INT32).astype(np.int32)
        else:
            return self._sound_file.read(frames, dtype=self.config.dtype)

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
            config = self.config
            if self._file_sample_rate != config.sample_rate or self._file_channels != config.channels:
                logger.debug(
                    f"File format mismatch: file={self._file_sample_rate}Hz/{self._file_channels}ch, "
                    f"config={config.sample_rate}Hz/{config.channels}ch"
                )

            # Store the file's native dtype for proper reading
            self._file_dtype = self._get_file_dtype()

            # Log if file is float format
            if self._file_is_float:
                logger.debug(f"File is float format, will convert to {config.dtype}")

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

        if self._needs_conversion:
            return self._get_converted_chunk(size)
        else:
            return self._get_raw_chunk(size)

    def _get_raw_chunk(self, size: int) -> np.ndarray | None:
        """Get a chunk without format conversion."""
        if self._sound_file is None:
            return None

        # Read samples from file (with proper float->int conversion if needed)
        data = self._safe_read(size)
        self._position += len(data)

        # Handle end of file and looping
        if len(data) < size:
            if self._check_loop():
                # Seek to beginning and read remaining samples
                self._sound_file.seek(0)
                remaining = size - len(data)
                extra = self._safe_read(remaining)
                if len(extra) > 0:
                    data = np.concatenate([data, extra])
                    self._position = len(extra)
            else:
                # No more loops - sound is finished
                # Set status directly since we're already inside the lock from get_next_chunk()
                self._do_stop()
                self._status = STATUS.STOPPED
                return None

        # Ensure shape is (size, channels)
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        return data

    def _get_converted_chunk(self, size: int) -> np.ndarray | None:
        """Get a chunk with sample rate and/or channel conversion."""
        if self._sound_file is None:
            return None

        config = self.config
        result = np.zeros((size, config.channels), dtype=config.dtype)
        result_pos = 0

        while result_pos < size:
            # Check if we need to read more data
            if self._resample_buffer is None or self._resample_position >= len(self._resample_buffer):
                # Calculate how many file samples we need for the output
                ratio = self._file_sample_rate / config.sample_rate
                file_samples_needed = int((size - result_pos) * ratio) + 1

                # Read from file (with proper float->int conversion if needed)
                data = self._safe_read(file_samples_needed)
                self._position += len(data)

                # Handle EOF
                if len(data) < file_samples_needed:
                    if self._check_loop():
                        self._sound_file.seek(0)
                        # Read remaining for this block
                        extra = self._safe_read(file_samples_needed - len(data))
                        if len(extra) > 0:
                            data = np.concatenate([data, extra])
                            self._position = len(extra)
                    else:
                        # No more loops - sound is finished
                        # Set status directly since we're already inside the lock from get_next_chunk()
                        self._do_stop()
                        self._status = STATUS.STOPPED
                        break

                # Convert channels if needed
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                if self._file_channels != config.channels:
                    data = self._convert_channels(data)

                # Resample if needed
                if self._file_sample_rate != config.sample_rate:
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
        target_channels = self.config.channels

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
        config = self.config
        if self._file_sample_rate == config.sample_rate:
            return data

        ratio = self._file_sample_rate / config.sample_rate
        input_length = len(data)
        output_length = int(input_length / ratio)

        if output_length == 0:
            return np.zeros((0, data.shape[1]), dtype=data.dtype)

        # Pre-compute interpolation indices once
        indices = np.linspace(0, input_length - 1, output_length)
        source_indices = np.arange(input_length)

        if data.shape[1] == 1:
            # Mono: single interp call, no loop needed
            resampled = np.interp(indices, source_indices, data[:, 0]).astype(data.dtype)
            return resampled.reshape(-1, 1)
        else:
            # Stereo: vectorize both channels
            resampled = np.column_stack(
                [np.interp(indices, source_indices, data[:, ch]) for ch in range(data.shape[1])]
            ).astype(data.dtype)
            return resampled

    def _get_remaining_samples(self) -> int | None:
        """Return remaining output samples until end of the last loop.

        Returns None for infinite loops or when the file is not open.
        Called with the lock held.
        """
        if self._sound_file is None or self._loop == -1:
            return None

        # Check if we are on the last loop iteration
        # _loop_count is incremented each time EOF is hit, so during pass N it equals N
        is_last_loop = self._loop is None or self._loop_count >= self._loop - 1
        if not is_last_loop:
            return None

        remaining_file_samples = self._file_info.frames - self._position
        if remaining_file_samples <= 0:
            return 0

        if self._file_sample_rate != self.config.sample_rate:
            return int(remaining_file_samples * self.config.sample_rate / self._file_sample_rate)
        return remaining_file_samples

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
