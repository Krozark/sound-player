"""SoundPlayer module for managing multiple audio layers."""

import logging
import threading

import numpy as np

from .audiolayer import AudioLayer
from .core.audio_config import AudioConfig
from .core.state import STATUS, StatusObject

logger = logging.getLogger(__name__)

__all__ = [
    "SoundPlayer",
]


class SoundPlayer(StatusObject):
    """Manages multiple audio layers with master mixing.

    The SoundPlayer:
    - Creates and manages named AudioLayers
    - Mixes output from all active layers
    - Provides master volume control
    - Handles bulk operations across layers
    """

    def __init__(self, config: AudioConfig | None = None):
        """Initialize the SoundPlayer.

        Args:
            config: AudioConfig for audio output format
        """
        super().__init__()
        self._config = config or AudioConfig()
        self._audio_layers: dict[str, AudioLayer] = {}
        self._lock = threading.RLock()
        self._master_volume = 1.0

        # Master mixer for combining all audio layers
        from .mixer import AudioMixer

        self._master_mixer: AudioMixer = AudioMixer(self._config, volume=1.0)

    @property
    def config(self) -> AudioConfig:
        """Get the audio configuration."""
        return self._config

    def set_master_volume(self, volume: float) -> None:
        """Set the master volume.

        Args:
            volume: Master volume (0.0 to 1.0)
        """
        logger.debug("SoundPlayer.set_master_volume(%s)", volume)
        with self._lock:
            self._master_volume = max(0.0, min(1.0, volume))
            self._master_mixer.set_volume(self._master_volume)

    def get_master_volume(self) -> float:
        """Get the master volume.

        Returns:
            Master volume (0.0 to 1.0)
        """
        return self._master_volume

    def create_audio_layer(self, layer, force=False, *args, **kwargs):
        """Create a new audio layer.

        Args:
            layer: Unique identifier for the layer
            force: If True, overwrite existing layer
            *args, **kwargs: Arguments passed to AudioLayer constructor
        """
        logger.debug("SoundPlayer.create_audio_layer(%s)", layer)
        with self._lock:
            if layer in self._audio_layers:
                if not force:
                    logger.warning(f"AudioLayer {layer} already exists")
                    return
                logger.debug(f"AudioLayer {layer} exists, overwriting due to force=True")
            # Pass config to AudioLayer if not provided
            if "config" not in kwargs:
                kwargs["config"] = self._config
            self._audio_layers[layer] = AudioLayer(*args, **kwargs)

    def enqueue(self, sound, layer):
        """Add a sound to a specific audio layer.

        Args:
            sound: The sound to enqueue
            layer: The audio layer to add to
        """
        logger.debug("SoundPlayer.enqueue(%s, %s)", sound, layer)
        if layer not in self._audio_layers:
            logger.error(f"AudioLayer {layer} not found")
            return

        with self._lock:
            if layer in self._audio_layers:
                if self._status == STATUS.PLAYING:
                    self._audio_layers[layer].play()
                elif self._status == STATUS.PAUSED:
                    self._audio_layers[layer].pause()
            self._audio_layers[layer].enqueue(sound)

    def status(self, layer=None):
        """Get the status of a layer or the player.

        Args:
            layer: Specific layer to check, or None for player status

        Returns:
            STATUS of the specified layer or player
        """
        logger.debug("SoundPlayer.status(%s)", layer)
        if layer is not None:
            return self._audio_layers[layer].status()
        return super().status()

    def get_audio_layers(self):
        """Get all audio layer names.

        Returns:
            Dictionary keys of all audio layers
        """
        logger.debug("SoundPlayer.get_audio_layers()")
        return self._audio_layers.keys()

    def clear(self, layer=None):
        """Clear queues for a layer or all layers.

        Args:
            layer: Specific layer to clear, or None for all layers
        """
        logger.debug("SoundPlayer.clear(%s)", layer)
        if layer is not None:
            self._audio_layers[layer].clear()
        else:
            for audio_layer in self._audio_layers.values():
                audio_layer.clear()

    def delete_audio_layer(self, layer):
        """Delete an audio layer.

        Args:
            layer: The layer to delete
        """
        logger.debug("SoundPlayer.delete_audio_layer(%s)", layer)
        with self._lock:
            self._audio_layers[layer].stop()
            del self._audio_layers[layer]

    def play(self, layer=None):
        """Start playback of a layer or all layers.

        Args:
            layer: Specific layer to play, or None for all layers
        """
        logger.debug("SoundPlayer.play(%s)", layer)
        with self._lock:
            if layer is not None:
                return self._audio_layers[layer].play()
            else:
                for audio_layer in self._audio_layers.values():
                    if audio_layer.status() != STATUS.PLAYING:
                        audio_layer.play()
                super().play()

    def pause(self, layer=None):
        """Pause playback of a layer or all layers.

        Args:
            layer: Specific layer to pause, or None for all layers
        """
        logger.debug("SoundPlayer.pause(%s)", layer)
        with self._lock:
            if layer is not None:
                return self._audio_layers[layer].pause()
            else:
                for audio_layer in self._audio_layers.values():
                    if audio_layer.status() != STATUS.PAUSED:
                        audio_layer.pause()
                super().pause()

    def stop(self, layer=None):
        """Stop playback of a layer or all layers.

        Args:
            layer: Specific layer to stop, or None for all layers
        """
        logger.debug("SoundPlayer.stop(%s)", layer)
        with self._lock:
            if layer is not None:
                return self._audio_layers[layer].stop()
            else:
                for audio_layer in self._audio_layers.values():
                    audio_layer.stop()
                super().stop()

    def __getitem__(self, layer):
        """Get an audio layer by name.

        Args:
            layer: The layer name

        Returns:
            The AudioLayer instance
        """
        return self._audio_layers[layer]

    def get_next_chunk(self) -> np.ndarray:
        """Get the next mixed chunk from all active audio layers.

        Returns:
            Mixed audio buffer from all active layers
        """
        active_layers = [layer for layer in self._audio_layers.values() if layer.status() == STATUS.PLAYING]

        if not active_layers:
            return np.zeros(
                (self._config.buffer_size, self._config.channels),
                dtype=self._config.dtype,
            )

        # Mix all active layers
        mixed = np.zeros(
            (self._config.buffer_size, self._config.channels),
            dtype=np.float32,
        )

        for layer in active_layers:
            chunk = layer.get_next_chunk()
            if chunk is not None and chunk.size > 0:
                # Apply layer volume (already applied by layer mixer, but master volume applied here)
                mixed += chunk.astype(np.float32)

        # Apply master volume and clip
        mixed *= self._master_volume
        mixed = np.clip(
            mixed,
            self._config.min_sample_value,
            self._config.max_sample_value,
        )

        return mixed.astype(self._config.dtype)
