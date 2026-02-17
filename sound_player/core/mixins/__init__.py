"""Mixin classes for the sound-player library.

This package provides reusable mixins for managing status, volume, locks,
audio configuration, and fade effects.
"""

from .audio_config import AudioConfigMixin, get_global_audio_config, set_global_audio_config
from .fade import FadeCurve, FadeMixin, FadeState
from .lock import LockMixin
from .status import STATUS, StatusMixin
from .volume import VolumeMixin

__all__ = [
    "STATUS",
    "StatusMixin",
    "VolumeMixin",
    "AudioConfigMixin",
    "LockMixin",
    "FadeState",
    "FadeCurve",
    "FadeMixin",
    "get_global_audio_config",
    "set_global_audio_config",
]
