"""Status mixin for managing playback state."""

import logging
from enum import Enum

from .lock import LockMixin

logger = logging.getLogger(__name__)


class STATUS(Enum):
    """Playback status enumeration."""

    ERROR = -1
    STOPPED = 1
    PLAYING = 2
    PAUSED = 3


class StatusMixin(LockMixin):
    """Mixin class for managing playback status with volume and thread safety.

    Provides status management (_status), volume management (inherited from
    VolumeMixin), and thread-safe play/pause/stop methods with hooks for
    subclasses.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._status = STATUS.STOPPED

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
