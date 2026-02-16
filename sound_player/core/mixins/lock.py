"""Lock mixin for thread-safe operations."""

import threading


class LockMixin:
    """Mixin that provides a reentrant lock for thread-safe operations.

    This is the base mixin for all other mixins that require thread safety.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the lock."""
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()
