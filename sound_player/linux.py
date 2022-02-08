import logging
import signal
import subprocess

from .sound import BaseSound, STATUS

logger = logging.getLogger(__name__)


class FFMpegSound(BaseSound):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._popen = None

    def __del__(self):
        if self._popen:
            self._popen.kill()
            self._popen = None

    def _build_options(self):
        player = None
        if self.which("avplay"):
            player = "avplay"
        elif self.which("ffplay"):
            player = "ffplay"
        else:
            # should raise exception
            msg = "Couldn't find ffplay or avplay - defaulting to ffplay, but may not work"
            logger.warning(msg)
            # raise RuntimeWarning(msg)
            player = "ffplay"

        options = [player, "-nodisp", "-autoexit", "-hide_banner"]
        if self._loop is not None:
            options.append("-loop")
            options.append(str(self._loop))
        options.append(self._filepath)
        return options

    def _create_popen(self):
        args = self._build_options()
        self._popen = subprocess.Popen(args)

    def wait(self, timeout=None):
        code = self._popen.wait(timeout=timeout)
        return code

    def poll(self):
        if self._popen:
            code = self._popen.poll()
            if code is not None:
                if code == signal.SIGSTOP:
                    self._status = STATUS.PAUSED
                elif code == signal.SIGCONT:
                    self._status = STATUS.PLAYING
                else:  # code == signal.SIGTERM:
                    self._status = STATUS.STOPPED
        return self._status

    def _do_play(self):
        if self._popen is None:
            self._create_popen()
        elif self._status == STATUS.PAUSED:
            self._popen.send_signal(signal.SIGCONT)

    def _do_pause(self):
        self._popen.send_signal(signal.SIGSTOP)

    def _do_stop(self):
        if self._popen:
            self._popen.kill()
            self._popen = None
