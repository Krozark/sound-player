"""Base sound class and PCM buffer interface for the sound player library."""

import logging
import time

import numpy as np

from .mixins import STATUS, AudioConfigMixin, StatusMixin

logger = logging.getLogger(__name__)

__all__ = [
    "BaseSound",
]


class BaseSound(StatusMixin, AudioConfigMixin):
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
        start_timestamps = time.time()
        while self._status != STATUS.STOPPED and (timeout is None or start_timestamps + timeout < time.time()):
            time.sleep(0.1)

    # PCM buffer interface for audio mixing

    def get_next_chunk(self, size: int) -> np.ndarray | None:
        """Return next audio chunk as numpy array.

        This method is called by the AudioMixer to get the next chunk of
        audio data for mixing. This implementation handles common logic
        like checking playback status and thread safety, then delegates
        to _do_get_next_chunk for platform-specific implementation.

        Args:
            size: Number of samples to return

        Returns:
            Audio data as numpy array with shape (size, channels)
            Returns None if sound has ended or is not playing
        """
        with self._lock:
            if self._status in (STATUS.STOPPED, STATUS.PAUSED):
                return None
            return self._do_get_next_chunk(size)

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
