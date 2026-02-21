"""Core classes for the sound-player library.

This module contains the base classes and enums used throughout the library.
"""

from .audio_config import AudioConfig
from .constants import MAX_INT16, MAX_INT32, MIN_INT16, MIN_INT32
from .mixins import (
    STATUS,
    AudioConfigMixin,
    FadeCurve,
    FadeMixin,
    FadeState,
    StatusMixin,
    VolumeMixin,
    get_global_audio_config,
    set_global_audio_config,
)

__all__ = [
    "AudioConfig",
    "STATUS",
    "StatusMixin",
    "VolumeMixin",
    "AudioConfigMixin",
    "FadeState",
    "FadeCurve",
    "FadeMixin",
    "get_global_audio_config",
    "set_global_audio_config",
    "MAX_INT16",
    "MAX_INT32",
    "MIN_INT16",
    "MIN_INT32",
]
