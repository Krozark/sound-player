import logging
import threading
import time

from .common import STATUS, StatusObject
from .sound import BaseSound

logger = logging.getLogger(__name__)


class Playlist(StatusObject):
    def __init__(self, concurrency: int = 1, replace: bool = False, loop: int = 0, volume: int = 100):
        super().__init__()
        self._concurrency: int = concurrency
        self._replace_on_add: bool = replace
        self._loop: int = loop
        self._volume: int = volume
        self._queue_waiting: list[BaseSound] = []
        self._queue_current: list[BaseSound] = []
        self._thread = None
        self._lock = threading.RLock()

    def set_concurrency(self, concurrency: int):
        logger.debug("Playlist.set_concurrency(%s)", concurrency)
        with self._lock:
            self._concurrency = concurrency

    def set_replace(self, replace: bool):
        logger.debug("Playlist.set_replace(%s)", replace)
        with self._lock:
            self._replace_on_add = replace

    def set_loop(self, loop: int):
        logger.debug("Playlist.set_loop(%s)", loop)
        with self._lock:
            self._loop = loop

    def set_volume(self, volume):
        logger.debug("Playlist.set_volume(%s)", volume)
        with self._lock:
            self._volume = volume

    def enqueue(self, sound: BaseSound):
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

    def create_playlist(self, playlist_name: str, *args, **kwargs):
        with self._lock:
            self._playlists[playlist_name] = Playlist(*args, **kwargs)

    def enqueue(self, sound, playlist_name: str):
        logger.debug("SoundPlayer.enqueue(%s, %s)", sound, playlist_name)
        if playlist_name not in self._playlists:
            logger.error(f"Playlist {playlist_name} not found")
            return

        with self._lock:
            if playlist_name not in self._playlists:
                if self._status == STATUS.PLAYING:
                    self._playlists[playlist_name].play()
                elif self._status == STATUS.PAUSED:
                    self._playlists[playlist_name].pause()
            self._playlists[playlist_name].enqueue(sound)

    def status(self, playlist_name: str | None = None):
        logger.debug("SoundPlayer.status(%s)", playlist_name)
        if playlist_name is not None:
            return self._playlists[playlist_name].status()
        return super().status()

    def get_playlists(self) -> list[str]:
        logger.debug("SoundPlayer.get_playlists()")
        return self._playlists.keys()

    def delete_playlist(self, playlist_name: str):
        logger.debug("SoundPlayer.delete_playlist(%s)", playlist_name)
        with self._lock:
            self._playlists[playlist_name].stop()
            del self._playlists[playlist_name]

    def play(self, playlist_name: str | None = None):
        logger.debug("SoundPlayer.play(%s)", playlist_name)
        with self._lock:
            if playlist_name is not None:
                return self._playlists[playlist_name].play()
            else:
                for pl in self._playlists.values():
                    if pl.status() != STATUS.PLAYING:
                        pl.play()
                super().play()

    def pause(self, playlist_name: str | None = None):
        logger.debug("SoundPlayer.pause(%s)", playlist_name)
        with self._lock:
            if playlist_name is not None:
                return self._playlists[playlist_name].pause()
            else:
                for pl in self._playlists.values():
                    if pl.status() != STATUS.PAUSED:
                        pl.pause()
                super().pause()

    def stop(self, playlist_name: str | None = None):
        logger.debug("SoundPlayer.stop(%s)", playlist_name)
        with self._lock:
            if playlist_name is not None:
                return self._playlists[playlist_name].stop()
            else:
                for pl in self._playlists.values():
                    pl.stop()
                super().stop()

    def __getitem__(self, playlist_name: str):
        return self._playlists[playlist_name]
