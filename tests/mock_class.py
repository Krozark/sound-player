import numpy as np

from sound_player.core.audio_config import AudioConfig
from sound_player.core.mixins import STATUS


class MockSound:
    """Mock sound class for testing."""

    def __init__(self, data, status=STATUS.PLAYING, volume=1.0):
        self._data = data
        self._status = status
        self._volume = volume
        self._loop = None

    @property
    def volume(self):
        return self._volume

    def get_next_chunk(self, size):
        if self._status != STATUS.PLAYING:
            return None
        if len(self._data) == 0:
            return None
        if len(self._data) < size:
            result = np.pad(self._data, ((0, size - len(self._data)), (0, 0)), mode="constant")
            self._data = np.array([])
        else:
            result = self._data[:size]
            self._data = self._data[size:]
        return result

    def get_sample_rate(self):
        return 44100

    def get_channels(self):
        return 2

    @property
    def config(self):
        return AudioConfig()

    def status(self):
        return self._status

    def play(self):
        self._status = STATUS.PLAYING

    def pause(self):
        self._status = STATUS.PAUSED

    def stop(self):
        self._status = STATUS.STOPPED

    def _do_seek(self):
        pass
