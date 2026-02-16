"""Tests for AudioLayer class."""

import time
from unittest.mock import MagicMock

from sound_player.audiolayer import AudioLayer
from sound_player.core.state import STATUS


class TestAudioLayerInit:
    """Tests for AudioLayer initialization."""

    def test_default_initialization(self):
        """Test AudioLayer with default parameters."""
        layer = AudioLayer()
        assert layer._concurrency == 1
        assert layer._replace_on_add is False
        assert layer._loop is None
        assert layer._volume == 100
        assert layer._queue_waiting == []
        assert layer._queue_current == []
        assert layer._thread is None
        assert layer.status() == STATUS.STOPPED

    def test_initialization_with_parameters(self):
        """Test AudioLayer with custom parameters."""
        layer = AudioLayer(concurrency=3, replace=True, loop=5, volume=50)
        assert layer._concurrency == 3
        assert layer._replace_on_add is True
        assert layer._loop == 5
        assert layer._volume == 50


class TestAudioLayerSetters:
    """Tests for AudioLayer setter methods."""

    def test_set_concurrency(self):
        """Test set_concurrency method."""
        layer = AudioLayer()
        layer.set_concurrency(5)
        assert layer._concurrency == 5

    def test_set_replace(self):
        """Test set_replace method."""
        layer = AudioLayer()
        layer.set_replace(True)
        assert layer._replace_on_add is True

    def test_set_loop(self):
        """Test set_loop method."""
        layer = AudioLayer()
        layer.set_loop(-1)
        assert layer._loop == -1

    def test_set_volume(self):
        """Test set_volume method."""
        layer = AudioLayer()
        layer.set_volume(75)
        assert layer._volume == 75


class TestAudioLayerEnqueue:
    """Tests for AudioLayer enqueue method."""

    def test_enqueue_adds_to_waiting_queue(self, mock_sound):
        """Test that enqueue adds sound to waiting queue."""
        layer = AudioLayer()
        sound = mock_sound()
        layer.enqueue(sound)
        assert len(layer._queue_waiting) == 1
        assert layer._queue_waiting[0] == sound

    def test_enqueue_applies_loop_from_sound(self, mock_sound):
        """Test that enqueue applies loop from sound if set."""
        layer = AudioLayer()
        sound = mock_sound(loop=3)
        layer.enqueue(sound)
        sound.set_loop.assert_called_once_with(3)

    def test_enqueue_applies_loop_from_layer(self, mock_sound):
        """Test that enqueue applies loop from layer if sound loop not set."""
        layer = AudioLayer(loop=2)
        sound = mock_sound(loop=None)
        layer.enqueue(sound)
        sound.set_loop.assert_called_once_with(2)

    def test_enqueue_applies_volume_from_sound(self, mock_sound):
        """Test that enqueue applies volume from sound if set."""
        layer = AudioLayer()
        sound = mock_sound(volume=60)
        layer.enqueue(sound)
        sound.set_volume.assert_called_once_with(60)

    def test_enqueue_applies_volume_from_layer(self, mock_sound):
        """Test that enqueue applies volume from layer if sound volume not set."""
        layer = AudioLayer(volume=80)
        sound = mock_sound(volume=None)
        layer.enqueue(sound)
        sound.set_volume.assert_called_once_with(80)

    def test_enqueue_multiple_sounds(self, mock_sound):
        """Test enqueueing multiple sounds."""
        layer = AudioLayer()
        sound1 = mock_sound()
        sound2 = mock_sound()
        layer.enqueue(sound1)
        layer.enqueue(sound2)
        assert len(layer._queue_waiting) == 2


class TestAudioLayerClear:
    """Tests for AudioLayer clear method."""

    def test_clear_waiting_queue(self, mock_sound):
        """Test that clear empties the waiting queue."""
        layer = AudioLayer()
        sound = mock_sound()
        layer.enqueue(sound)
        layer.clear()
        assert len(layer._queue_waiting) == 0

    def test_clear_current_queue(self, mock_sound):
        """Test that clear empties the current queue."""
        layer = AudioLayer()
        sound = mock_sound()
        layer._queue_current.append(sound)
        layer.clear()
        assert len(layer._queue_current) == 0


