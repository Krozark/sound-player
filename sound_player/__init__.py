import logging

from currentplatform import platform

from .player import Playlist, SoundPlayer  # noqa: F401
from .sound import BaseSound  # noqa: F401
from .vlc_sound import VLCSound

logger = logging.getLogger(__name__)

from .vlc_sound import VLCSound as Sound  # noqa: F401

#
# if platform == "linux":
#     # from .linux import LinuxSound as Sound  # noqa: F401
# elif platform == "android":
#     from .android import AndroidSound as Sound  # noqa: F401
# else:
#     logger.critical("No implementation found for platform %s", platform)
#     raise NotImplementedError()
