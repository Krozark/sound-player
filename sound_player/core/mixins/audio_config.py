"""Audio configuration mixin for managing audio settings."""

from ..audio_config import AudioConfig


class AudioConfigMixin:
    """Mixin class for managing audio configuration.

    Provides an AudioConfig object with a config property.
    """

    def __init__(self, config: AudioConfig | None = None, *args, **kwargs):
        """Initialize the audio configuration.

        Args:
            config: AudioConfig instance, or None to use defaults.
        """
        super().__init__(*args, **kwargs)
        self._config = config or AudioConfig()

    @property
    def config(self) -> AudioConfig:
        """Get the audio configuration."""
        return self._config
