"""Audio layer module for managing multiple sounds with mixing support."""

import logging
import threading
import time

import numpy as np

from .core.mixins import STATUS, AudioConfigMixin, StatusMixin
from .mixer import AudioMixer

logger = logging.getLogger(__name__)

__all__ = [
    "AudioLayer",
]


class AudioLayer(StatusMixin, AudioConfigMixin):
    """Manages a queue of sounds with support for concurrent playback and mixing.

    The AudioLayer maintains two queues:
    - _queue_waiting: Sounds waiting to be played
    - _queue_current: Sounds currently playing

    Key features:
    - concurrency: Maximum number of sounds playing simultaneously
    - replace: If True, stops old sounds when adding new ones beyond concurrency limit
    - loop: How many times sounds should be played (-1 = infinite, N = finite)
    - volume: Layer-level volume (0.0-1.0)
    - mixer: AudioMixer for mixing current sounds together
    """

    def __init__(
        self,
        concurrency=1,
        replace=False,
        loop=None,
        fade_in_duration=None,
        fade_out_duration=None,
        crossfade_duration=None,
        *args,
        **kwargs,
    ):
        """Initialize the AudioLayer.

        Args:
            concurrency: Maximum number of sounds playing simultaneously
            replace: If True, stop old sounds when limit is exceeded
            loop: Default loop count for sounds (-1 = infinite)
            fade_in_duration: Default fade-in duration for enqueued sounds (seconds)
            fade_out_duration: Default fade-out duration for enqueued sounds (seconds)
            crossfade_duration: Crossfade duration for replace mode (seconds)
            volume: Layer volume (0.0-1.0)
            config: AudioConfig for the mixer
        """
        super().__init__(*args, **kwargs)
        self._concurrency = concurrency
        self._replace_on_add = replace
        self._loop = loop
        self._fade_in_duration = fade_in_duration
        self._fade_out_duration = fade_out_duration
        self._crossfade_duration = crossfade_duration
        self._queue_waiting = []
        self._queue_current = []
        self._fading_out_sounds = []  # Sounds fading out during crossfade
        self._thread = None

        # Create mixer for this layer
        self._mixer: AudioMixer = AudioMixer(self)

    @property
    def mixer(self) -> "AudioMixer":
        """Get the AudioMixer for this layer."""
        return self._mixer

    def set_concurrency(self, concurrency):
        """Set the maximum number of concurrent sounds.

        Args:
            concurrency: Maximum number of sounds playing at once
        """
        logger.debug("AudioLayer.set_concurrency(%s)", concurrency)
        with self._lock:
            self._concurrency = concurrency

    def set_replace(self, replace):
        """Set whether to replace old sounds when limit is exceeded.

        Args:
            replace: If True, stop old sounds when adding new ones
        """
        logger.debug("AudioLayer.set_replace(%s)", replace)
        with self._lock:
            self._replace_on_add = replace

    def set_loop(self, loop):
        """Set the default loop count for sounds.

        Args:
            loop: Number of times to loop (-1 for infinite)
        """
        logger.debug("AudioLayer.set_loop(%s)", loop)
        with self._lock:
            self._loop = loop

    def set_fade_in_duration(self, duration: float) -> None:
        """Set the default fade-in duration for enqueued sounds.

        Args:
            duration: Fade-in duration in seconds (None to disable)
        """
        logger.debug("AudioLayer.set_fade_in_duration(%s)", duration)
        with self._lock:
            self._fade_in_duration = duration

    def set_fade_out_duration(self, duration: float) -> None:
        """Set the default fade-out duration for enqueued sounds.

        Args:
            duration: Fade-out duration in seconds (None to disable)
        """
        logger.debug("AudioLayer.set_fade_out_duration(%s)", duration)
        with self._lock:
            self._fade_out_duration = duration

    def set_crossfade_duration(self, duration: float) -> None:
        """Set the crossfade duration for replace mode.

        Args:
            duration: Crossfade duration in seconds (None to disable)
        """
        logger.debug("AudioLayer.set_crossfade_duration(%s)", duration)
        with self._lock:
            self._crossfade_duration = duration

    def enqueue(self, sound, fade_in=None, fade_out=None):
        """Add a sound to the waiting queue.

        Args:
            sound: The sound to enqueue
            fade_in: Override fade-in duration (None to use layer default)
            fade_out: Override fade-out duration (None to use layer default)
        """
        logger.debug("AudioLayer.enqueue(%s)", sound)
        with self._lock:
            logger.debug("enqueue %s" % sound)
            loop = sound._loop or self._loop
            volume = sound._volume or self._volume
            sound.set_loop(loop)
            sound.set_volume(volume)

            # Apply fade-in duration
            if fade_in is None:
                fade_in = self._fade_in_duration
            if fade_in is not None and fade_in > 0:
                sound.start_fade_in(fade_in, target_volume=volume)

            # Store fade-out duration for later use
            if fade_out is None:
                fade_out = self._fade_out_duration
            if fade_out is not None:
                sound._fade_out_duration = fade_out

            self._queue_waiting.append(sound)

    def clear(self):
        """Clear all queues and the mixer."""
        logger.debug("AudioLayer.clear()")
        with self._lock:
            # Stop and remove all sounds from mixer and fading list
            for sound in self._queue_current:
                self._mixer.remove_sound(sound)
                sound.stop()
            for sound in self._fading_out_sounds:
                self._mixer.remove_sound(sound)
                sound.stop()
            self._fading_out_sounds.clear()
            self._queue_waiting.clear()
            self._queue_current.clear()

    def _do_stop(self, *args, **kwargs):
        """Stop playback and clear all queues."""
        logger.debug("AudioLayer.stop()")
        with self._lock:
            self.clear()

    def _do_play(self):
        """Hook called when play status changes to PLAYING."""
        if self._thread is None:
            logger.debug("Create audio layer Thread")
            self._thread = threading.Thread(target=self._thread_task, daemon=True)
            logger.debug("Start audio layer Thread")
            self._thread.start()

        for sound in self._queue_current:
            sound.play()

    def _do_pause(self):
        """Hook called when play status changes to PAUSED."""
        for sound in self._queue_current:
            sound.pause()

    def _do_stop(self):
        """Hook called when play status changes to STOPPED."""
        self.clear()

    def get_next_chunk(self) -> np.ndarray:
        """Get the next mixed audio chunk from this layer.

        Returns:
            Mixed audio buffer from all current sounds
        """
        return self._mixer.get_next_chunk()

    def _thread_task(self):
        """Daemon thread that manages sound lifecycle.

        This thread:
        1. Removes stopped sounds from current queue
        2. Manages fading out sounds during crossfade
        3. Stops old sounds if replace mode is enabled (with or without crossfade)
        4. Moves sounds from waiting to current queue
        5. Adds/removes sounds from the mixer as they transition
        """
        logger.debug("In audio layer Thread")
        try:
            while self._status != STATUS.STOPPED:
                if self._status == STATUS.PLAYING:
                    with self._lock:
                        # Remove stopped sounds from current queue
                        i = 0
                        while i < len(self._queue_current):
                            sound_status = self._queue_current[i].status()
                            if sound_status == STATUS.STOPPED:
                                sound = self._queue_current.pop(i)
                                logger.debug("sound %s has stopped. Remove it", sound)
                                self._mixer.remove_sound(sound)
                                del sound
                            else:
                                i += 1

                        # Remove completed crossfading sounds
                        i = 0
                        while i < len(self._fading_out_sounds):
                            sound = self._fading_out_sounds[i]
                            if sound.status() == STATUS.STOPPED or not sound.is_fading():
                                self._fading_out_sounds.pop(i)
                                logger.debug("Crossfade sound %s completed. Remove it", sound)
                                self._mixer.remove_sound(sound)
                                del sound
                            else:
                                i += 1

                        # Stop sounds to make place for new ones (replace mode)
                        if self._replace_on_add:
                            place_needed = len(self._queue_current) + len(self._queue_waiting) - self._concurrency
                            if place_needed > 0 and len(self._queue_current) > 0:
                                # Check if we should use crossfade
                                use_crossfade = self._crossfade_duration is not None and self._crossfade_duration > 0

                                for i in range(0, min(len(self._queue_current), place_needed)):
                                    sound = self._queue_current[i]
                                    if use_crossfade:
                                        # Start crossfade out
                                        logger.debug(
                                            "Crossfading out sound %s to add new one.",
                                            sound,
                                        )
                                        sound.start_crossfade_out(self._crossfade_duration)
                                        self._fading_out_sounds.append(sound)
                                    else:
                                        # Immediate stop
                                        logger.debug("stopping sound %s to add new one.", sound)
                                        sound.stop()
                                        self._mixer.remove_sound(sound)

                                # Remove crossfaded sounds from current queue
                                if use_crossfade:
                                    for sound in self._fading_out_sounds:
                                        if sound in self._queue_current:
                                            self._queue_current.remove(sound)

                        # Add as many new as we can
                        while self._concurrency > len(self._queue_current) and len(self._queue_waiting):
                            sound = self._queue_waiting.pop(0)
                            logger.debug("Adding sound %s", sound)
                            sound.play()
                            self._queue_current.append(sound)
                            self._mixer.add_sound(sound)

                time.sleep(0.1)
            self._thread = None
            logger.debug("Exit audio layer Thread")
        except Exception as e:
            logger.exception(f"Critical error: {e}")
            raise
