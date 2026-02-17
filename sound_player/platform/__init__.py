"""Platform-specific implementations for the sound-player library.

This module contains platform-specific audio implementations organized by submodules.
"""

import logging
import os

from currentplatform import platform

logger = logging.getLogger(__name__)

__all__ = [
    "Sound",
    "SoundPlayer",
]


if platform in ("linux", "windows"):
    # Linux and Windows share the same sounddevice/soundfile-based implementation
    from .linux import LinuxPCMSound as Sound
    from .linux import LinuxSoundPlayer as SoundPlayer
elif platform == "android":
    # Select the Android decoder via environment variable (default: sync).
    #   SOUND_PLAYER_ANDROID_DECODER=sync   — background decode thread with backpressure
    #   SOUND_PLAYER_ANDROID_DECODER=async  — MediaCodec callback mode, event-driven
    _decoder = os.environ.get("SOUND_PLAYER_ANDROID_DECODER", "sync").lower()
    if _decoder == "async":
        from .android import AndroidPCMSoundAsync as Sound
    else:
        from .android import AndroidPCMSound as Sound
    from .android import AndroidSoundPlayer as SoundPlayer
    logger.debug("Android decoder: %s", _decoder)
else:
    logger.critical("No implementation found for platform %s", platform)
    raise NotImplementedError(f"No implementation available for platform: {platform}")
