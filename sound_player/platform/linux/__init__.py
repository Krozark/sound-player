"""Linux platform implementation for the sound-player library.

This module provides Linux-specific audio functionality including PCM sound decoding.
"""

from .sound import LinuxPCMSound

__all__ = [
    "LinuxPCMSound",
    "LinuxSound",
    "Sound",
]

# For backward compatibility and direct access
LinuxSound = LinuxPCMSound
Sound = LinuxSound
