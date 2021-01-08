import logging
import os
import signal
import subprocess
import threading
import time
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)

__version__ = "0.2.3"


def which(program):
    """
    Mimics behavior of UNIX which command.
    """
    # Add .exe program extension for windows support
    if os.name == "nt" and not program.endswith(".exe"):
        program += ".exe"

    envdir_list = [os.curdir] + os.environ["PATH"].split(os.pathsep)

    for envdir in envdir_list:
        program_path = os.path.join(envdir, program)
        if os.path.isfile(program_path) and os.access(program_path, os.X_OK):
            return program_path


def get_player_name():
    """
    Return enconder default application for system, either avconv or ffmpeg
    """
    if which("avplay"):
        return "avplay"
    elif which("ffplay"):
        return "ffplay"
    else:
        # should raise exception
        msg = "Couldn't find ffplay or avplay - defaulting to ffplay, but may not work"
        logger.warning(msg)
        # raise RuntimeWarning(msg)
        return "ffplay"


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


class Sound(StatusObject):
    FFPLAY_PLAYER = get_player_name()

    def __init__(self, filepath):
        super().__init__()
        self._filepath = filepath
        self._popen = None
        self._loop = None

    def __del__(self):
        if self._popen:
            self._popen.kill()
            self._popen = None

    def set_loop(self, loop):
        self._loop = loop

    def _create_popen(self):
        args = [self.FFPLAY_PLAYER, "-nodisp", "-autoexit", "-hide_banner"]
        if self._loop is not None:
            args.append("-loop")
            args.append(str(self._loop))
        args.append(self._filepath)
        self._popen = subprocess.Popen(args)

    def play(self):
        if self.status() == STATUS.PLAYING:
            return
        elif self._status not in (STATUS.STOPPED, STATUS.PAUSED):
            raise Exception()

        if self._popen is None:
            self._create_popen()
        elif self._status == STATUS.PAUSED:
            self._popen.send_signal(signal.SIGCONT)

        super().play()

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
                else: # code == signal.SIGTERM:
                    self._status = STATUS.STOPPED
        return self._status

    def pause(self):
        if self._status != STATUS.PLAYING:
            raise Exception()

        self._popen.send_signal(signal.SIGSTOP)
        super().pause()

    def stop(self):
        if self._status != STATUS.PLAYING:
            raise Exception()

        if self._popen:
            self._popen.kill()
            self._popen = None

        super().stop()


class Playlist(StatusObject):
    def __init__(self, concurency=1, replace=False, loop=1):
        super().__init__()
        self._concurency = concurency
        self._replace_on_add = replace
        self._queue_waiting = []
        self._queue_current = []
        self._thread = None
        self._loop = None
        self._lock = threading.Lock()

    def set_concurency(self, concurency):
        self._concurency = concurency

    def set_replace(self, replace):
        self._replace_on_add = replace

    def set_loop(self, loop):
        self._loop = loop

    def enqueue(self, sound):
        with self._lock:
            logger.debug("enqueue %s" % sound)
            loop = sound._loop or self._loop
            if loop is not None:
                sound.set_loop(loop)
            self._queue_waiting.append(sound)

    def clear(self):
        with self._lock:
            self._queue_waiting.clear()
            self._queue_current.clear()

    def pause(self):
        super().pause()
        with self._lock:
            for sound in self._queue_current:
                sound.pause()

    def stop(self):
        super().stop()
        with self._lock:
            for sound in self._queue_current:
                sound.stop()

        self.clear()

    def play(self):
        super().play()
        if self._thread is None:
            logger.debug("Create playlist Thread")
            self._thread = threading.Thread(target=self._thread_task, daemon=True)
            logger.debug("Start playlist Thread")
            self._thread.start()

        with self._lock:
            for sound in self._queue_current:
                sound.play()

    def _thread_task(self):
        logger.debug("In playlist Thread")
        while self._status != STATUS.STOPPED:
            logger.debug("Thread loop")
            if self._status == STATUS.PLAYING:
                with self._lock:
                    # remove stopped sound
                    i = 0
                    while i < len(self._queue_current):
                        sound_status = self._queue_current[i].poll()
                        if sound_status == STATUS.STOPPED:
                            logger.debug("sound %s has stopped. Remove it", sound)
                            sound = self._queue_current.pop(i)
                        else:
                            i += 1

                    if self._replace_on_add and len(self._queue_waiting):
                        # remove a sound to make a place for a new one
                        if len(self._queue_current) == self._concurency:
                            sound = self._queue_current.pop(0)
                            sound.stop()

                    # add new if needed
                    while self._concurency > len(self._queue_current) and len(self._queue_waiting):
                        sound = self._queue_waiting.pop(0)
                        logger.debug("Add sound %s", sound)
                        sound.play()
                        self._queue_current.append(sound)

            time.sleep(0.1)
        self._thread = None


class SoundPlayer(StatusObject):
    def __init__(self):
        super().__init__()
        self._playlists = defaultdict(Playlist)

    def enqueue(self, sound, playlist):
        if not playlist in self._playlists:
            if self._status == STATUS.PLAYING:
                self._playlists[playlist].play()
            elif self._status == STATUS.PAUSED:
                self._playlists[playlist].pause()
        self._playlists[playlist].enqueue(sound)

    def status(self, playlist=None):
        if playlist is not None:
            return self._playlists[playlist].status()
        return super().status()

    def get_playlists(self):
        return self._playlists.keys()

    def delete_playlist(self, playlist):
        self._playlists[playlist].stop()
        del self._playlists[playlist]

    def play(self, playlist=None):
        if playlist is not None:
            return self._playlists[playlist].play()
        else:
            for pl in self._playlists.values():
                if pl.status() != STATUS.PLAYING:
                    pl.play()
            super().play()

    def pause(self, playlist=None):
        if playlist is not None:
            return self._playlists[playlist].pause()
        else:
            for pl in self._playlists.values():
                if pl.status() != STATUS.PAUSED:
                    pl.pause()
            super().pause()

    def stop(self, playlist=None):
        if playlist is not None:
            return self._playlists[playlist].stop()
        else:
            for pl in self._playlists.values():
                if pl.status() != STATUS.STOPPED:
                    pl.stop()
            super().stop()
