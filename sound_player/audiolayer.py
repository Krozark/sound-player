"""Audio layer module for managing multiple sounds with mixing support."""

import logging
import threading
import time
from typing import TYPE_CHECKING

import numpy as np

from .core.audio_config import AudioConfig
from .core.state import STATUS, StatusObject

if TYPE_CHECKING:
    from .mixer import AudioMixer

logger = logging.getLogger(__name__)

__all__ = [
    "AudioLayer",
]


class AudioLayer(StatusObject):
    """Manages a queue of sounds with support for concurrent playback and mixing.

    The AudioLayer maintains two queues:
    - _queue_waiting: Sounds waiting to be played
    - _queue_current: Sounds currently playing

    Key features:
    - concurrency: Maximum number of sounds playing simultaneously
    - replace: If True, stops old sounds when adding new ones beyond concurrency limit
    - loop: How many times sounds should be played (-1 = infinite, N = finite)
    - volume: Layer-level volume (0-100)
    - mixer: AudioMixer for mixing current sounds together
    """

    def __init__(self, concurrency=1, replace=False, loop=None, volume=100, config: AudioConfig | None = None):
        """Initialize the AudioLayer.

        Args:
            concurrency: Maximum number of sounds playing simultaneously
            replace: If True, stop old sounds when limit is exceeded
            loop: Default loop count for sounds (-1 = infinite)
            volume: Layer volume (0-100)
            config: AudioConfig for the mixer
        """
        super().__init__()
        self._concurrency = concurrency
        self._replace_on_add = replace
        self._loop = loop
        self._volume = volume
        self._config = config or AudioConfig()
        self._queue_waiting = []
        self._queue_current = []
        self._thread = None
        self._lock = threading.RLock()

        # Import mixer here to avoid circular imports
        from .mixer import AudioMixer

        # Create mixer for this layer
        self._mixer: AudioMixer = AudioMixer(self._config, volume / 100.0)

    @property
    def config(self) -> AudioConfig:
        """Get the audio configuration."""
        return self._config

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

    def set_volume(self, volume):
        """Set the layer volume.

        Args:
            volume: Volume level (0-100)
        """
        logger.debug("AudioLayer.set_volume(%s)", volume)
        with self._lock:
            self._volume = volume
            self._mixer.set_volume(volume / 100.0)

    def enqueue(self, sound):
        """Add a sound to the waiting queue.

        Args:
            sound: The sound to enqueue
        """
        logger.debug("AudioLayer.enqueue(%s)", sound)
        with self._lock:
            logger.debug("enqueue %s" % sound)
            loop = sound._loop or self._loop
            volume = sound._volume or self._volume
            sound.set_loop(loop)
            sound.set_volume(volume)
            self._queue_waiting.append(sound)

    def clear(self):
        """Clear all queues and the mixer."""
        logger.debug("AudioLayer.clear()")
        with self._lock:
            # Stop and remove all sounds from mixer
            for sound in self._queue_current:
                self._mixer.remove_sound(sound)
                sound.stop()
            self._queue_waiting.clear()
            self._queue_current.clear()

    def pause(self):
        """Pause playback of all current sounds."""
        logger.debug("AudioLayer.pause()")
        with self._lock:
            super().pause()
            for sound in self._queue_current:
                sound.pause()

    def stop(self):
        """Stop playback and clear all queues."""
        logger.debug("AudioLayer.stop()")
        with self._lock:
            if self._status != STATUS.STOPPED:
                super().stop()
            self.clear()

    def play(self):
        """Start playback of the audio layer."""
        logger.debug("AudioLayer.play()")
        with self._lock:
            super().play()
            if self._thread is None:
                logger.debug("Create audio layer Thread")
                self._thread = threading.Thread(target=self._thread_task, daemon=True)
                logger.debug("Start audio layer Thread")
                self._thread.start()

            for sound in self._queue_current:
                sound.play()

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
        2. Stops old sounds if replace mode is enabled
        3. Moves sounds from waiting to current queue
        4. Adds/removes sounds from the mixer as they transition
        """
        logger.debug("In audio layer Thread")
        try:
            while self._status != STATUS.STOPPED:
                if self._status == STATUS.PLAYING:
                    with self._lock:
                        # Remove stopped sounds
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

                        # Stop sounds to make place for new ones (replace mode)
                        if self._replace_on_add:
                            place_needed = len(self._queue_current) + len(self._queue_waiting) - self._concurrency
                            for i in range(0, min(len(self._queue_current), place_needed)):
                                sound = self._queue_current[i]
                                logger.debug("stopping sound %s to add new one.", sound)
                                sound.stop()
                                self._mixer.remove_sound(sound)

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
