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
        return self._status

    def play(self):
        self._status = STATUS.PLAYING

    def pause(self):
        self._status = STATUS.PAUSED

    def stop(self):
        self._status = STATUS.STOPPED
