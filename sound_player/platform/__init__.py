"""Platform-specific implementations for the sound-player library.

This module contains platform-specific audio implementations organized by submodules.
"""

import logging

from currentplatform import platform

logger = logging.getLogger(__name__)

__all__ = [
    "Sound",
    "SoundPlayer",
]


if platform == "linux":
    from .linux import LinuxPCMSound as Sound
    from .linux import LinuxSoundPlayer as SoundPlayer
elif platform == "android":
    from .android import AndroidPCMSound as Sound
    from .android import AndroidSoundPlayer as SoundPlayer
else:
    logger.critical("No implementation found for platform %s", platform)
    raise NotImplementedError(f"No implementation available for platform: {platform}")