class TestAudioLayerPlay:
    """Tests for AudioLayer play method."""

    def test_play_changes_status(self):
        """Test that play changes status to PLAYING."""
        layer = AudioLayer()
        layer.play()
        assert layer.status() == STATUS.PLAYING

    def test_play_creates_thread(self):
        """Test that play creates a daemon thread."""
        layer = AudioLayer()
        layer.play()
        assert layer._thread is not None
        assert layer._thread.daemon is True

        # Cleanup
        layer.stop()
        time.sleep(0.2)

    def test_play_reuses_existing_thread(self, wait_for_thread_stop):
        """Test that play reuses existing thread."""
        layer = AudioLayer()
        layer.play()
        first_thread = layer._thread
        layer.play()
        assert layer._thread == first_thread

        # Cleanup
        layer.stop()
        wait_for_thread_stop(layer)

    def test_play_starts_current_sounds(self, mock_sound):
        """Test that play calls play on current sounds."""
        layer = AudioLayer()
        sound = mock_sound(status=STATUS.PAUSED)
        layer._queue_current.append(sound)
        layer.play()

        # Give thread time to process
        time.sleep(0.2)
        sound.play.assert_called()

        # Cleanup
        layer.stop()
        time.sleep(0.2)


class TestAudioLayerPause:
    """Tests for AudioLayer pause method."""

    def test_pause_changes_status(self):
        """Test that pause changes status to PAUSED."""
        layer = AudioLayer()
        layer.play()
        layer.pause()
        assert layer.status() == STATUS.PAUSED

    def test_pause_pauses_current_sounds(self, mock_sound):
        """Test that pause pauses all current sounds."""
        layer = AudioLayer()
        sound1 = mock_sound()
        sound2 = mock_sound()
        layer._queue_current.extend([sound1, sound2])
        layer.pause()
        sound1.pause.assert_called_once()
        sound2.pause.assert_called_once()


class TestAudioLayerStop:
    """Tests for AudioLayer stop method."""

    def test_stop_changes_status(self):
        """Test that stop changes status to STOPPED."""
        layer = AudioLayer()
        layer.play()
        layer.stop()
        assert layer.status() == STATUS.STOPPED

    def test_stop_stops_current_sounds(self, mock_sound):
        """Test that stop stops all current sounds."""

        layer = AudioLayer()
        layer.play()  # Set status to PLAYING

        # Create sounds that return PLAYING status so thread doesn't remove them
        sound1 = MagicMock()
        sound1._loop = None
        sound1._volume = None
        sound1.status.return_value = STATUS.PLAYING
        sound1.stop = MagicMock()

        sound2 = MagicMock()
        sound2._loop = None
        sound2._volume = None
        sound2.status.return_value = STATUS.PLAYING
        sound2.stop = MagicMock()

        layer._queue_current.extend([sound1, sound2])
        layer.stop()

        sound1.stop.assert_called_once()
        sound2.stop.assert_called_once()

    def test_stop_clears_queues(self, mock_sound):
        """Test that stop clears both queues."""
        layer = AudioLayer()
        sound = mock_sound()
        layer.enqueue(sound)
        layer._queue_current.append(sound)
        layer.play()
        layer.stop()
        time.sleep(0.3)  # Wait for thread to finish

        assert len(layer._queue_waiting) == 0
        assert len(layer._queue_current) == 0

    def test_stop_when_already_stopped(self):
        """Test that stop when already stopped doesn't cause issues."""
        layer = AudioLayer()
        layer.stop()
        assert layer.status() == STATUS.STOPPED
        assert len(layer._queue_waiting) == 0
        assert len(layer._queue_current) == 0


