"""BaseSoundPlayer class for platform-specific audio output.

This module provides the BaseSoundPlayer abstract base class which defines
the interface for platform-specific audio output implementations.
"""

import logging
from abc import ABC, abstractmethod

import numpy as np

from sound_player.audiolayer import AudioLayer

from .mixins import STATUS, AudioConfigMixin, StatusMixin, VolumeMixin

logger = logging.getLogger(__name__)

__all__ = [
    "BaseSoundPlayer",
]


class BaseSoundPlayer(StatusMixin, VolumeMixin, AudioConfigMixin, ABC):
    """Base class for platform-specific audio output.

    The BaseSoundPlayer:
    - Manages multiple audio layers with independent mixing
    - Handles bulk operations across layers
    - Delegates actual audio output to platform-specific subclasses

    Platform-specific implementations must implement:
    - _create_output_stream(): Create the platform's audio output stream
    - _close_output_stream(): Close/release the audio output stream
    """

    def __init__(self, *args, **kwargs):
        """Initialize the BaseSoundPlayer.

        Args:
            config: AudioConfig for audio output format
        """
        super().__init__(*args, **kwargs)
        self._audio_layers: dict[str, AudioLayer] = {}

    def create_audio_layer(self, layer, force=False, *args, **kwargs) -> AudioLayer:
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
                    return self._audio_layers[layer]
                logger.debug(f"AudioLayer {layer} exists, overwriting due to force=True")

            # Pass config to AudioLayer if not provided
            if "config" not in kwargs:
                kwargs["config"] = self.config
            new_layer = AudioLayer(*args, **kwargs)
            self._audio_layers[layer] = new_layer
            return new_layer

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

    def play(self, layer=None, *args, **kwargs):
        """Start playback of a layer or all layers.

        Args:
            layer: Specific layer to play, or None for all layers

        For the player (layer=None), this also starts the audio output stream.
        """
        logger.debug("BasePlayer.play(%s)", layer)
        with self._lock:
            if layer is not None:
                # Play specific layer only
                return self._audio_layers[layer].play()
            else:
                # Play all layers and start output stream
                for audio_layer in self._audio_layers.values():
                    audio_layer.play()
                super().play(*args, **kwargs)

    def pause(self, layer=None):
        """Pause playback of a layer or all layers.

        Args:
            layer: Specific layer to pause, or None for all layers

        For the player (layer=None), this also pauses the AudioTrack.
        """
        logger.debug("BasePlayer.pause(%s)", layer)
        with self._lock:
            if layer is not None:
                # Pause specific layer only
                return self._audio_layers[layer].pause()
            else:
                # Pause all layers and pause AudioTrack
                for audio_layer in self._audio_layers.values():
                    audio_layer.pause()
                super().pause()

    def stop(self, layer=None):
        """Stop playback of a layer or all layers.

        Args:
            layer: Specific layer to stop, or None for all layers

        For the player (layer=None), this also stops the AudioTrack and
        closes the output stream.
        """
        logger.debug("BasePlayer.stop(%s)", layer)
        with self._lock:
            if layer is not None:
                # Stop specific layer only
                return self._audio_layers[layer].stop()
            else:
                # Stop all layers and close output stream
                for audio_layer in self._audio_layers.values():
                    audio_layer.stop()
                super().stop()

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
        # Cache config lookups (called ~43 times/sec at 44100Hz/1024 buffer)
        cfg = self.config
        buffer_size = cfg.buffer_size
        channels = cfg.channels
        target_dtype = cfg.dtype

        active_layers = [layer for layer in self._audio_layers.values() if layer.status() == STATUS.PLAYING]

        if not active_layers:
            return np.zeros((buffer_size, channels), dtype=target_dtype)

        # Mix all active layers
        mixed = np.zeros((buffer_size, channels), dtype=np.float32)

        master_vol = self.volume
        for layer in active_layers:
            chunk = layer.get_next_chunk()
            if chunk is not None and chunk.size > 0:
                # Layer volume already applied by AudioLayer.mixer
                # Avoid copy if already float32
                if chunk.dtype == np.float32:
                    mixed += chunk * master_vol
                else:
                    mixed += chunk.astype(np.float32) * master_vol

        # Clip in-place to avoid allocation
        np.clip(mixed, cfg.min_sample_value, cfg.max_sample_value, out=mixed)

        return mixed.astype(target_dtype)

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
