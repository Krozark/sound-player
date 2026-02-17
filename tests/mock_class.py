"""Mock classes and utilities for sound-player tests.

Centralizes all test mock classes and factory functions to avoid
duplication across test modules.
"""

from unittest.mock import MagicMock

import numpy as np

from sound_player.core import FadeMixin, StatusMixin
from sound_player.core.base_sound import BaseSound
from sound_player.core.mixins import STATUS, AudioConfigMixin


class MockSound(BaseSound):
    """Concrete implementation of BaseSound for testing.

    Supports two modes:
    - filepath mode: pass a string filepath (default "test.ogg") for testing BaseSound behavior
    - data mode: pass a numpy array for controlled audio output (mixer/layer tests)
    """

    def __init__(self, filepath_or_data="test.ogg", config=None, loop=None, volume=1.0):
        if isinstance(filepath_or_data, np.ndarray):
            self._mock_data = filepath_or_data.copy()
            filepath = "mock_data"
        else:
            self._mock_data = None
            filepath = filepath_or_data

        super().__init__(filepath, loop, config=config, volume=volume)
        self.do_play_called = False
        self.do_pause_called = False
        self.do_stop_called = False

    def _do_play(self):
        self.do_play_called = True

    def _do_pause(self):
        self.do_pause_called = True

    def _do_stop(self):
        self.do_stop_called = True

    def _do_seek(self, position=0):
        pass

    def _do_get_next_chunk(self, size):
        if self._mock_data is None or self._mock_data.shape[0] == 0:
            return None
        if self._mock_data.shape[0] < size:
            pad_width = size - self._mock_data.shape[0]
            result = np.pad(self._mock_data, ((0, pad_width), (0, 0)), mode="constant")
            ncols = self._mock_data.shape[1]
            self._mock_data = np.empty((0, ncols), dtype=self._mock_data.dtype)
        else:
            result = self._mock_data[:size]
            self._mock_data = self._mock_data[size:]
        return result


class ConcreteStatusMixin(StatusMixin):
    """Concrete implementation of StatusMixin for testing."""

    def _do_play(self):
        pass

    def _do_pause(self):
        pass

    def _do_stop(self):
        pass


class ConcreteFadeMixin(StatusMixin, AudioConfigMixin, FadeMixin):
    """Concrete implementation of FadeMixin for testing."""

    def _do_play(self):
        pass

    def _do_pause(self):
        pass

    def _do_stop(self):
        pass


class MockOwner:
    """Mock owner for AudioMixer testing (provides config and volume delegation)."""

    def __init__(self, config, volume=1.0):
        self._config = config
        self._volume = volume

    @property
    def config(self):
        return self._config

    @property
    def volume(self):
        return self._volume

    def set_volume(self, volume):
        self._volume = max(0.0, min(1.0, volume))


def create_mock_sound(status=STATUS.STOPPED, loop=None, volume=None):
    """Create a MagicMock configured to behave like a BaseSound instance.

    Uses unittest.mock.MagicMock for lightweight sound mocking in tests
    that don't need real audio data (e.g., queue management, playback control).

    Args:
        status: Initial status for the mock sound
        loop: Loop value (_loop attribute)
        volume: Volume value (_volume attribute)
    """
    sound = MagicMock()
    sound._loop = loop
    sound._volume = volume
    sound.status.return_value = status
    sound.is_fading = False
    return sound
