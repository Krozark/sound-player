"""Tests for BaseSound class."""

import pytest

from sound_player.core.mixins import STATUS

from .mock_class import MockSound


class TestBaseSoundInit:
    """Tests for BaseSound initialization."""

    def test_initialization(self):
        """Test BaseSound initializes correctly."""
        sound = MockSound("test.ogg")
        assert sound._filepath == "test.ogg"
        assert sound._loop is None
        assert sound._volume == 1.0
        assert sound.status() == STATUS.STOPPED

    def test_initialization_with_loop(self):
        """Test BaseSound with loop parameter."""
        sound = MockSound("test.ogg", loop=3)
        assert sound._loop == 3

    def test_initialization_with_volume(self):
        """Test BaseSound with volume parameter."""
        sound = MockSound("test.ogg", volume=0.75)
        assert sound._volume == 0.75

    def test_initialization_with_all_parameters(self):
        """Test BaseSound with all parameters."""
        sound = MockSound("test.ogg", loop=-1, volume=0.5)
        assert sound._filepath == "test.ogg"
        assert sound._loop == -1
        assert sound._volume == 0.5


class TestBaseSoundSetLoop:
    """Tests for set_loop method."""

    def test_set_loop(self):
        """Test set_loop updates the loop value."""
        sound = MockSound("test.ogg")
        sound.set_loop(5)
        assert sound._loop == 5

    def test_set_loop_infinite(self):
        """Test set_loop with -1 for infinite loop."""
        sound = MockSound("test.ogg")
        sound.set_loop(-1)
        assert sound._loop == -1

    def test_set_loop_zero(self):
        """Test set_loop with 0."""
        sound = MockSound("test.ogg")
        sound.set_loop(0)
        assert sound._loop == 0


class TestBaseSoundSetVolume:
    """Tests for set_volume method."""

    def test_set_volume(self):
        """Test set_volume updates the volume value."""
        sound = MockSound("test.ogg")
        sound.set_volume(0.8)
        assert sound._volume == 0.8

    def test_set_volume_zero(self):
        """Test set_volume with 0.0 (mute)."""
        sound = MockSound("test.ogg")
        sound.set_volume(0.0)
        assert sound._volume == 0.0

    def test_set_volume_max(self):
        """Test set_volume with 1.0 (max)."""
        sound = MockSound("test.ogg")
        sound.set_volume(1.0)
        assert sound._volume == 1.0


class TestBaseSoundPlay:
    """Tests for play method."""

    def test_play_from_stopped(self):
        """Test play from STOPPED status."""
        sound = MockSound("test.ogg")
        sound.play()
        assert sound.status() == STATUS.PLAYING
        assert sound.do_play_called is True

    def test_play_from_paused(self):
        """Test play from PAUSED status."""
        sound = MockSound("test.ogg")
        sound.play()
        sound.pause()
        sound.play()
        assert sound.status() == STATUS.PLAYING

    def test_play_when_playing(self):
        """Test play when already PLAYING doesn't call _do_play again."""
        sound = MockSound("test.ogg")
        sound.play()
        sound.do_play_called = False
        sound.play()
        assert sound.do_play_called is False
        assert sound.status() == STATUS.PLAYING

    def test_play_from_error_state_raises(self):
        """Test play from ERROR state raises exception."""
        sound = MockSound("test.ogg")
        sound._status = STATUS.ERROR
        with pytest.raises(Exception, match=""):
            sound.play()


class TestBaseSoundPause:
    """Tests for pause method."""

    def test_pause_from_playing(self):
        """Test pause from PLAYING status."""
        sound = MockSound("test.ogg")
        sound.play()
        sound.pause()
        assert sound.status() == STATUS.PAUSED
        assert sound.do_pause_called is True

    def test_pause_when_paused(self):
        """Test pause when already PAUSED doesn't call _do_pause again."""
        sound = MockSound("test.ogg")
        sound.play()
        sound.pause()
        sound.do_pause_called = False
        sound.pause()
        assert sound.do_pause_called is False
        assert sound.status() == STATUS.PAUSED

    def test_pause_from_stopped_raises(self):
        """Test pause from STOPPED status raises exception."""
        sound = MockSound("test.ogg")
        with pytest.raises(Exception, match=""):
            sound.pause()

    def test_pause_from_error_raises(self):
        """Test pause from ERROR status raises exception."""
        sound = MockSound("test.ogg")
        sound._status = STATUS.ERROR
        with pytest.raises(Exception, match=""):
            sound.pause()


