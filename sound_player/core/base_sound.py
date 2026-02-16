"""Base sound class and PCM buffer interface for the sound player library."""

import logging
import threading
import time

import numpy as np

from .audio_config import AudioConfig
from .state import STATUS, StatusObject

logger = logging.getLogger(__name__)

__all__ = [
    "BaseSound",
]


class BaseSound(StatusObject):
    def __init__(self, filepath, config: AudioConfig | None = None, loop=None, volume=None):
        super().__init__()
        self._filepath = filepath
        self._config = config or AudioConfig()
        self._loop = loop
        self._volume = volume
        self._lock = threading.Lock()

    def set_loop(self, loop):
        logger.debug("BaseSound.set_loop(%s)", loop)
        with self._lock:
            self._loop = loop

    def set_volume(self, volume: int):
        logger.debug("BaseSound.set_volume(%s)", volume)
        with self._lock:
            self._volume = volume

    def play(self):
        logger.debug("BaseSound.play()")
        with self._lock:
            if self._status == STATUS.PLAYING:
                return
            elif self._status not in (STATUS.STOPPED, STATUS.PAUSED):
                raise Exception()

            self._do_play()
            super().play()

    def pause(self):
        logger.debug("BaseSound.pause()")
        with self._lock:
            if self._status == STATUS.PAUSED:
                return
            elif self._status != STATUS.PLAYING:
                raise Exception()

            self._do_pause()
            super().pause()

    def stop(self):
        logger.debug("BaseSound.stop()")
        with self._lock:
            if self._status == STATUS.STOPPED:
                return
            elif self._status not in (STATUS.PLAYING, STATUS.PAUSED):
                raise Exception()

            self._do_stop()
            super().stop()

    def wait(self, timeout=None):
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
        logger.debug("BaseSound.get_next_chunk(%s)", size)

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
        return self._config.sample_rate

    def get_channels(self) -> int:
        """Return the number of audio channels.

        Returns:
            Number of channels (1=mono, 2=stereo)
        """
        return self._config.channels

    def get_audio_config(self) -> AudioConfig:
        """Return the audio configuration for this sound.

        Returns:
            AudioConfig instance describing the audio format
        """
        return self._config

    def seek(self, position: float) -> None:
        """Seek to position in seconds.

        Args:
            position: Position in seconds
        """
        logger.debug("BaseSound.seek(%s)", position)
        with self._lock:
            self._do_seek(position)

    # Platform-specific implementations

    def _do_play(self):
        raise NotImplementedError()

    def _do_pause(self):
        raise NotImplementedError()

    def _do_stop(self):
        raise NotImplementedError()

    def _do_seek(self, position: float) -> None:
        """Seek to position in seconds.

        Subclasses can override this to implement seeking.
        Called with the lock held.

        Args:
            position: Position in seconds
        """
        pass
