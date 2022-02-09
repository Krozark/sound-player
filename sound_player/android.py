import logging

from android import api_version
from jnius import autoclass, java_method, PythonJavaClass

from .sound import BaseSound, STATUS

logger = logging.getLogger(__name__)

MediaPlayer = autoclass("android.media.MediaPlayer")
AudioManager = autoclass("android.media.AudioManager")
if api_version >= 21:
    AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")


class OnCompletionListener(PythonJavaClass):
    __javainterfaces__ = ["android/media/MediaPlayer$OnCompletionListener"]
    __javacontext__ = "app"

    def __init__(self, callback, **kwargs):
        super(OnCompletionListener, self).__init__(**kwargs)
        self.callback = callback

    @java_method("(Landroid/media/MediaPlayer;)V")
    def onCompletion(self, mp):
        logger.debug("OnCompletionListener.onCompletion()")
        self.callback()


class AndroidSound(BaseSound):

    def __init__(self, *args, **kwargs):
        self._mediaplayer = None
        self._completion_listener = None
        self._loop_done = 0
        super().__init__(*args, **kwargs)

    def __del__(self):
        self._unload()

    def _do_play(self):
        logger.debug("AndroidSound._do_play()")
        if not self._mediaplayer:
            self._load()
        self._loop_done = 0
        self._mediaplayer.start()
        # elif self._status == STATUS.PAUSED:
        #     self._mediaplayer.start()

    def _do_pause(self):
        logger.debug("AndroidSound._do_pause()")
        self._mediaplayer.pause()

    def _do_stop(self):
        logger.debug("AndroidSound._do_stop()")
        # if not self._mediaplayer:
        #     return
        self._mediaplayer.stop()
        self._mediaplayer.prepare()

    def _completion_callback(self):
        logger.debug("AndroidSound._completion_callback()")
        self._loop_done += 1
        if self._loop == 0 or int(self._loop) > self._loop_done:
            logger.debug("more loop to do")
            self._mediaplayer.start()
        else:
            self.stop()

    def _load(self):
        logger.debug("AndroidSound._load()")
        self._unload()
        self._completion_listener = OnCompletionListener(
            self._completion_callback
        )

        self._mediaplayer = MediaPlayer()
        if api_version >= 21:
            logger.debug("API version >= 21")
            self._mediaplayer.setAudioAttributes(
                AudioAttributesBuilder()
                    .setLegacyStreamType(AudioManager.STREAM_MUSIC)
                    .build())
        else:
            logger.debug("API version < 21")
            self._mediaplayer.setAudioStreamType(AudioManager.STREAM_MUSIC)

        self._mediaplayer.setDataSource(self._filepath)
        self._mediaplayer.setOnCompletionListener(self._completion_listener)
        self._mediaplayer.setLooping(False)
        self._mediaplayer.prepare()

    def _unload(self):
        logger.debug("AndroidSound._unload()")
        if self._mediaplayer:
            self._mediaplayer.release()
            self._mediaplayer = None
        self._completion_listener = None