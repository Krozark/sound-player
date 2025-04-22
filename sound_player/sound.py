import logging
import time

from sound_player.common import STATUS, StatusObject

logger = logging.getLogger(__name__)


class BaseSound(StatusObject):
    def __init__(self, filepath, loop=None, volume=None):
        super().__init__()
        self._filepath = filepath
        self._loop = loop
        self._volume = volume

    def set_loop(self, loop):
        logger.debug("BaseSound.set_loop(%s)", loop)
        self._loop = loop

    def set_volume(self, volume: int):
        logger.debug("BaseSound.set_volume(%s)", volume)
        self._volume = volume

    def play(self):
        logger.debug("BaseSound.play()")
        if self._status == STATUS.PLAYING:
            return
        elif self._status not in (STATUS.STOPPED, STATUS.PAUSED):
            raise Exception()

        self._do_play()
        super().play()

    def pause(self):
        logger.debug("BaseSound.pause()")
        if self._status == STATUS.PAUSED:
            return
        elif self._status != STATUS.PLAYING:
            raise Exception()

        self._do_pause()
        super().pause()

    def stop(self):
        logger.debug("BaseSound.stop()")
        if self._status == STATUS.STOPPED:
            return
        elif self._status not in (STATUS.PLAYING, STATUS.PAUSED):
            raise Exception()

        self._do_stop()
        super().stop()

    def wait(self, timeout=None):
        logger.debug("BaseSound.wait()")
        start_timestamps = time.time()
        while self._status != STATUS.STOPPED and (timeout is None or start_timestamps + timeout < time.time()):
            time.sleep(0.1)

    def _do_play(self):
        raise NotImplementedError()

    def _do_pause(self):
        raise NotImplementedError()

    def _do_stop(self):
        raise NotImplementedError()
