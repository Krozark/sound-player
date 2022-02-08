__version__ = "0.3.2"


import logging

from currentplatform import platform

from .player import Playlist, SoundPlayer
from .sound import BaseSound

logger = logging.getLogger(__name__)

if platform == "linux":
    from .linux import FFMpegSound as Sound
elif platform == "android":
    from .android import AndroidSound as Sound
else:
    logger.critical("No implementation found for platform %s", platform)
    raise NotImplementedError
