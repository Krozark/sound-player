"""Base sound class and PCM buffer interface for the sound player library."""

import logging
import time

import numpy as np

from .mixins import STATUS, AudioConfigMixin, FadeMixin, FadeState, StatusMixin

logger = logging.getLogger(__name__)

__all__ = [
    "BaseSound",
]


class BaseSound(StatusMixin, AudioConfigMixin, FadeMixin):
    """Base class for all sound types.

    Provides PCM buffer interface and platform-specific hooks for
    audio playback control.
    """

    def __init__(self, filepath, loop=None, *args, **kwargs):
        """Initialize the BaseSound.

        Args:
            filepath: Path to the audio file
            config: AudioConfig for audio format
            loop: Loop count (-1 for infinite, None for no loop)
            volume: Initial volume (0.0-1.0)
        """
        super().__init__(*args, **kwargs)
        self._filepath = filepath
        self._loop = loop

    def set_loop(self, loop):
        """Set the loop count.

        Args:
            loop: Loop count (-1 for infinite)
        """
        logger.debug("BaseSound.set_loop(%s)", loop)
        with self._lock:
            self._loop = loop

    def wait(self, timeout=None):
        """Wait for the sound to finish playing.

        Args:
            timeout: Maximum time to wait in seconds, None for unlimited
        """
        logger.debug("BaseSound.wait()")
        start_time = time.time()
        while self._status != STATUS.STOPPED and (timeout is None or time.time() - start_time < timeout):
            time.sleep(0.1)

    def get_next_chunk(self, size: int) -> np.ndarray | None:
        """Return next audio chunk as numpy array.

        This implementation handles sample-accurate fading and thread safety.
        """
        with self._lock:
            if self._status in (STATUS.STOPPED, STATUS.PAUSED):
                return None

            chunk = self._do_get_next_chunk(size)

            if chunk is not None:
                # Get sample-accurate fade multipliers for this chunk size
                fade_map = self._get_fade_multiplier_array(len(chunk))

                # Check if we actually need to apply math (optimization)
                # If all multipliers are 1.0, we can skip multiplication
                if not np.all(fade_map == 1.0):
                    # Broadcast fade_map to match channels
                    # fade_map is (N,), chunk is (N, Channels)
                    # We add a new axis to fade_map to make it (N, 1) for broadcasting
                    chunk = (chunk.astype(np.float32) * fade_map[:, np.newaxis]).astype(self.config.dtype)

                # Auto-stop logic:
                # If fade finished (NONE) AND volume is effectively 0, stop playback
                if self._fade_state == FadeState.NONE and self._fade_target_volume <= 0.001:
                    # Double check the last sample of the map to be sure we are at 0
                    if fade_map[-1] <= 0.001:
                        self._status = STATUS.STOPPED

            return chunk

    def _do_get_next_chunk(self, size: int) -> np.ndarray | None:
        """Get the next chunk of audio data.

        Subclasses must implement this method to provide the actual
        audio data. This method is called with the lock held.

        Args:
            size: Number of samples to return

        Returns:
            Audio data as numpy array with shape (size, channels)
            Returns None if sound has ended
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement _do_get_next_chunk()")

    def get_sample_rate(self) -> int:
        """Return the audio sample rate.

        Returns:
            Sample rate in Hz
        """
        return self.config.sample_rate

    def get_channels(self) -> int:
        """Return the number of audio channels.

        Returns:
            Number of channels (1=mono, 2=stereo)
        """
        return self.config.channels

    def seek(self, position: float) -> None:
        """Seek to position in seconds.

        Args:
            position: Position in seconds
        """
        logger.debug("BaseSound.seek(%s)", position)
        with self._lock:
            self._do_seek(position)

    def _do_seek(self, position: float) -> None:
        """Hook for subclasses to implement seeking.

        Called with the lock held.

        Args:
            position: Position in seconds
        """
        pass
