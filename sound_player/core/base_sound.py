"""Base sound class and PCM buffer interface for the sound player library."""

import logging
import time
from abc import ABC, abstractmethod

import numpy as np

from .mixins import STATUS, AudioConfigMixin, FadeMixin, FadeState, StatusMixin

logger = logging.getLogger(__name__)

__all__ = [
    "BaseSound",
]


class BaseSound(StatusMixin, AudioConfigMixin, FadeMixin, ABC):
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

    def _get_remaining_samples(self) -> int | None:
        """Return the number of output samples remaining until end of the last loop.

        Returns None if unknown (e.g. infinite loop, or platform doesn't support it).
        Called with the lock held. Subclasses should override this to enable
        automatic fade-out support.
        """
        return None

    def get_next_chunk(self, size: int) -> np.ndarray | None:
        """Return next audio chunk as numpy array.

        This implementation handles sample-accurate fading and thread safety.
        """
        with self._lock:
            if self._status in (STATUS.STOPPED, STATUS.PAUSED):
                return None

            # Auto-trigger fade-out when approaching end of last loop
            if (
                self._fade_out_samples is not None
                and self._fade_state != FadeState.FADING_OUT
                and self._fade_target_volume > 0.001
            ):
                remaining = self._get_remaining_samples()
                if remaining is not None and 0 < remaining <= self._fade_out_samples:
                    self.fade_out(remaining / self.config.sample_rate)

            chunk = self._do_get_next_chunk(size)

            if chunk is not None:
                # Fast path: skip fade math when not fading and target is full volume
                if self._fade_state == FadeState.NONE and self._fade_target_volume >= 0.999:
                    return chunk

                # Get sample-accurate fade multipliers for this chunk size
                fade_map = self._get_fade_multiplier_array(len(chunk))

                # Apply fade: broadcast fade_map (N,) to chunk (N, Channels) via (N, 1)
                if chunk.dtype == np.float32:
                    chunk = (chunk * fade_map[:, np.newaxis]).astype(self.config.dtype)
                else:
                    chunk = (chunk.astype(np.float32) * fade_map[:, np.newaxis]).astype(self.config.dtype)

                # Auto-stop logic:
                # If fade finished (NONE) AND volume is effectively 0, stop playback
                if self._fade_state == FadeState.NONE and self._fade_target_volume <= 0.001:
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

    @abstractmethod
    def _do_seek(self, position: float) -> None:
        """Hook for subclasses to implement seeking.

        Called with the lock held.

        Args:
            position: Position in seconds
        """
        raise NotImplementedError()
