import logging
import time

import vlc

from .sound import BaseSound

logger = logging.getLogger(__name__)


class VLCSound(BaseSound):
    def __init__(self, filepath, **kwargs):
        super().__init__(filepath, **kwargs)
        self._instance = vlc.Instance()
        self._player = self._instance.media_player_new()
        self._loop_done = 0

        self._setup_event_handlers()
        self._setup_media()

    def set_volume(self, volume: int):
        super().set_volume(volume)
        self._apply_volume()

    def _do_play(self):
        logger.debug("VLCSound._do_play()")
        self._player.play()

    def _do_pause(self):
        logger.debug("VLCSound._do_pause()")
        self._player.pause()

    def _do_stop(self):
        logger.debug("VLCSound._do_stop()")
        self._player.stop()

    def _setup_media(self):
        logger.debug("VLCSound._setup_media()")
        media = self._instance.media_new(self._filepath)
        self._player.set_media(media)

    def _setup_event_handlers(self):
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end)
        # events.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_play)
        # events.event_attach(vlc.EventType.MediaPlayerPaused, self._on_pause)
        # events.event_attach(vlc.EventType.MediaPlayerStopped, self._on_stop)

    def _on_end(self, event):
        logger.debug("VLCSound._on_end()")
        self._loop_done += 1

        if self._loop == -1 or int(self._loop) > self._loop_done:
            logger.debug("more loop to do")
            self._do_stop()
            self._setup_media()
            time.sleep(0.05)
            self._do_play()
        else:
            self.stop()

    # def _on_play(self, event):
    #     logger.debug("VLCSound._on_play()")
    #     self._apply_volume()
    #     #super().play()
    #
    # def _on_pause(self, event):
    #     logger.debug("VLCSound._on_pause()")
    #     #super().pause()
    #
    # def _on_stop(self, event):
    #     logger.debug("VLCSound._on_stop()")
    #     #super().stop()

    def _apply_volume(self):
        if self._volume is not None:
            try:
                logger.debug("VLCSound: Applying volume %s", self._volume)
                self._player.audio_set_volume(self._volume)
            except Exception as e:
                logger.warning("VLCSound: Failed to set volume: %s", e)
