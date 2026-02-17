"""Volume mixin for managing audio volume levels."""

from .lock import LockMixin


class VolumeMixin(LockMixin):
    """Mixin class for managing volume with clamping.

    Provides _volume attribute, _lock (inherited), and set_volume/get_volume
    methods that clamp values to the 0.0-1.0 range.
    Thread-safe via inherited LockMixin.
    """

    def __init__(self, volume: float = 1.0, *args, **kwargs):
        """Initialize the volume.

        Args:
            volume: Initial volume (0.0-1.0), defaults to 1.0.
        """
        super().__init__(*args, **kwargs)
        self._volume = max(0.0, min(1.0, volume))

    def set_volume(self, volume: float | None) -> None:
        """Set the volume with clamping.

        Args:
            volume: Volume level (0.0-1.0), will be clamped to this range.
        """
        with self._lock:
            self._volume = max(0.0, min(1.0, volume))

    @property
    def volume(self) -> float:
        """Get the current volume."""
        return self._volume
