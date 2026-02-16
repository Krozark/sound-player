"""Linux platform implementation for the sound-player library.

This module provides Linux-specific audio functionality including PCM sound decoding
and audio output using sounddevice.
"""

from .player import LinuxSoundPlayer
from .sound import LinuxPCMSound

__all__ = [
    "LinuxPCMSound",
    "LinuxSoundPlayer",
]
