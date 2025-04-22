import logging

import vlc

from .sound import STATUS, BaseSound

logger = logging.getLogger(__name__)


class VLCSound(BaseSound):
    def __init__(self, filepath, loop=None):
        super().__init__(filepath, loop)
        self._instance = vlc.Instance()
        self._player = self._instance.media_player_new()
        self._loop_done = 0
        self._setup_callbacks()

    def poll(self):
        state = self._player.get_state()
        if state == vlc.State.Playing:
            return STATUS.PLAYING
        elif state == vlc.State.Paused:
            return STATUS.PAUSED
        elif state in (vlc.State.Stopped, vlc.State.Ended):
            return STATUS.STOPPED
        return self._status

    def _do_play(self):
        logger.debug("VLCSound._do_play()")
        self._player.play()

    def _do_pause(self):
        logger.debug("VLCSound._do_pause()")
        self._player.pause()

    def _do_stop(self):
        logger.debug("VLCSound._do_stop()")
        self._player.stop()

    def _setup_callbacks(self):
        logger.debug("VLCSound._setup_callbacks()")
        self._event_manager = self._player.event_manager()
        self._event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self._on_end_reached,
        )

    def _on_end_reached(self, event):
        logger.debug("VLCSound._on_end_reached()")

        self._player.stop()
        self._loop_done += 1

        if self._loop == -1 or int(self._loop) > self._loop_done:
            logger.debug("more loop to do")
            self._player.play()
