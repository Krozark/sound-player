from pydub import AudioSegment
import logging
import subprocess
import signal
from tempfile import NamedTemporaryFile
from pydub.utils import get_player_name
import time
from enum import Enum
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

__version__ = "0.1.0"


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

    def __init__(self, segment):
        super().__init__()
        self._segment = segment
        self._tmp_file = None
        self._popen = None

    def __del__(self):
        if self._popen:
            self._popen.kill()
            self._popen = None

        if self._tmp_file:
            self._tmp_file.close()

    def _create_tmp(self):
        self._tmp_file = NamedTemporaryFile("w+b", suffix=".wav")
        self._segment.export(self._tmp_file.name, "wav")

    def _create_popen(self):
        self._popen = subprocess.Popen([self.FFPLAY_PLAYER, "-nodisp", "-autoexit", "-hide_banner", self._tmp_file.name])

    def play(self):
        if self.status() == STATUS.PLAYING:
            return
        elif self._status not in (STATUS.STOPPED, STATUS.PAUSED):
            raise Exception()

        if self._tmp_file is None:
            self._create_tmp()

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

        if self._tmp_file:
            self._tmp_file.close()

        super().stop()


# song = AudioSegment.from_ogg("music.ogg")
#
# sound = Sound(song)
#
# sound.play()
# time.sleep(5)
#
# sound.pause()
# time.sleep(5)
#
# sound.play()
# time.sleep(5)
#
# sound.stop()
# time.sleep(5)


class Playlist(StatusObject):
    def __init__(self, concurency=1):
        super().__init__()
        self._concurency = concurency
        self._queue_waiting = []
        self._queue_current = []
        self._thread = None
        self._lock = threading.Lock()

    def enqueue(self, sound):
        with self._lock:
            logger.debug("enqueue %s" % sound)
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
                    i = 0
                    while i < len(self._queue_current):
                        sound_status = self._queue_current[i].poll()
                        if sound_status == STATUS.STOPPED:
                            logger.debug("sound %s has stoped. Remove it", sound)
                            sound = self._queue_current.pop(i)
                        else:
                            i += 1

                    while self._concurency > len(self._queue_current) and len(self._queue_waiting):
                        sound = self._queue_waiting.pop(0)
                        logger.debug("Add sound %s", sound)
                        sound.play()
                        self._queue_current.append(sound)

            time.sleep(0.1)
        self._thread = None


# pl = Playlist(concurency=2)
# pl.enqueue(Sound(AudioSegment.from_wav("coin.wav")))
# pl.enqueue(Sound(AudioSegment.from_ogg("music.ogg")))
# pl.enqueue(Sound(AudioSegment.from_wav("coin.wav")))
# pl.enqueue(Sound(AudioSegment.from_wav("coin.wav")))
#
# pl.play()
# time.sleep(100)


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

# player = SoundPlayer()
# player.enqueue(Sound(AudioSegment.from_wav("coin.wav")), 1)
# player.enqueue(Sound(AudioSegment.from_ogg("music.ogg")), 1)
# player.enqueue(Sound(AudioSegment.from_wav("coin.wav")), 1)
#
# player.play()
# time.sleep(5)
# player.enqueue(Sound(AudioSegment.from_wav("coin.wav")), 2)
# player.enqueue(Sound(AudioSegment.from_wav("coin.wav")), 2)
# time.sleep(50)
