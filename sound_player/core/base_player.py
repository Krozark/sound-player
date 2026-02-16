"""BaseSoundPlayer class for platform-specific audio output.

This module provides the BaseSoundPlayer abstract base class which defines
the interface for platform-specific audio output implementations.
"""

import logging
import threading
from abc import ABC, abstractmethod

import numpy as np

from sound_player.audiolayer import AudioLayer

from .audio_config import AudioConfig
from .state import STATUS, StatusObject

logger = logging.getLogger(__name__)

__all__ = [
    "BaseSoundPlayer",
]


class BaseSoundPlayer(StatusObject, ABC):
    """Base class for platform-specific audio output.

    The BaseSoundPlayer:
    - Manages multiple audio layers with independent mixing
    - Handles bulk operations across layers
    - Delegates actual audio output to platform-specific subclasses

    Platform-specific implementations must implement:
    - _create_output_stream(): Create the platform's audio output stream
    - _close_output_stream(): Close/release the audio output stream
    """

    def __init__(self, config: AudioConfig | None = None):
        """Initialize the BaseSoundPlayer.

        Args:
            config: AudioConfig for audio output format
        """
        super().__init__()
        self._config = config or AudioConfig()
        self._audio_layers: dict[str, AudioLayer] = {}
        self._lock = threading.RLock()
        self._volume = 1.0

    @property
    def config(self) -> AudioConfig:
        """Get the audio configuration."""
        return self._config

    def set_volume(self, volume: float) -> None:
        """Set the master volume.

        Args:
            volume: Volume (0.0-1.0)
        """
        logger.debug("BaseSoundPlayer.set_volume(%s)", volume)
        with self._lock:
            self._volume = max(0.0, min(1.0, volume))

    def get_volume(self) -> float:
        """Get the master volume.

        Returns:
            Volume (0.0-1.0)
        """
        return self._volume

    def create_audio_layer(self, layer, force=False, *args, **kwargs):
        """Create a new audio layer.

        Args:
            layer: Unique identifier for the layer
            force: If True, overwrite existing layer
            *args, **kwargs: Arguments passed to AudioLayer constructor
        """
        logger.debug("BaseSoundPlayer.create_audio_layer(%s)", layer)
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
        logger.debug("BaseSoundPlayer.enqueue(%s, %s)", sound, layer)
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
        logger.debug("BaseSoundPlayer.status(%s)", layer)
        if layer is not None:
            return self._audio_layers[layer].status()
        return super().status()

    def get_audio_layers(self):
        """Get all audio layer names.

        Returns:
            Dictionary keys of all audio layers
        """
        logger.debug("BaseSoundPlayer.get_audio_layers()")
        return self._audio_layers.keys()

    def clear(self, layer=None):
        """Clear queues for a layer or all layers.

        Args:
            layer: Specific layer to clear, or None for all layers
        """
        logger.debug("BaseSoundPlayer.clear(%s)", layer)
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
        logger.debug("BaseSoundPlayer.delete_audio_layer(%s)", layer)
        with self._lock:
            self._audio_layers[layer].stop()
            del self._audio_layers[layer]

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

        This method is called by the platform-specific audio output
        implementation to get the next buffer of mixed audio data.

        Returns:
            Mixed audio buffer from all active layers with shape
            (config.buffer_size, config.channels)
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
                mixed += chunk.astype(np.float32)

        # Apply volume and clip
        mixed *= self._volume
        mixed = np.clip(
            mixed,
            self._config.min_sample_value,
            self._config.max_sample_value,
        )

        return mixed.astype(self._config.dtype)

    @abstractmethod
    def _create_output_stream(self):
        """Create the platform-specific audio output stream.

        This method is called when starting playback. The implementation
        should create and configure the audio output device/stream.
        """
        raise NotImplementedError()

    @abstractmethod
    def _close_output_stream(self):
        """Close the platform-specific audio output stream.

        This method is called when stopping playback. The implementation
        should release any audio device resources.
        """
        raise NotImplementedError()
