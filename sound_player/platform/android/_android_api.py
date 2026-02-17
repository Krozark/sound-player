"""Android API classes and constants for the sound-player library.

Loads all required Android API classes via jnius and exposes the constants
needed for audio decoding and playback configuration.

If loading fails, a critical error is logged and the exception is re-raised.
There is no valid fallback: this module must only be imported on Android.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

try:
    from jnius import PythonJavaClass, autoclass, java_method

    # Media decoding classes
    MediaExtractor = autoclass("android.media.MediaExtractor")
    MediaFormat = autoclass("android.media.MediaFormat")
    MediaCodec = autoclass("android.media.MediaCodec")
    MediaCodecBufferInfo = autoclass("android.media.MediaCodec$BufferInfo")

    # Audio output classes
    AudioTrack = autoclass("android.media.AudioTrack")
    AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")
    AudioFormatBuilder = autoclass("android.media.AudioFormat$Builder")

    # Constant sources (not part of public API, only used to read constants below)
    _AudioFormat = autoclass("android.media.AudioFormat")
    _AudioAttributes = autoclass("android.media.AudioAttributes")

    # AudioFormat constants
    ENCODING_PCM_16BIT = _AudioFormat.ENCODING_PCM_16BIT
    ENCODING_PCM_32BIT = _AudioFormat.ENCODING_PCM_32BIT  # API 31+
    CHANNEL_OUT_MONO = _AudioFormat.CHANNEL_OUT_MONO
    CHANNEL_OUT_STEREO = _AudioFormat.CHANNEL_OUT_STEREO

    # AudioTrack constants
    MODE_STREAM = AudioTrack.MODE_STREAM

    # AudioAttributes constants
    USAGE_MEDIA = _AudioAttributes.USAGE_MEDIA
    CONTENT_TYPE_MUSIC = _AudioAttributes.CONTENT_TYPE_MUSIC

except Exception:
    logger.critical("Failed to load Android APIs - cannot continue", exc_info=True)
    raise

# Maps numpy dtype -> Android PCM encoding constant
ENCODING_BY_DTYPE = {
    np.dtype(np.int16): ENCODING_PCM_16BIT,
    np.dtype(np.int32): ENCODING_PCM_32BIT,
}

# Maps channel count -> Android channel mask constant
CHANNEL_MASK_BY_CHANNELS = {
    1: CHANNEL_OUT_MONO,
    2: CHANNEL_OUT_STEREO,
}

__all__ = [
    # jnius helpers needed by DecodeCallback
    "PythonJavaClass",
    "java_method",
    # Media decoding
    "MediaExtractor",
    "MediaFormat",
    "MediaCodec",
    "MediaCodecBufferInfo",
    # Audio output
    "AudioTrack",
    "AudioAttributesBuilder",
    "AudioFormatBuilder",
    # Constants
    "ENCODING_PCM_16BIT",
    "ENCODING_PCM_32BIT",
    "CHANNEL_OUT_MONO",
    "CHANNEL_OUT_STEREO",
    "MODE_STREAM",
    "USAGE_MEDIA",
    "CONTENT_TYPE_MUSIC",
    # Lookup dicts
    "ENCODING_BY_DTYPE",
    "CHANNEL_MASK_BY_CHANNELS",
]
