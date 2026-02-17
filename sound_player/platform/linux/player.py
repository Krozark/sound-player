"""Linux audio output implementation using sounddevice.

This module provides the LinuxSoundPlayer class which implements audio
output on Linux using the sounddevice library.
"""

import logging

from sound_player.core.base_player import BaseSoundPlayer

try:
    import sounddevice as sd
except ImportError as e:
    raise ImportError(
        "sounddevice is required for audio output on Linux. Install it with: pip install sound-player[linux]"
    ) from e


logger = logging.getLogger(__name__)

__all__ = [
    "LinuxSoundPlayer",
]


class LinuxSoundPlayer(BaseSoundPlayer):
    """Linux audio output using sounddevice.

    This implementation:
    - Uses sounddevice.RawOutputStream with a callback for efficient audio output
    - The callback continuously pulls mixed audio from get_next_chunk()
    - Supports play/pause/stop control
    """

    def __init__(self, *args, **kwargs):
        """Initialize the LinuxSoundPlayer.

        Args:
            config: AudioConfig for audio output format
        """
        super().__init__(*args, **kwargs)
        self._stream = None

    def _create_output_stream(self):
        """Create the sounddevice output stream.

        Creates a RawOutputStream with a callback that will be invoked
        by sounddevice whenever it needs more audio data.
        """

        config = self.config
        logger.debug(
            f"Creating sounddevice stream: {config.sample_rate}Hz, "
            f"{config.channels}ch, {config.dtype}"
        )

        self._stream = sd.RawOutputStream(
            samplerate=config.sample_rate,
            channels=config.channels,
            dtype=config.dtype,
            blocksize=config.buffer_size,
            callback=self._audio_callback,
        )

    def _audio_callback(self, outdata, frames, time, status):
        """Called by sounddevice to fill the output buffer.

        This callback is invoked by sounddevice whenever it needs more
        audio data. We pull the next mixed chunk from get_next_chunk()
        and copy it to the output buffer.

        Args:
            outdata: Output buffer to fill with audio data
            frames: Number of frames to write
            time: Timestamp information
            status: Stream status (e.g., underflow)
        """
        if status:
            logger.warning(f"Audio callback status: {status}")

        chunk = self.get_next_chunk()
        if chunk is not None:
            # Reshape chunk to match output buffer shape (frames, channels)
            config = self.config
            if chunk.size == frames * config.channels:
                outdata[:] = chunk.reshape(frames, config.channels)
            else:
                # Handle size mismatch (shouldn't happen normally)
                logger.warning(f"Chunk size mismatch: {chunk.size} vs {frames * config.channels}")
                outdata[:] = 0
        else:
            # No audio data, output silence
            outdata[:] = 0

    def _close_output_stream(self):
        """Close the sounddevice stream.

        Stops and closes the audio stream, releasing the audio device.
        """
        logger.debug("Closing sounddevice stream")
        with self._lock:
            if self._stream:
                if self._stream.active:
                    self._stream.stop()
                self._stream.close()
                self._stream = None

    # Hooks for StatusMixin
    def _do_play(self):
        """Hook called when play status changes to PLAYING."""
        # Start the audio output stream
        if self._stream is None:
            self._create_output_stream()
        if not self._stream.active:
            self._stream.start()

    def _do_pause(self):
        """Hook called when play status changes to PAUSED."""
        # Stop the audio output stream
        if self._stream and self._stream.active:
            self._stream.stop()

    def _do_stop(self):
        """Hook called when play status changes to STOPPED."""
        # Close the audio output stream
        self._close_output_stream()

    def __del__(self):
        """Cleanup on deletion."""
        import contextlib

        with contextlib.suppress(Exception):
            self._close_output_stream()
