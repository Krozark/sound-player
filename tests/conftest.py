"""Test configuration and fixtures for sound-player tests."""

from unittest.mock import MagicMock

import pytest

from sound_player.core.mixins import STATUS


@pytest.fixture
def mock_sound():
    """Create a mock sound object for testing."""

    def _create_sound(status=STATUS.STOPPED, loop=None, volume=None):
        sound = MagicMock()
        sound._loop = loop
        sound._volume = volume
        sound.status.return_value = status
        sound.play = MagicMock()
        sound.pause = MagicMock()
        sound.stop = MagicMock()
        sound.set_loop = MagicMock()
        sound.set_volume = MagicMock()
        return sound

    return _create_sound


@pytest.fixture
def wait_for_thread_stop():
    """Helper to wait for the audio layer thread to stop."""

    def _wait(audio_layer, timeout=1.0):
        import time

        start = time.time()
        while audio_layer._thread is not None and (time.time() - start) < timeout:
            time.sleep(0.05)

    return _wait