class TestAudioLayerThreading:
    """Tests for AudioLayer threading behavior."""

    def test_thread_starts_sounds_from_waiting(self, wait_for_thread_stop):
        """Test that thread moves sounds from waiting to current queue."""
        # Create real mock sounds that start PLAYING after play() is called

        layer = AudioLayer(concurrency=2)

        sound1 = MagicMock()
        sound1._loop = None
        sound1._volume = None
        sound1.status.return_value = STATUS.PLAYING  # Will be PLAYING after play()
        sound1.play = MagicMock()
        sound1.stop = MagicMock()
        sound1.set_loop = MagicMock()
        sound1.set_volume = MagicMock()

        sound2 = MagicMock()
        sound2._loop = None
        sound2._volume = None
        sound2.status.return_value = STATUS.PLAYING
        sound2.play = MagicMock()
        sound2.stop = MagicMock()
        sound2.set_loop = MagicMock()
        sound2.set_volume = MagicMock()

        layer.enqueue(sound1)
        layer.enqueue(sound2)
        layer.play()

        # Wait for thread to process
        time.sleep(0.3)

        assert len(layer._queue_current) == 2
        assert len(layer._queue_waiting) == 0
        sound1.play.assert_called()
        sound2.play.assert_called()

        # Cleanup
        layer.stop()
        wait_for_thread_stop(layer)

    def test_thread_respects_concurrency_limit(self, wait_for_thread_stop):
        """Test that thread respects concurrency limit."""

        layer = AudioLayer(concurrency=2)

        sounds = []
        for _ in range(4):
            sound = MagicMock()
            sound._loop = None
            sound._volume = None
            sound.status.return_value = STATUS.PLAYING
            sound.play = MagicMock()
            sound.stop = MagicMock()
            sound.set_loop = MagicMock()
            sound.set_volume = MagicMock()
            sounds.append(sound)

        for sound in sounds:
            layer.enqueue(sound)

        layer.play()

        # Wait for thread to process
        time.sleep(0.3)

        assert len(layer._queue_current) == 2
        assert len(layer._queue_waiting) == 2

        # Cleanup
        layer.stop()
        wait_for_thread_stop(layer)

    def test_thread_removes_stopped_sounds(self, wait_for_thread_stop):
        """Test that thread removes stopped sounds from current queue."""

        layer = AudioLayer(concurrency=3)

        sound1 = MagicMock()
        sound1._loop = None
        sound1._volume = None
        sound1.status.return_value = STATUS.PLAYING
        sound1.play = MagicMock()
        sound1.stop = MagicMock()

        sound2 = MagicMock()
        sound2._loop = None
        sound2._volume = None
        sound2.status.return_value = STATUS.STOPPED  # Already stopped
        sound2.play = MagicMock()
        sound2.stop = MagicMock()

        sound3 = MagicMock()
        sound3._loop = None
        sound3._volume = None
        sound3.status.return_value = STATUS.PLAYING
        sound3.play = MagicMock()
        sound3.stop = MagicMock()

        layer._queue_current.extend([sound1, sound2, sound3])
        layer.play()

        # Wait for thread to process
        time.sleep(0.3)

        assert len(layer._queue_current) == 2
        assert sound2 not in layer._queue_current

        # Cleanup
        layer.stop()
        wait_for_thread_stop(layer)

    def test_replace_mode_stops_oldest_sounds(self, wait_for_thread_stop):
        """Test that replace mode stops oldest sounds when limit exceeded."""

        layer = AudioLayer(concurrency=2, replace=True)

        sound1 = MagicMock()
        sound1._loop = None
        sound1._volume = None
        sound1.status.return_value = STATUS.PLAYING
        sound1.play = MagicMock()
        sound1.stop = MagicMock()

        sound2 = MagicMock()
        sound2._loop = None
        sound2._volume = None
        sound2.status.return_value = STATUS.PLAYING
        sound2.play = MagicMock()
        sound2.stop = MagicMock()

        sound3 = MagicMock()
        sound3._loop = None
        sound3._volume = None
        sound3.status.return_value = STATUS.STOPPED
        sound3.play = MagicMock()
        sound3.stop = MagicMock()
        sound3.set_loop = MagicMock()
        sound3.set_volume = MagicMock()

        sound4 = MagicMock()
        sound4._loop = None
        sound4._volume = None
        sound4.status.return_value = STATUS.STOPPED
        sound4.play = MagicMock()
        sound4.stop = MagicMock()
        sound4.set_loop = MagicMock()
        sound4.set_volume = MagicMock()

        layer._queue_current.extend([sound1, sound2])
        layer.enqueue(sound3)
        layer.enqueue(sound4)

        layer.play()

        # Wait for thread to process
        time.sleep(0.3)

        # Should have stopped some sounds to make room
        assert sound1.stop.called or sound2.stop.called

        # Cleanup
        layer.stop()
        wait_for_thread_stop(layer)

    def test_thread_starts_next_sound_after_previous_stops(self, wait_for_thread_stop):
        """Test that thread starts next sound after previous one stops."""

        layer = AudioLayer(concurrency=1)

        sound1 = MagicMock()
        sound1._loop = None
        sound1._volume = None
        # Start as PLAYING, will change to STOPPED later
        sound1.status.return_value = STATUS.PLAYING
        sound1.play = MagicMock()

        sound2 = MagicMock()
        sound2._loop = None
        sound2._volume = None
        sound2.status.return_value = STATUS.PLAYING
        sound2.play = MagicMock()
        sound2.set_loop = MagicMock()
        sound2.set_volume = MagicMock()

        layer._queue_current.append(sound1)
        layer.enqueue(sound2)
        layer.play()

        # Initially only sound1 should be in current
        time.sleep(0.2)
        assert len(layer._queue_current) == 1

        # After sound1 stops, sound2 should start
        sound1.status.return_value = STATUS.STOPPED
        time.sleep(0.3)

        assert len(layer._queue_current) == 1
        assert sound2 in layer._queue_current

        # Cleanup
        layer.stop()
        wait_for_thread_stop(layer)
