import logging
import os
import vlc
from currentplatform import platform

from .common import STATUS, StatusObject


logger = logging.getLogger(__name__)


class BaseSound(StatusObject):
    def __init__(self, filepath, loop=None):
        super().__init__()
        self._filepath = filepath
        self._loop = loop

    def set_loop(self, loop):
        logger.debug("BaseSound.set_loop(%s)", loop)
        self._loop = loop

    def play(self):
        logger.debug("BaseSound.play()")
        if self.status() == STATUS.PLAYING:
            return
        elif self._status not in (STATUS.STOPPED, STATUS.PAUSED):
            raise Exception()

        self._do_play()
        super().play()

    def pause(self):
        logger.debug("BaseSound.pause()")
        if self.status() == STATUS.PAUSED:
            return
        elif self._status != STATUS.PLAYING:
            raise Exception()

        self._do_pause()
        super().pause()

    def stop(self):
        logger.debug("BaseSound.stop()")
        if self.status() == STATUS.STOPPED:
            return
        elif self._status not in (STATUS.PLAYING, STATUS.PAUSED):
            raise Exception()

        self._do_stop()
        super().stop()

    def wait(self, timeout=None):
        raise NotImplementedError

    def poll(self):
        logger.debug("BaseSound.poll()")
        return self._status

    def which(self, program):
        """
        Mimics behavior of UNIX which command.
        """
        logger.debug("BaseSound.wich(%s)", program)
        # Add .exe program extension for windows support
        if platform == "windows" and not program.endswith(".exe"):
            program += ".exe"

        envdir_list = [os.curdir] + os.environ["PATH"].split(os.pathsep)

        for envdir in envdir_list:
            program_path = os.path.join(envdir, program)
            if os.path.isfile(program_path) and os.access(program_path, os.X_OK):
                return program_path

    def _do_play(self):
        raise NotImplementedError

    def _do_pause(self):
        raise NotImplementedError

    def _do_stop(self):
        raise NotImplementedError

class VLCSound(BaseSound):
    def __init__(self, filepath, loop=None):
        super().__init__(filepath, loop)
        self._instance = vlc.Instance()
        self._player = self._instance.media_player_new()
        media = self._instance.media_new(self._filepath)
        self._player.set_media(media)
        if self._loop:
            self._player.set_media(media)
            media.add_option('input-repeat={}'.format(self._loop - 1))

    def _do_play(self):
        logger.debug("VLCSound._do_play()")
        self._player.play()

    def _do_pause(self):
        logger.debug("VLCSound._do_pause()")
        self._player.pause()

    def _do_stop(self):
        logger.debug("VLCSound._do_stop()")
        self._player.stop()

    def poll(self):
        state = self._player.get_state()
        if state == vlc.State.Playing:
            return STATUS.PLAYING
        elif state == vlc.State.Paused:
            return STATUS.PAUSED
        elif state in (vlc.State.Stopped, vlc.State.Ended):
            return STATUS.STOPPED
        return self._status

Sound = VLCSound