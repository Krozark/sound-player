"""Core classes for the sound-player library.

This module contains the base classes and enums used throughout the library.
"""

from .audio_config import AudioConfig
from .state import STATUS, StatusObject

__all__ = [
    "AudioConfig",
    "STATUS",
    "StatusObject",
]
