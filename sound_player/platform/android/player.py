"""Android audio output implementation using AudioTrack.

This module provides the AndroidSoundPlayer class which implements audio
output on Android using the AudioTrack API with blocking write mode.
"""

import logging
import threading
import time

import numpy as np

from sound_player.core import STATUS, AudioConfig
from sound_player.core.base_player import BaseSoundPlayer

logger = logging.getLogger(__name__)

try:
    from jnius import autoclass

    ANDROID_AVAILABLE = True
except Exception:
    ANDROID_AVAILABLE = False
    logger.warning("Android APIs not available")

__all__ = [
    "AndroidSoundPlayer",
]


class AndroidSoundPlayer(BaseSoundPlayer):
    """Android audio output using AudioTrack in blocking write mode.

    This implementation:
    - Uses AudioTrack in MODE_STREAM for real-time PCM output
    - Runs a background thread to continuously pull and write audio data
    - Supports play/pause/stop control via inherited StatusMixin
    """

    # Android AudioFormat constants
    ENCODING_PCM_16BIT = 2
    CHANNEL_OUT_MONO = 4
    CHANNEL_OUT_STEREO = 12
    MODE_STREAM = 1

    # Android AudioManager constants
    STREAM_MUSIC = 3

    # Android AudioAttributes constants
    USAGE_MEDIA = 1
    CONTENT_TYPE_MUSIC = 2

    def __init__(self, config: AudioConfig | None = None):
        """Initialize the AndroidSoundPlayer.

        Args:
            config: AudioConfig for audio output format

        Raises:
            RuntimeError: If Android APIs are not available
        """
        if not ANDROID_AVAILABLE:
            raise RuntimeError("Android APIs not available")

        super().__init__(config)
        self._audiotrack = None
        self._output_thread = None
        self._stop_output_event = threading.Event()

    def _create_output_stream(self):
        """Create the AudioTrack for PCM output.

        Creates an AudioTrack instance in stream mode with the configured
        audio format. Uses modern AudioAttributes API (API 21+) with fallback.
        """
        if self._audiotrack is not None:
            return

        try:
            AudioTrack = autoclass("android.media.AudioTrack")
            AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")
            AudioFormatBuilder = autoclass("android.media.AudioFormat$Builder")

            config = self.config
            logger.debug(
                f"Creating AudioTrack: {config.sample_rate}Hz, {config.channels}ch, {config.dtype}"
            )

            # Determine channel mask
            channel_mask = self.CHANNEL_OUT_STEREO if config.channels == 2 else self.CHANNEL_OUT_MONO

            # Determine encoding
            encoding = self.ENCODING_PCM_16BIT
            bytes_per_sample = 2

            # Create audio attributes (API 21+)
            attrs = AudioAttributesBuilder().setUsage(self.USAGE_MEDIA).setContentType(self.CONTENT_TYPE_MUSIC).build()

            # Create audio format
            fmt = (
                AudioFormatBuilder()
                .setEncoding(encoding)
                .setSampleRate(config.sample_rate)
                .setChannelMask(channel_mask)
                .build()
            )

            # Calculate buffer size in bytes
            # Android recommends buffer_size = sample_rate * channels * bytes_per_sample / buffers_per_second
            # Using a reasonable buffer size
            min_buffer_size = AudioTrack.getMinBufferSize(config.sample_rate, channel_mask, encoding)
            buffer_size = max(min_buffer_size, config.buffer_size * config.channels * bytes_per_sample)

            # Create AudioTrack in stream mode
            self._audiotrack = AudioTrack(attrs, fmt, buffer_size, self.MODE_STREAM, 0)

            logger.debug(f"AudioTrack created successfully with buffer size: {buffer_size}")

        except Exception as e:
            logger.error(f"Failed to create AudioTrack: {e}")
            raise

    def _output_thread_task(self):
        """Background thread that continuously writes audio data.

        This thread runs continuously while playing, pulling audio data
        from get_next_chunk() and writing it to the AudioTrack in blocking mode.
        """
        logger.debug("Audio output thread started")

        while not self._stop_output_event.is_set():
            if self._status == STATUS.PLAYING and self._audiotrack:
                chunk = self.get_next_chunk()
                if chunk is not None:
                    self._write_audio(chunk)
                else:
                    # No audio data, write a small silence buffer
                    config = self.config
                    silence = np.zeros((config.buffer_size // 4, config.channels), dtype=config.dtype)
                    self._write_audio(silence)
            else:
                # Not playing, wait a bit
                time.sleep(0.01)

        logger.debug("Audio output thread stopped")

    def _write_audio(self, data: np.ndarray):
        """Write PCM data to the AudioTrack.

        Converts the numpy array to bytes and writes to the AudioTrack.
        Uses blocking write which will wait until the buffer has space.

        Args:
            data: Audio data as numpy array
        """
        if self._audiotrack is None:
            return

        try:
            # Convert numpy array to bytes
            bytes_data = data.tobytes()

            # Write in blocking mode - this will wait until there's space in the buffer
            written = self._audiotrack.write(bytes_data, 0, len(bytes_data), 0)

            if written < 0:
                logger.warning(f"AudioTrack.write returned: {written}")

        except Exception as e:
            logger.error(f"Error writing to AudioTrack: {e}")

    def _start_output_thread(self):
        """Start the background output thread."""
        if self._output_thread is None or not self._output_thread.is_alive():
            self._stop_output_event.clear()
            self._output_thread = threading.Thread(target=self._output_thread_task, daemon=True, name="AudioOutput")
            self._output_thread.start()

    def _join_output_thread(self):
        """Stop the background output thread."""
        self._stop_output_event.set()
        if self._output_thread and self._output_thread.is_alive():
            self._output_thread.join(timeout=1.0)

    def _close_output_stream(self):
        """Close and release the AudioTrack.

        Stops playback and releases all AudioTrack resources.
        """
        logger.debug("Closing AudioTrack")
        if self._audiotrack:
            try:
                if self._audiotrack.getPlayState() == 3:  # PLAYSTATE_PLAYING
                    self._audiotrack.stop()
                self._audiotrack.release()
            except Exception as e:
                logger.error(f"Error releasing AudioTrack: {e}")
            finally:
                self._audiotrack = None

    # Hooks for StatusMixin
    def _do_play(self):
        """Hook called when play status changes to PLAYING."""
        # Create AudioTrack if needed and start playback
        if self._audiotrack is None:
            self._create_output_stream()

        if self._audiotrack.getPlayState() != 3:  # Not PLAYING
            self._audiotrack.play()
            self._start_output_thread()

    def _do_pause(self):
        """Hook called when play status changes to PAUSED."""
        # Pause the AudioTrack
        if self._audiotrack:
            self._audiotrack.pause()

    def _do_stop(self):
        """Hook called when play status changes to STOPPED."""
        # Stop output thread and close AudioTrack
        self._join_output_thread()
        self._close_output_stream()

    def __del__(self):
        """Cleanup on deletion."""
        self._join_output_thread()
        self._close_output_stream()
