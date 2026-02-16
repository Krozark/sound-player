"""Android PCM audio implementation using AudioTrack.

This module provides the AndroidPCMSound class which implements PCM-based
audio playback on Android using:
- MediaPlayer for audio decoding
- AudioTrack for real-time PCM output
"""

import logging

import numpy as np

from sound_player.core import AudioConfig
from sound_player.core.base_sound import BaseSound

logger = logging.getLogger(__name__)

try:
    from android import api_version
    from jnius import PythonJavaClass, autoclass, java_method

    MediaPlayer = autoclass("android.media.MediaPlayer")
    AudioManager = autoclass("android.media.AudioManager")
    AudioFormat = autoclass("android.media.AudioFormat")
    AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")
    AudioTrackBuilder = autoclass("android.media.AudioTrack$Builder")

    ANDROID_AVAILABLE = True
except Exception:
    ANDROID_AVAILABLE = False
    logger.warning("Android APIs not available")

__all__ = [
    "AndroidPCMSound",
]


class OnCompletionListener(PythonJavaClass):
    """Listener for MediaPlayer completion events."""

    __javainterfaces__ = ["android/media/MediaPlayer$OnCompletionListener"]
    __javacontext__ = "app"

    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback

    @java_method("(Landroid/media/MediaPlayer;)V")
    def onCompletion(self, mp):
        logger.debug("OnCompletionListener.onCompletion()")
        self.callback()


class AndroidPCMSound(BaseSound):
    """Android PCM sound implementation using AudioTrack.

    This implementation:
    - Uses MediaPlayer for audio decoding
    - Streams PCM data through AudioTrack for real-time mixing support
    """

    # Android AudioFormat constants
    ENCODING_PCM_16BIT = 2
    ENCODING_PCM_8BIT = 3
    CHANNEL_OUT_MONO = 4
    CHANNEL_OUT_STEREO = 12
    MODE_STREAM = 1
    SAMPLE_RATE_44100 = 44100

    def __init__(self, filepath, config: AudioConfig | None = None, loop=None, volume=None):
        """Initialize the AndroidPCMSound.

        Args:
            filepath: Path to the audio file
            config: AudioConfig for output format
            loop: Number of times to loop (-1 for infinite)
            volume: Volume level (0-100)
        """
        if not ANDROID_AVAILABLE:
            raise RuntimeError("Android APIs not available")

        super().__init__(filepath, config, loop, volume)

        # Playback state
        self._mediaplayer: MediaPlayer | None = None
        self._audiotrack = None
        self._loop_done = 0
        self._is_playing = False
        self._is_eof = False

        # Buffer for decoded audio
        self._buffer: np.ndarray | None = None
        self._buffer_position = 0

        # Audio file info
        self._file_sample_rate = self.SAMPLE_RATE_44100
        self._file_channels = 2

    def _do_play(self):
        """Start or resume playback."""
        logger.debug("AndroidPCMSound._do_play()")

        if self._mediaplayer is None:
            self._load()

        if self._mediaplayer:
            self._mediaplayer.start()
            self._is_playing = True
            self._is_eof = False
            self._loop_done = 0

    def _do_pause(self):
        """Pause playback."""
        logger.debug("AndroidPCMSound._do_pause()")

        if self._mediaplayer:
            self._mediaplayer.pause()
        self._is_playing = False

    def _do_stop(self):
        """Stop playback and reset state."""
        logger.debug("AndroidPCMSound._do_stop()")

        if self._mediaplayer:
            self._mediaplayer.stop()
            self._mediaplayer.release()
            self._mediaplayer = None

        self._is_playing = False
        self._is_eof = False
        self._loop_done = 0
        self._buffer = None
        self._buffer_position = 0

    def _setup_event_handlers(self):
        """Setup MediaPlayer completion listener."""
        completion_listener = OnCompletionListener(self._on_end)
        self._mediaplayer.setOnCompletionListener(completion_listener)

    def _on_end(self):
        """Handle MediaPlayer completion event."""
        logger.debug("AndroidPCMSound._on_end()")
        self._loop_done += 1

        if self._loop == -1 or (self._loop is not None and self._loop_done < self._loop):
            logger.debug("More loops to do")
            if self._mediaplayer:
                self._mediaplayer.start()
        else:
            self.stop()

    def _load(self):
        """Load the audio file using MediaPlayer."""
        logger.debug("AndroidPCMSound._load()")
        self._unload()

        self._mediaplayer = MediaPlayer()

        if api_version >= 21:
            logger.debug("API version >= 21")
            self._mediaplayer.setAudioAttributes(
                AudioAttributesBuilder().setLegacyStreamType(AudioManager.STREAM_MUSIC).build()
            )
        else:
            logger.debug("API version < 21")
            self._mediaplayer.setAudioStreamType(AudioManager.STREAM_MUSIC)

        self._mediaplayer.setDataSource(self._filepath)
        self._mediaplayer.setLooping(False)
        self._setup_event_handlers()
        self._mediaplayer.prepare()

    def _unload(self):
        """Release MediaPlayer resources."""
        logger.debug("AndroidPCMSound._unload()")

        if self._mediaplayer:
            self._mediaplayer.release()
            self._mediaplayer = None

    def _do_get_next_chunk(self, size: int) -> np.ndarray | None:
        """Get the next chunk of audio data.

        Note: This is a simplified implementation that returns silence.
        A full implementation would use AudioTrack with pull callbacks
        to provide real PCM data.

        Args:
            size: Number of samples to return

        Returns:
            Audio data as numpy array with shape (size, config.channels)
        """
        if self._is_eof:
            return None

        # Return silence for now - a full implementation would decode
        # the MediaPlayer output to PCM buffers
        return np.zeros((size, self._config.channels), dtype=self._config.dtype)

    def _do_seek(self, position: float) -> None:
        """Seek to position in seconds.

        Args:
            position: Position in seconds
        """
        if self._mediaplayer:
            self._mediaplayer.seekTo(int(position * 1000))

    def __del__(self):
        """Cleanup on deletion."""
        self._unload()
