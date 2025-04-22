import logging
import threading
import time

from .common import STATUS, StatusObject

logger = logging.getLogger(__name__)


class Playlist(StatusObject):
    def __init__(self, concurrency=1, replace=False, loop=None, volume=100):
        super().__init__()
        self._concurrency = concurrency
        self._replace_on_add = replace
        self._loop = loop
        self._volume = volume
        self._queue_waiting = []
        self._queue_current = []
        self._thread = None
        self._lock = threading.RLock()

    def set_concurrency(self, concurrency):
        logger.debug("Playlist.set_concurrency(%s)", concurrency)
        with self._lock:
            self._concurrency = concurrency

    def set_replace(self, replace):
        logger.debug("Playlist.set_replace(%s)", replace)
        with self._lock:
            self._replace_on_add = replace

    def set_loop(self, loop):
        logger.debug("Playlist.set_loop(%s)", loop)
        with self._lock:
            self._loop = loop

    def set_volume(self, volume):
        logger.debug("Playlist.set_volume(%s)", volume)
        with self._lock:
            self._volume = volume

    def enqueue(self, sound):
        logger.debug("Playlist.enqueue(%s)", sound)
        with self._lock:
            logger.debug("enqueue %s" % sound)
            loop = sound._loop or self._loop
            volume = sound._volume or self._volume
            sound.set_loop(loop)
            sound.set_volume(volume)
            self._queue_waiting.append(sound)

    def clear(self):
        logger.debug("Playlist.clear()")
        with self._lock:
            self._queue_waiting.clear()
            self._queue_current.clear()

    def pause(self):
        logger.debug("Playlist.pause()")
        with self._lock:
            super().pause()
            for sound in self._queue_current:
                sound.pause()

    def stop(self):
        logger.debug("Playlist.stop()")
        with self._lock:
            if self._status != STATUS.STOPPED:
                super().stop()
                for sound in self._queue_current:
                    sound.stop()
            self.clear()

    def play(self):
        logger.debug("Playlist.play()")
        with self._lock:
            super().play()
            if self._thread is None:
                logger.debug("Create playlist Thread")
                self._thread = threading.Thread(target=self._thread_task, daemon=True)
                logger.debug("Start playlist Thread")
                self._thread.start()

            for sound in self._queue_current:
                sound.play()

    def _thread_task(self):
        logger.debug("In playlist Thread")
        try:
            while self._status != STATUS.STOPPED:
                if self._status == STATUS.PLAYING:
                    with self._lock:
                        # remove stopped sound
                        i = 0
                        while i < len(self._queue_current):
                            sound_status = self._queue_current[i].status()
                            if sound_status == STATUS.STOPPED:
                                sound = self._queue_current.pop(i)
                                logger.debug("sound %s has stopped. Remove it", sound)
                                del sound
                            else:
                                i += 1

                        # stop sounds to make place for new ones
                        if self._replace_on_add:
                            place_needed = len(self._queue_current) + len(self._queue_waiting) - self._concurrency
                            for i in range(0, min(len(self._queue_current), place_needed)):
                                sound = self._queue_current[i]
                                logger.debug("stopping sound %s to add new one.", sound)
                                sound.stop()

                        # add as many new as we can
                        while self._concurrency > len(self._queue_current) and len(self._queue_waiting):
                            sound = self._queue_waiting.pop(0)
                            logger.debug("Adding sound %s", sound)
                            sound.play()
                            self._queue_current.append(sound)

                time.sleep(0.1)
            self._thread = None
            logger.debug("Exit playlist Thread")
        except Exception as e:
            logger.exception(f"Critical error: {e}")
            raise


class SoundPlayer(StatusObject):
    def __init__(self):
        super().__init__()
        self._playlists: dict[str, Playlist] = {}
        self._lock = threading.RLock()

    def create_playlist(self, playlist, *args, **kwargs):
        with self._lock:
            self._playlists[playlist] = Playlist(*args, **kwargs)

    def enqueue(self, sound, playlist):
        logger.debug("SoundPlayer.enqueue(%s, %s)", sound, playlist)
        if playlist not in self._playlists:
            logger.error(f"Playlist {playlist} not found")
            return

        with self._lock:
            if playlist not in self._playlists:
                if self._status == STATUS.PLAYING:
                    self._playlists[playlist].play()
                elif self._status == STATUS.PAUSED:
                    self._playlists[playlist].pause()
            self._playlists[playlist].enqueue(sound)

    def status(self, playlist=None):
        logger.debug("SoundPlayer.status(%s)", playlist)
        if playlist is not None:
            return self._playlists[playlist].status()
        return super().status()

    def get_playlists(self):
        logger.debug("SoundPlayer.get_playlists()")
        return self._playlists.keys()

    def delete_playlist(self, playlist):
        logger.debug("SoundPlayer.delete_playlist(%s)", playlist)
        with self._lock:
            self._playlists[playlist].stop()
            del self._playlists[playlist]

    def play(self, playlist=None):
        logger.debug("SoundPlayer.play(%s)", playlist)
        with self._lock:
            if playlist is not None:
                return self._playlists[playlist].play()
            else:
                for pl in self._playlists.values():
                    if pl.status() != STATUS.PLAYING:
                        pl.play()
                super().play()

    def pause(self, playlist=None):
        logger.debug("SoundPlayer.pause(%s)", playlist)
        with self._lock:
            if playlist is not None:
                return self._playlists[playlist].pause()
            else:
                for pl in self._playlists.values():
                    if pl.status() != STATUS.PAUSED:
                        pl.pause()
                super().pause()

    def stop(self, playlist=None):
        logger.debug("SoundPlayer.stop(%s)", playlist)
        with self._lock:
            if playlist is not None:
                return self._playlists[playlist].stop()
            else:
                for pl in self._playlists.values():
                    pl.stop()
                super().stop()

    def __getitem__(self, playlist):
        return self._playlists[playlist]
