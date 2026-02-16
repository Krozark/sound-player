"""Platform-specific implementations for the sound-player library.

This module contains platform-specific audio implementations organized by submodules.
"""

import logging

from currentplatform import platform

logger = logging.getLogger(__name__)

__all__ = [
    "Sound",
]


if platform == "linux":
    from .linux import Sound
elif platform == "android":
    from .android import Sound
else:
    logger.critical("No implementation found for platform %s", platform)
    raise NotImplementedError(f"No implementation available for platform: {platform}")
