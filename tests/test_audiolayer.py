"""Tests for AudioLayer class."""

import time
from collections import deque

import pytest

from sound_player.audiolayer import AudioLayer
from sound_player.core.mixins import STATUS

from .mock_class import create_mock_sound


class TestAudioLayerInit:
    """Tests for AudioLayer initialization."""

    def test_default_initialization(self):
        """Test AudioLayer with default parameters."""
        layer = AudioLayer()
        assert layer._concurrency == 1
        assert layer._replace_on_add is False
        assert layer._loop is None
        assert layer.volume == 1.0
        assert layer._queue_waiting == deque()
        assert layer._queue_current == []
        assert layer._thread is None
        assert layer.status() == STATUS.STOPPED

    def test_initialization_with_parameters(self):
        """Test AudioLayer with custom parameters."""
        layer = AudioLayer(concurrency=3, replace=True, loop=5, volume=0.5)
        assert layer._concurrency == 3
        assert layer._replace_on_add is True
        assert layer._loop == 5
        assert layer.volume == 0.5


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
        layer.set_loop(3)
        assert layer._loop == 3

    def test_set_loop_infinite_requires_replace(self):
        """Test that loop=-1 raises ValueError when replace=False."""
        layer = AudioLayer(replace=False)
        with pytest.raises(ValueError):
            layer.set_loop(-1)

    def test_set_loop_infinite_allowed_with_replace(self):
        """Test that loop=-1 is allowed when replace=True."""
        layer = AudioLayer(replace=True)
        layer.set_loop(-1)
        assert layer._loop == -1

    def test_set_volume(self):
        """Test set_volume method."""
        layer = AudioLayer()
        layer.set_volume(0.75)
        assert layer.volume == 0.75


class TestAudioLayerEnqueue:
    """Tests for AudioLayer enqueue method."""

    def test_enqueue_adds_to_waiting_queue(self, mock_sound):
        """Test that enqueue adds sound to waiting queue."""
        layer = AudioLayer()
        sound = mock_sound()
        layer.enqueue(sound)
        assert len(layer._queue_waiting) == 1
        assert layer._queue_waiting[0][0] == sound

    def test_enqueue_preserves_sound_loop_when_layer_has_no_default(self, mock_sound):
        """Test that enqueue does not override sound loop when layer loop is None."""
        layer = AudioLayer()
        sound = mock_sound(loop=3)
        layer.enqueue(sound)
        sound.set_loop.assert_not_called()

    def test_enqueue_applies_loop_from_layer(self, mock_sound):
        """Test that enqueue applies loop from layer when layer loop is set."""
        layer = AudioLayer(loop=2)
        sound = mock_sound(loop=None)
        layer.enqueue(sound)
        sound.set_loop.assert_called_once_with(2)

    def test_enqueue_preserves_sound_volume(self, mock_sound):
        """Test that enqueue does not override sound volume (layer volume applies at mixer level)."""
        layer = AudioLayer()
        sound = mock_sound(volume=0.6)
        layer.enqueue(sound)
        sound.set_volume.assert_not_called()

    def test_enqueue_layer_volume_applies_at_mixer_level(self, mock_sound):
        """Test that layer volume is applied at mixer level, not overriding sound volume."""
        layer = AudioLayer(volume=0.8)
        sound = mock_sound(volume=0.5)
        layer.enqueue(sound)
        # Sound volume should not be changed by layer — layer volume applies in mixer
        sound.set_volume.assert_not_called()
        # Layer volume should be accessible
        assert layer.volume == 0.8

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
        layer.play()  # Need to be playing to pause
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

    def test_stop_stops_current_sounds(self):
        """Test that stop stops all current sounds."""
        layer = AudioLayer()
        layer.play()  # Set status to PLAYING

        # Create sounds that return PLAYING status so thread doesn't remove them
        sound1 = create_mock_sound(status=STATUS.PLAYING)
        sound2 = create_mock_sound(status=STATUS.PLAYING)

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

    def test_thread_starts_sounds_from_waiting(self, mock_sound, wait_for_thread_stop):
        """Test that thread moves sounds from waiting to current queue."""
        layer = AudioLayer(concurrency=2)

        sound1 = mock_sound(status=STATUS.PLAYING)
        sound2 = mock_sound(status=STATUS.PLAYING)

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

    def test_thread_respects_concurrency_limit(self, mock_sound, wait_for_thread_stop):
        """Test that thread respects concurrency limit."""
        layer = AudioLayer(concurrency=2)

        sounds = [mock_sound(status=STATUS.PLAYING) for _ in range(4)]

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

    def test_thread_removes_stopped_sounds(self, mock_sound, wait_for_thread_stop):
        """Test that thread removes stopped sounds from current queue."""
        layer = AudioLayer(concurrency=3)

        sound1 = mock_sound(status=STATUS.PLAYING)
        sound2 = mock_sound(status=STATUS.STOPPED)  # Already stopped
        sound3 = mock_sound(status=STATUS.PLAYING)

        layer._queue_current.extend([sound1, sound2, sound3])
        layer.play()

        # Wait for thread to process
        time.sleep(0.3)

        assert len(layer._queue_current) == 2
        assert sound2 not in layer._queue_current

        # Cleanup
        layer.stop()
        wait_for_thread_stop(layer)

    def test_replace_mode_stops_oldest_sounds(self, mock_sound, wait_for_thread_stop):
        """Test that replace mode stops oldest sounds when limit exceeded."""
        layer = AudioLayer(concurrency=2, replace=True)

        sound1 = mock_sound(status=STATUS.PLAYING)
        sound2 = mock_sound(status=STATUS.PLAYING)
        sound3 = mock_sound(status=STATUS.STOPPED)
        sound4 = mock_sound(status=STATUS.STOPPED)

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

    def test_thread_starts_next_sound_after_previous_stops(self, mock_sound, wait_for_thread_stop):
        """Test that thread starts next sound after previous one stops."""
        layer = AudioLayer(concurrency=1)

        # Start as PLAYING, will change to STOPPED later
        sound1 = mock_sound(status=STATUS.PLAYING)
        sound2 = mock_sound(status=STATUS.PLAYING)

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


