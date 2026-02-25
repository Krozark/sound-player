"""Platform-specific implementations for the sound-player library.

This module contains platform-specific audio implementations organized by submodules.
"""

import logging

from currentplatform import platform

logger = logging.getLogger(__name__)

__all__ = [
    "SoundPlayer",
]


if platform in ("linux", "windows"):
    # Linux and Windows share the same sounddevice/soundfile-based implementation
    from .platform.linux import LinuxSoundPlayer as SoundPlayer
elif platform == "android":
    # Select the Android decoder via environment variable).
    from .platform.android import AndroidSoundPlayer as SoundPlayer
else:
    logger.critical("No implementation found for platform %s", platform)
    raise NotImplementedError(f"No implementation available for platform: {platform}")
