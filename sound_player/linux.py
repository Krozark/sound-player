import logging
import os
import signal
import subprocess

from currentplatform import platform

from .sound import STATUS, BaseSound

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
        logger.debug("FFMpegSound._build_options()")

        if self._which("avplay"):
            player = "avplay"
        elif self._which("ffplay"):
            player = "ffplay"
        else:
            # should raise exception
            msg = "Couldn't find ffplay or avplay - defaulting to ffplay, but may not work"
            logger.warning(msg)
            # raise RuntimeWarning(msg)
            player = "ffplay"

        options = [
            player,
            "-nodisp",
            "-autoexit",
            "-hide_banner",
        ]
        if self._loop is not None:
            if self._loop == -1:
                options.append("-loop")
                options.append("0")  # 0 is infinit for player, but -1 in class
            elif self._loop > 0:
                options.append("-loop")
                options.append(str(self._loop))

        if self._volume is not None:
            options.append("-volume")
            options.append(str(self._volume))

        options.append(self._filepath)
        return options

    def _create_popen(self):
        logger.debug("FFMpegSound._create_popen()")
        args = self._build_options()
        logger.debug(f"FFMpegSound._create_popen() {args}")
        self._popen = subprocess.Popen(args)

    def wait(self, timeout=None):
        logger.debug("FFMpegSound.wait(%s)", timeout)
        code = self._popen.wait(timeout=timeout)
        return code

    def poll(self):
        logger.debug("FFMpegSound.poll()")
        if self._popen is None:
            return STATUS.STOPPED

        if self._popen.poll() is not None:
            self.stop()

        return self._status

    def _do_play(self):
        logger.debug("FFMpegSound._do_play()")
        if self._popen is None:
            self._create_popen()
        elif self._status == STATUS.PAUSED:
            self._popen.send_signal(signal.SIGCONT)

    def _do_pause(self):
        logger.debug("FFMpegSound._do_pause()")
        self._popen.send_signal(signal.SIGSTOP)

    def _do_stop(self):
        logger.debug("FFMpegSound._do_stop()")
        if self._popen:
            self._popen.terminate()
            self._popen = None

    def _which(self, program):
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


LinuxSound = FFMpegSound