class TestBaseSoundStop:
    """Tests for stop method."""

    def test_stop_from_playing(self):
        """Test stop from PLAYING status."""
        sound = MockSound("test.ogg")
        sound.play()
        sound.stop()
        assert sound.status() == STATUS.STOPPED
        assert sound.do_stop_called is True

    def test_stop_from_paused(self):
        """Test stop from PAUSED status."""
        sound = MockSound("test.ogg")
        sound.play()
        sound.pause()
        sound.stop()
        assert sound.status() == STATUS.STOPPED
        assert sound.do_stop_called is True

    def test_stop_when_stopped(self):
        """Test stop when already STOPPED doesn't call _do_stop again."""
        sound = MockSound("test.ogg")
        sound.stop()
        assert sound.status() == STATUS.STOPPED

    def test_stop_from_error_raises(self):
        """Test stop from ERROR status raises exception."""
        sound = MockSound("test.ogg")
        sound._status = STATUS.ERROR
        with pytest.raises(Exception, match=""):
            sound.stop()


class TestBaseSoundWait:
    """Tests for wait method."""

    def test_wait_when_stopped_returns_immediately(self):
        """Test wait returns immediately when status is STOPPED."""
        sound = MockSound("test.ogg")
        sound.wait()  # Should return immediately

    def test_wait_with_timeout(self):
        """Test wait with timeout parameter."""
        import time

        sound = MockSound("test.ogg")
        start = time.time()
        sound.wait(timeout=0.1)
        elapsed = time.time() - start
        # Should return very quickly since status is STOPPED
        assert elapsed < 0.2

    def test_wait_waits_until_stopped(self):
        """Test wait waits until sound is stopped."""
        import time

        sound = MockSound("test.ogg")
        sound.play()

        # Stop the sound after a short delay in a separate thread
        def stop_after_delay():
            time.sleep(0.1)
            sound.stop()

        import threading

        thread = threading.Thread(target=stop_after_delay)
        thread.start()

        start = time.time()
        sound.wait()
        elapsed = time.time() - start

        thread.join()

        # Should have waited approximately 0.1 seconds
        assert 0.05 < elapsed < 0.3


class TestBaseSoundLifecycleCallbacks:
    """Tests for on_start and on_end lifecycle callbacks."""

    def test_on_start_called_when_play(self):
        calls = []
        sound = MockSound("test.ogg", on_start=lambda: calls.append("start"))
        sound.play()
        assert calls == ["start"]

    def test_on_start_not_called_before_play(self):
        calls = []
        MockSound("test.ogg", on_start=lambda: calls.append("start"))
        assert calls == []

    def test_on_start_fires_only_once(self):
        calls = []
        sound = MockSound("test.ogg", on_start=lambda: calls.append("start"))
        sound.play()
        sound.pause()
        sound.play()
        assert calls == ["start"]

    def test_on_end_called_when_stop(self):
        calls = []
        sound = MockSound("test.ogg", on_end=lambda: calls.append("end"))
        sound.play()
        sound.stop()
        assert calls == ["end"]

    def test_on_end_not_called_without_prior_play(self):
        calls = []
        sound = MockSound("test.ogg", on_end=lambda: calls.append("end"))
        sound.stop()
        assert calls == []

    def test_on_end_fires_only_once(self):
        calls = []
        sound = MockSound("test.ogg", on_end=lambda: calls.append("end"))
        sound.play()
        sound.stop()
        sound._fire_on_end()
        assert calls == ["end"]

    def test_on_start_and_on_end_both_fire(self):
        calls = []
        sound = MockSound(
            "test.ogg",
            on_start=lambda: calls.append("start"),
            on_end=lambda: calls.append("end"),
        )
        sound.play()
        sound.stop()
        assert calls == ["start", "end"]

    def test_no_callbacks_is_fine(self):
        sound = MockSound("test.ogg")
        sound.play()
        sound.stop()
        assert sound.status().name == "STOPPED"

    def test_fire_on_end_without_play_is_noop(self):
        calls = []
        sound = MockSound("test.ogg", on_end=lambda: calls.append("end"))
        sound._fire_on_end()
        assert calls == []

    def test_on_end_not_fired_if_on_start_raised(self):
        end_calls = []

        def bad_on_start():
            raise RuntimeError("on_start failed")

        sound = MockSound("test.ogg", on_start=bad_on_start, on_end=lambda: end_calls.append("end"))
        with pytest.raises(RuntimeError):
            sound.play()
        sound._fire_on_end()
        assert end_calls == []
