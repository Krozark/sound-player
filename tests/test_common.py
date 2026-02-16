"""Tests for common.py - STATUS enum and StatusObject class."""

from sound_player.common import STATUS, StatusObject


class TestStatusEnum:
    """Tests for the STATUS enum."""

    def test_status_values(self):
        """Test that STATUS enum has correct values."""
        assert STATUS.ERROR.value == -1
        assert STATUS.STOPPED.value == 1
        assert STATUS.PLAYING.value == 2
        assert STATUS.PAUSED.value == 3

    def test_status_equality(self):
        """Test STATUS enum equality."""
        assert STATUS.PLAYING == STATUS.PLAYING
        assert STATUS.PLAYING != STATUS.PAUSED
        assert STATUS.STOPPED != STATUS.PLAYING


class TestStatusObject:
    """Tests for the StatusObject base class."""

    def test_initial_status_is_stopped(self):
        """Test that StatusObject initializes with STOPPED status."""
        obj = StatusObject()
        assert obj.status() == STATUS.STOPPED

    def test_play_changes_status(self):
        """Test that play() changes status to PLAYING."""
        obj = StatusObject()
        obj.play()
        assert obj.status() == STATUS.PLAYING

    def test_pause_changes_status(self):
        """Test that pause() changes status to PAUSED."""
        obj = StatusObject()
        obj.play()
        obj.pause()
        assert obj.status() == STATUS.PAUSED

    def test_stop_changes_status(self):
        """Test that stop() changes status to STOPPED."""
        obj = StatusObject()
        obj.play()
        obj.stop()
        assert obj.status() == STATUS.STOPPED

    def test_stop_from_paused(self):
        """Test that stop() works from PAUSED status."""
        obj = StatusObject()
        obj.play()
        obj.pause()
        obj.stop()
        assert obj.status() == STATUS.STOPPED

    def test_multiple_play_calls(self):
        """Test that multiple play() calls result in PLAYING status."""
        obj = StatusObject()
        obj.play()
        obj.play()
        obj.play()
        assert obj.status() == STATUS.PLAYING
