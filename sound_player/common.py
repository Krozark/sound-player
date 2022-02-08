import logging
from enum import Enum

logger = logging.getLogger(__name__)

__version__ = "0.3.0"


class STATUS(Enum):
    ERROR = -1
    STOPPED = 1
    PLAYING = 2
    PAUSED = 3


class StatusObject(object):
    def __init__(self):
        self._status = STATUS.STOPPED

    def status(self):
        logger.debug("StatusObject,status()")
        return self._status

    def play(self):
        logger.debug("StatusObject,play()")
        self._status = STATUS.PLAYING

    def pause(self):
        logger.debug("StatusObject,pause()")
        self._status = STATUS.PAUSED

    def stop(self):
        logger.debug("StatusObject,stop()")
        self._status = STATUS.STOPPED
