import logging

from currentplatform import platform

from .audio_config import AudioConfig  # noqa: F401
from .audiolayer import AudioLayer  # noqa: F401
from .mixer import AudioMixer  # noqa: F401
from .player import SoundPlayer  # noqa: F401
from .sound import BaseSound  # noqa: F401

logger = logging.getLogger(__name__)

if platform == "linux":
    from .linux_pcm import LinuxPCMSound as Sound  # noqa: F401
elif platform == "android":
    from .android_pcm import AndroidPCMSound as Sound  # noqa: F401
else:
    logger.critical("No implementation found for platform %s", platform)
    raise NotImplementedError()

__all__ = [
    "AudioConfig",
    "AudioMixer",
    "AudioLayer",
    "SoundPlayer",
    "BaseSound",
    "Sound",
]
