import logging
import threading
import time

from .common import STATUS, StatusObject

logger = logging.getLogger(__name__)


class AudioLayer(StatusObject):
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
        logger.debug("AudioLayer.set_concurrency(%s)", concurrency)
        with self._lock:
            self._concurrency = concurrency

    def set_replace(self, replace):
        logger.debug("AudioLayer.set_replace(%s)", replace)
        with self._lock:
            self._replace_on_add = replace

    def set_loop(self, loop):
        logger.debug("AudioLayer.set_loop(%s)", loop)
        with self._lock:
            self._loop = loop

    def set_volume(self, volume):
        logger.debug("AudioLayer.set_volume(%s)", volume)
        with self._lock:
            self._volume = volume

    def enqueue(self, sound):
        logger.debug("AudioLayer.enqueue(%s)", sound)
        with self._lock:
            logger.debug("enqueue %s" % sound)
            loop = sound._loop or self._loop
            volume = sound._volume or self._volume
            sound.set_loop(loop)
            sound.set_volume(volume)
            self._queue_waiting.append(sound)

    def clear(self):
        logger.debug("AudioLayer.clear()")
        with self._lock:
            self._queue_waiting.clear()
            self._queue_current.clear()

    def pause(self):
        logger.debug("AudioLayer.pause()")
        with self._lock:
            super().pause()
            for sound in self._queue_current:
                sound.pause()

    def stop(self):
        logger.debug("AudioLayer.stop()")
        with self._lock:
            if self._status != STATUS.STOPPED:
                super().stop()
                for sound in self._queue_current:
                    sound.stop()
            self.clear()

    def play(self):
        logger.debug("AudioLayer.play()")
        with self._lock:
            super().play()
            if self._thread is None:
                logger.debug("Create audio layer Thread")
                self._thread = threading.Thread(target=self._thread_task, daemon=True)
                logger.debug("Start audio layer Thread")
                self._thread.start()

            for sound in self._queue_current:
                sound.play()

    def _thread_task(self):
        logger.debug("In audio layer Thread")
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
            logger.debug("Exit audio layer Thread")
        except Exception as e:
            logger.exception(f"Critical error: {e}")
            raise
