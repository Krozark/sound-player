"""Android platform implementation for the sound-player library.

This module provides Android-specific audio functionality including MediaPlayer-based
audio playback and AudioTrack-based audio output.
"""

from .player import AndroidSoundPlayer
from .sound import AndroidPCMSound

__all__ = [
    "AndroidPCMSound",
    "AndroidSoundPlayer",
]
