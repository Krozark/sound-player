"""Mixin classes for the sound-player library.

This module provides reusable mixins for managing status and volume.
"""

import logging
import threading
from enum import Enum

from .audio_config import AudioConfig

logger = logging.getLogger(__name__)

__all__ = [
    "STATUS",
    "StatusMixin",
    "VolumeMixin",
    "AudioConfigMixin",
    "LockMixin",
]


class STATUS(Enum):
    """Playback status enumeration."""

    ERROR = -1
    STOPPED = 1
    PLAYING = 2
    PAUSED = 3


class LockMixin:
    def __init__(self, *args, **kwargs):
        """Initialize the volume and lock.

        Args:
            volume: Initial volume (0.0-1.0), defaults to 1.0.
        """
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()


class VolumeMixin(LockMixin):
    """Mixin class for managing volume with clamping.

    Provides _volume attribute, _lock, and set_volume/get_volume methods that
    clamp values to the 0.0-1.0 range.
    """

    def __init__(self, volume: float = 1.0, *args, **kwargs):
        """Initialize the volume and lock.

        Args:
            volume: Initial volume (0.0-1.0), defaults to 1.0.
        """
        super().__init__(*args, **kwargs)

        self.set_volume(volume)

    def set_volume(self, volume: float) -> None:
        """Set the volume with clamping.

        Args:
            volume: Volume level (0.0-1.0), will be clamped to this range.
        """
        if volume is None:
            volume = 1.0

        with self._lock:
            self._volume = max(0.0, min(1.0, volume))

    @property
    def volume(self) -> float:
        """Get the master volume."""
        return self._volume


class StatusMixin(VolumeMixin):
    """Mixin class for managing playback status with volume and thread safety.

    Provides status management (_status), volume management (inherited),
    and thread-safe play/pause/stop methods with hooks for subclasses.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the status and volume.

        Args:
            volume: Initial volume (0.0-1.0), defaults to 1.0.
        """
        self._status = STATUS.STOPPED

        super().__init__(*args, **kwargs)

    def status(self) -> STATUS:
        """Get the current playback status.

        Returns:
            Current STATUS enum value
        """
        return self._status

    def play(self, *args, **kwargs):
        """Start playback.

        This method is thread-safe and calls _do_play() for subclass-specific logic.
        """
        logger.debug("StatusMixin.play()")
        with self._lock:
            if self._status == STATUS.PLAYING:
                return
            elif self._status not in (STATUS.STOPPED, STATUS.PAUSED):
                raise ValueError()
            self._status = STATUS.PLAYING
            self._do_play(*args, **kwargs)

    def pause(self, *args, **kwargs):
        """Pause playback.

        This method is thread-safe and calls _do_pause() for subclass-specific logic.
        """
        logger.debug("StatusMixin.pause()")
        with self._lock:
            if self._status == STATUS.PAUSED:
                return
            elif self._status != STATUS.PLAYING:
                raise ValueError()
            self._do_pause()
            self._status = STATUS.PAUSED

    def stop(self, *args, **kwargs):
        """Stop playback.

        This method is thread-safe and calls _do_stop() for subclass-specific logic.
        """
        logger.debug("StatusMixin.stop()")
        with self._lock:
            if self._status == STATUS.STOPPED:
                return
            elif self._status not in (STATUS.PLAYING, STATUS.PAUSED):
                raise ValueError()
            self._do_stop()
            self._status = STATUS.STOPPED

    # Hooks for subclasses to override

    def _do_play(self, *args, **kwargs):
        """Hook for subclasses to implement play-specific logic.

        Called with the lock held.
        """
        raise NotImplementedError()

    def _do_pause(self, *args, **kwargs):
        """Hook for subclasses to implement pause-specific logic.

        Called with the lock held.
        """
        raise NotImplementedError()

    def _do_stop(self, *args, **kwargs):
        """Hook for subclasses to implement stop-specific logic.

        Called with the lock held.
        """
        raise NotImplementedError()


class AudioConfigMixin:
    def __init__(self, config: AudioConfig | None = None, *args, **kwargs):
        self._config = config or AudioConfig()

        super().__init__(*args, **kwargs)

    @property
    def config(self) -> AudioConfig:
        """Get the audio configuration."""
        return self._config
