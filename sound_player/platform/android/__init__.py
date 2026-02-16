"""Android platform implementation for the sound-player library.

This module provides Android-specific audio functionality including MediaPlayer-based
audio playback.
"""

from .sound import ANDROID_AVAILABLE, AndroidPCMSound

__all__ = [
    "AndroidPCMSound",
    "ANDROID_AVAILABLE",
]
