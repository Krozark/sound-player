import logging
import threading

from .audiolayer import AudioLayer
from .common import STATUS, StatusObject

logger = logging.getLogger(__name__)


class SoundPlayer(StatusObject):
    def __init__(self):
        super().__init__()
        self._audio_layers: dict[str, AudioLayer] = {}
        self._lock = threading.RLock()

    def create_audio_layer(self, layer, force=False, *args, **kwargs):
        logger.debug("SoundPlayer.create_audio_layer(%s)", layer)
        with self._lock:
            if layer in self._audio_layers:
                if not force:
                    logger.warning(f"AudioLayer {layer} already exists")
                    return
                logger.debug(f"AudioLayer {layer} exists, overwriting due to force=True")
            self._audio_layers[layer] = AudioLayer(*args, **kwargs)

    def enqueue(self, sound, layer):
        logger.debug("SoundPlayer.enqueue(%s, %s)", sound, layer)
        if layer not in self._audio_layers:
            logger.error(f"AudioLayer {layer} not found")
            return

        with self._lock:
            if layer not in self._audio_layers:
                if self._status == STATUS.PLAYING:
                    self._audio_layers[layer].play()
                elif self._status == STATUS.PAUSED:
                    self._audio_layers[layer].pause()
            self._audio_layers[layer].enqueue(sound)

    def status(self, layer=None):
        logger.debug("SoundPlayer.status(%s)", layer)
        if layer is not None:
            return self._audio_layers[layer].status()
        return super().status()

    def get_audio_layers(self):
        logger.debug("SoundPlayer.get_audio_layers()")
        return self._audio_layers.keys()

    def clear(self, layer=None):
        logger.debug("SoundPlayer.clear(%s)", layer)
        if layer is not None:
            self._audio_layers[layer].clear()
        else:
            for audio_layer in self._audio_layers.values():
                audio_layer.clear()

    def delete_audio_layer(self, layer):
        logger.debug("SoundPlayer.delete_audio_layer(%s)", layer)
        with self._lock:
            self._audio_layers[layer].stop()
            del self._audio_layers[layer]

    def play(self, layer=None):
        logger.debug("SoundPlayer.play(%s)", layer)
        with self._lock:
            if layer is not None:
                return self._audio_layers[layer].play()
            else:
                for audio_layer in self._audio_layers.values():
                    if audio_layer.status() != STATUS.PLAYING:
                        audio_layer.play()
                super().play()

    def pause(self, layer=None):
        logger.debug("SoundPlayer.pause(%s)", layer)
        with self._lock:
            if layer is not None:
                return self._audio_layers[layer].pause()
            else:
                for audio_layer in self._audio_layers.values():
                    if audio_layer.status() != STATUS.PAUSED:
                        audio_layer.pause()
                super().pause()

    def stop(self, layer=None):
        logger.debug("SoundPlayer.stop(%s)", layer)
        with self._lock:
            if layer is not None:
                return self._audio_layers[layer].stop()
            else:
                for audio_layer in self._audio_layers.values():
                    audio_layer.stop()
                super().stop()

    def __getitem__(self, layer):
        return self._audio_layers[layer]
