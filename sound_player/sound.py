import logging
import os

from currentplatform import platform

from sound_player.common import StatusObject, STATUS

logger = logging.getLogger(__name__)


class BaseSound(StatusObject):
    def __init__(self, filepath, loop=None):
        super().__init__()
        self._filepath = filepath
        self._loop = loop

    def set_loop(self, loop):
        self._loop = loop

    def play(self):
        if self.status() == STATUS.PLAYING:
            return
        elif self._status not in (STATUS.STOPPED, STATUS.PAUSED):
            raise Exception()

        self._do_play()
        super().play()

    def pause(self):
        if self.status() == STATUS.PAUSED:
            return
        elif self._status != STATUS.PLAYING:
            raise Exception()

        self._do_pause()
        super().pause()

    def stop(self):
        if self.status() == STATUS.STOPPED:
            return
        elif self._status not in (STATUS.PLAYING, STATUS.PAUSED):
            raise Exception()

        self._do_stop()
        super().stop()

    def wait(self, timeout=None):
        raise NotImplementedError

    def poll(self):
        return self._status

    def which(self, program):
        """
        Mimics behavior of UNIX which command.
        """
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