class TestAudioLayerDelay:
    """Tests for per-sound delay in AudioLayer.enqueue."""

    def test_enqueue_stores_delay(self, mock_sound):
        """Test that enqueue stores the delay in the waiting queue tuple."""
        layer = AudioLayer()
        sound = mock_sound()
        layer.enqueue(sound, delay=2.5)
        assert len(layer._queue_waiting) == 1
        stored_sound, _, stored_delay = layer._queue_waiting[0]
        assert stored_sound is sound
        assert stored_delay == 2.5

    def test_enqueue_no_delay_stores_none(self, mock_sound):
        """Test that enqueue without delay stores None."""
        layer = AudioLayer()
        sound = mock_sound()
        layer.enqueue(sound)
        _, _, stored_delay = layer._queue_waiting[0]
        assert stored_delay is None

    def test_sound_without_delay_starts_immediately(self, mock_sound, wait_for_thread_stop):
        """Test that a sound with no delay starts as soon as a slot is available."""
        layer = AudioLayer(concurrency=1)
        sound = mock_sound(status=STATUS.PLAYING)
        layer.enqueue(sound)
        layer.play()

        time.sleep(0.2)
        assert sound in layer._queue_current

        layer.stop()
        wait_for_thread_stop(layer)

    def test_sound_with_elapsed_delay_starts(self, mock_sound, wait_for_thread_stop):
        """Test that a sound with an already-elapsed delay starts immediately."""
        layer = AudioLayer(concurrency=1)
        sound = mock_sound(status=STATUS.PLAYING)
        layer.enqueue(sound, delay=0.0)
        layer.play()

        time.sleep(0.2)
        assert sound in layer._queue_current

        layer.stop()
        wait_for_thread_stop(layer)

    def test_sound_with_future_delay_is_skipped(self, mock_sound, wait_for_thread_stop):
        """Test that a sound with a large delay is not started before the delay elapses."""
        layer = AudioLayer(concurrency=1)
        sound = mock_sound(status=STATUS.PLAYING)
        layer.enqueue(sound, delay=60.0)  # 60 seconds — will never elapse in test
        layer.play()

        time.sleep(0.3)
        assert sound not in layer._queue_current
        assert len(layer._queue_waiting) == 1

        layer.stop()
        wait_for_thread_stop(layer)

    def test_later_sound_plays_while_earlier_is_delayed(self, mock_sound, wait_for_thread_stop):
        """Test that a sound enqueued after a delayed sound can start if the slot is free."""
        layer = AudioLayer(concurrency=1)
        sound1 = mock_sound(status=STATUS.PLAYING)  # long delay — never ready
        sound2 = mock_sound(status=STATUS.PLAYING)  # no delay — ready immediately

        layer.enqueue(sound1, delay=60.0)
        layer.enqueue(sound2)
        layer.play()

        time.sleep(0.3)

        # sound1 must still be waiting (delay not elapsed)
        assert sound1 not in layer._queue_current
        # sound2 should have started despite being enqueued after sound1
        assert sound2 in layer._queue_current

        layer.stop()
        wait_for_thread_stop(layer)

    def test_delayed_sound_starts_after_delay_elapses(self, mock_sound, wait_for_thread_stop):
        """Test that a delayed sound starts once its delay has elapsed."""
        layer = AudioLayer(concurrency=1)
        sound = mock_sound(status=STATUS.PLAYING)
        layer.enqueue(sound, delay=0.25)
        layer.play()

        # Not yet started — delay hasn't elapsed
        time.sleep(0.1)
        assert sound not in layer._queue_current

        # After delay has elapsed the thread should promote it
        time.sleep(0.4)
        assert sound in layer._queue_current

        layer.stop()
        wait_for_thread_stop(layer)

    def test_fifo_order_among_ready_sounds(self, mock_sound, wait_for_thread_stop):
        """Test that ready sounds are still promoted in FIFO order."""
        layer = AudioLayer(concurrency=1)
        sound1 = mock_sound(status=STATUS.PLAYING)
        sound2 = mock_sound(status=STATUS.PLAYING)

        layer.enqueue(sound1)  # both ready immediately
        layer.enqueue(sound2)
        layer.play()

        time.sleep(0.2)

        # First sound enqueued should be the one currently playing
        assert sound1 in layer._queue_current
        assert sound2 not in layer._queue_current

        layer.stop()
        wait_for_thread_stop(layer)
