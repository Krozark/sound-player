"""Test configuration and fixtures for sound-player tests."""

import pytest

from sound_player.core.mixins import STATUS

from .mock_class import create_mock_sound


@pytest.fixture
def mock_sound():
    """Create a mock sound factory for testing.

    Returns a factory function that creates MagicMock-based sound objects
    via create_mock_sound from mock_class.
    """

    def _create_sound(status=STATUS.STOPPED, loop=None, volume=None):
        return create_mock_sound(status=status, loop=loop, volume=volume)

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
