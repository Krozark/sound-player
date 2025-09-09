import logging
from enum import Enum, auto

logger = logging.getLogger(__name__)


class StatusEnum(Enum):
    ERROR = -1
    STOPPED = 1
    PLAYING = 2
    PAUSED = 3


class AudioEffectEnum(Enum):
    """Available audio effect types"""

    FADE_IN = auto()
    FADE_OUT = auto()
    SET_VOLUME = auto()


class StatusObject:
    def __init__(self):
        self._status = StatusEnum.STOPPED

    def status(self):
        logger.debug("StatusObject.status()")
        return self._status

    def play(self):
        logger.debug("StatusObject.play()")
        self._status = StatusEnum.PLAYING

    def pause(self):
        logger.debug("StatusObject.pause()")
        self._status = StatusEnum.PAUSED

    def stop(self):
        logger.debug("StatusObject.stop()")
        self._status = StatusEnum.STOPPED
