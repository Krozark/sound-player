"""Audio layer module for managing multiple sounds with mixing support."""

import logging
import threading
import time
from collections import deque

import numpy as np

from .core.mixins import STATUS, AudioConfigMixin, FadeCurve, FadeState, StatusMixin, VolumeMixin
from .mixer import AudioMixer

logger = logging.getLogger(__name__)

__all__ = [
    "AudioLayer",
]


class AudioLayer(StatusMixin, VolumeMixin, AudioConfigMixin):
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
        concurrency: int = 1,
        replace: bool = False,
        loop: int = None,
        fade_in_duration: float = None,
        fade_out_duration: float = None,
        fade_curve: FadeCurve | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the AudioLayer.

        Args:
            concurrency: Maximum number of sounds playing simultaneously
            replace: If True, stop old sounds when limit is exceeded
            loop: Default loop count for sounds (-1 = infinite)
            fade_in_duration: Default fade-in duration for enqueued sounds (seconds)
            fade_out_duration: Default fade-out duration for enqueued sounds (seconds),
                                 also used for crossfade when replace=True
            volume: Layer volume (0.0-1.0)
            config: AudioConfig for the mixer
        """
        AudioLayer._check_replace_loop(replace, loop)
        super().__init__(*args, **kwargs)
        self._concurrency = concurrency
        self._replace_on_add = replace
        self._loop = loop
        self._fade_in_duration = fade_in_duration
        self._fade_out_duration = fade_out_duration
        self._fade_curve = fade_curve
        self._queue_waiting = deque()
        self._queue_current = []
        self._fading_out_sounds = []  # Sounds fading out during crossfade
        self._thread = None

        # Create mixer for this layer
        self._mixer: AudioMixer = AudioMixer(self)

    @property
    def mixer(self) -> "AudioMixer":
        """Get the AudioMixer for this layer."""
        return self._mixer

    @staticmethod
    def _check_replace_loop(replace: bool, loop: int | None) -> None:
        """Raise ValueError if replace=False and loop=-1 (infinite loop blocks all slots forever)."""
        if not replace and loop == -1:
            raise ValueError(
                "replace=False with loop=-1 is invalid: sounds would loop forever and never free their slot."
            )

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
        AudioLayer._check_replace_loop(replace, self._loop)
        with self._lock:
            self._replace_on_add = replace

    def set_loop(self, loop):
        """Set the default loop count for sounds.

        Args:
            loop: Number of times to loop (-1 for infinite)
        """
        logger.debug("AudioLayer.set_loop(%s)", loop)
        AudioLayer._check_replace_loop(self._replace_on_add, loop)
        with self._lock:
            self._loop = loop

    def set_fade_curve(self, curve: FadeCurve) -> None:
        """Set the fade curve type.

        Args:
            curve: FadeCurve enum value
        """
        logger.debug(f"AudioLayer.set_fade_curve({curve})")
        with self._lock:
            self._fade_curve = curve

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

        Also used for crossfade when replace=True.

        Args:
            duration: Fade-out duration in seconds (None to disable)
        """
        logger.debug("AudioLayer.set_fade_out_duration(%s)", duration)
        with self._lock:
            self._fade_out_duration = duration

    def enqueue(self, sound, fade_in=None, fade_out=None):
        """Add a sound to the waiting queue.

        Layer defaults override sound properties only when explicitly set (not None).
        Volume is inherited from the sound unless the layer has an explicitly set volume.

        Args:
            sound: The sound to enqueue
            fade_in: Override fade-in duration (None to use layer default)
            fade_out: Override fade-out duration (None to use layer default)
        """
        logger.debug("AudioLayer.enqueue(%s)", sound)
        with self._lock:
            logger.debug("enqueue %s" % sound)

            # Apply layer defaults only when explicitly set (not None)
            if self._loop is not None:
                sound.set_loop(self._loop)
            if self._fade_curve is not None:
                sound.set_fade_curve(self._fade_curve)

            # Apply fade-in duration
            if fade_in is None:
                fade_in = self._fade_in_duration
            if fade_in is not None and fade_in > 0:
                sound.fade_in(fade_in)

            # Store fade-out duration for later use
            if fade_out is None:
                fade_out = self._fade_out_duration
            if fade_out is not None:
                sound.set_fade_out_duration(fade_out)

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

    def _do_play(self, *args, **kwargs):
        """Hook called when play status changes to PLAYING."""
        if self._thread is None:
            logger.debug("Create audio layer Thread")
            self._thread = threading.Thread(target=self._thread_task, daemon=True)
            logger.debug("Start audio layer Thread")
            self._thread.start()

        for sound in self._queue_current:
            sound.play()

    def _do_pause(self, *args, **kwargs):
        """Hook called when play status changes to PAUSED."""
        for sound in self._queue_current:
            sound.pause()

    def _do_stop(self, *args, **kwargs):
        """Hook called when play status changes to STOPPED."""
        self.clear()

    def wait(self, timeout: float | None = None) -> None:
        """Wait until all sounds in this layer have finished playing.

        Args:
            timeout: Maximum time to wait in seconds, None for unlimited
        """
        logger.debug("AudioLayer.wait()")
        start_time = time.time()
        while True:
            with self._lock:
                done = (
                    len(self._queue_waiting) == 0
                    and len(self._queue_current) == 0
                    and len(self._fading_out_sounds) == 0
                )
            if done:
                return
            if timeout is not None and time.time() - start_time >= timeout:
                return
            time.sleep(0.1)

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
                        # Remove stopped sounds; also move fading-out sounds to
                        # _fading_out_sounds when sounds are waiting so the next
                        # sound can start immediately (sequential crossfade).
                        i = 0
                        while i < len(self._queue_current):
                            sound = self._queue_current[i]
                            if sound.status() == STATUS.STOPPED:
                                self._queue_current.pop(i)
                                logger.debug("sound %s has stopped. Remove it", sound)
                                self._mixer.remove_sound(sound)
                                del sound
                            elif sound.fade_state == FadeState.FADING_OUT:
                                self._queue_current.pop(i)
                                self._fading_out_sounds.append(sound)
                                logger.debug("Sequential crossfade: sound %s is fading out, freeing slot", sound)
                            else:
                                i += 1

                        # Remove completed crossfading sounds
                        i = 0
                        while i < len(self._fading_out_sounds):
                            sound = self._fading_out_sounds[i]
                            if sound.status() == STATUS.STOPPED or not sound.is_fading:
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
                                use_fading_out = self._fade_out_duration is not None and self._fade_out_duration > 0

                                # Collect the oldest sounds to remove (from the front of the list)
                                count_to_remove = min(len(self._queue_current), place_needed)
                                sounds_to_remove = self._queue_current[:count_to_remove]
                                self._queue_current = self._queue_current[count_to_remove:]

                                for sound in sounds_to_remove:
                                    if use_fading_out:
                                        # Start fade out for crossfade
                                        logger.debug(
                                            "Crossfading out sound %s to add new one.",
                                            sound,
                                        )
                                        sound.fade_out(self._fade_out_duration)
                                        self._fading_out_sounds.append(sound)
                                    else:
                                        # Immediate stop
                                        logger.debug("stopping sound %s to add new one.", sound)
                                        sound.stop()
                                        self._mixer.remove_sound(sound)

                        # Add as many new as we can
                        while self._concurrency > len(self._queue_current) and len(self._queue_waiting):
                            sound = self._queue_waiting.popleft()
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
