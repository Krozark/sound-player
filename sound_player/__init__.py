import logging

from currentplatform import platform

from .player import Playlist, SoundPlayer  # noqa: F401
from .sound import BaseSound  # noqa: F401

logger = logging.getLogger(__name__)

if platform == "linux":
    from .linux import LinuxSound as Sound  # noqa: F401
elif platform == "android":
    from .android import AndroidSound as Sound  # noqa: F401
else:
    logger.critical("No implementation found for platform %s", platform)
    raise NotImplementedError()
