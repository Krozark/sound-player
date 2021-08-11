import logging
import threading
import time
from collections import defaultdict

from sound_player.common import StatusObject, STATUS

logger = logging.getLogger(__name__)


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
