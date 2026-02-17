"""Audio configuration mixin for managing audio settings."""

from ..audio_config import AudioConfig

__all__ = [
    "AudioConfigMixin",
    "get_global_audio_config",
    "set_global_audio_config",
]

_global_audio_config: AudioConfig = AudioConfig()


def get_global_audio_config() -> AudioConfig:
    """Get the global default audio configuration.

    Returns:
        The current global AudioConfig instance.
    """
    return _global_audio_config


def set_global_audio_config(config: AudioConfig) -> None:
    """Set the global default audio configuration.

    All objects that were created without an explicit config will use this
    configuration. Changes take effect immediately for any property access
    that goes through the AudioConfigMixin.config property.

    Args:
        config: The new global AudioConfig instance.
    """
    global _global_audio_config
    if not isinstance(config, AudioConfig):
        raise TypeError(f"Expected AudioConfig, got {type(config).__name__}")
    _global_audio_config = config


class AudioConfigMixin:
    """Mixin class for managing audio configuration.

    Provides an AudioConfig object with a config property. If no config is
    provided at construction time, the global default config (see
    get_global_audio_config / set_global_audio_config) is used and any change
    to the global config is automatically reflected via the config property.
    """

    def __init__(self, config: AudioConfig | None = None, *args, **kwargs):
        """Initialize the audio configuration.

        Args:
            config: AudioConfig instance, or None to use the global default.
        """
        super().__init__(*args, **kwargs)
        self._config = config

    @property
    def config(self) -> AudioConfig:
        """Get the audio configuration.

        Returns the instance-specific config if one was provided at construction
        time, otherwise returns the current global default config.
        """
        if self._config is None:
            return _global_audio_config
        return self._config
