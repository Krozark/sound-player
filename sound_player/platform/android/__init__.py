"""Android platform implementation for the sound-player library.

This module provides Android-specific audio functionality including MediaPlayer-based
audio playback.
"""

from .sound import ANDROID_AVAILABLE, AndroidPCMSound

__all__ = [
    "Sound",
    "AndroidPCMSound",
    "AndroidSound",
    "ANDROID_AVAILABLE",
]

# For backward compatibility and direct access
AndroidSound = AndroidPCMSound
Sound = AndroidSound
