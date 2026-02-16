"""Audio mixing engine using NumPy.

This module provides the AudioMixer class which handles real-time mixing
of multiple audio streams with support for volume control at multiple levels.
"""

import logging
import threading
from typing import TYPE_CHECKING

import numpy as np

from .core.audio_config import AudioConfig

if TYPE_CHECKING:
    from .core.base_sound import BaseSound

logger = logging.getLogger(__name__)

__all__ = [
    "AudioMixer",
]


class AudioMixer:
    """Mixes multiple audio streams into a single output buffer.

    The mixer handles:
    - Mixing multiple audio streams
    - Individual sound volume control
    - Master volume control
    - Clipping prevention to avoid distortion

    Volume hierarchy: final = (sound1 * vol1 + sound2 * vol2 + ...) * master_volume
    """

    def __init__(self, config: AudioConfig, volume: float = 1.0):
        """Initialize the AudioMixer.

        Args:
            config: AudioConfig defining the audio format
            volume: Master volume (0.0 to 1.0)
        """
        self._config = config
        self._volume = max(0.0, min(1.0, volume))
        self._sounds: list[BaseSound] = []
        self._lock = threading.RLock()

    @property
    def config(self) -> AudioConfig:
        """Get the audio configuration."""
        return self._config

    @property
    def volume(self) -> float:
        """Get the master volume."""
        return self._volume

    def set_volume(self, volume: float) -> None:
        """Set the master volume.

        Args:
            volume: Master volume (0.0 to 1.0)
        """
        with self._lock:
            self._volume = max(0.0, min(1.0, volume))

    @property
    def sound_count(self) -> int:
        """Get the number of sounds in the mixer."""
        with self._lock:
            return len(self._sounds)

    def add_sound(self, sound: "BaseSound") -> None:
        """Add a sound to the mixer.

        Args:
            sound: The sound to add
        """
        with self._lock:
            if sound not in self._sounds:
                self._sounds.append(sound)
                logger.debug(f"Added sound {sound} to mixer")

    def remove_sound(self, sound: "BaseSound") -> None:
        """Remove a sound from the mixer.

        Args:
            sound: The sound to remove
        """
        with self._lock:
            if sound in self._sounds:
                self._sounds.remove(sound)
                logger.debug(f"Removed sound {sound} from mixer")

    def remove_all_sounds(self) -> None:
        """Remove all sounds from the mixer."""
        with self._lock:
            self._sounds.clear()
            logger.debug("Cleared all sounds from mixer")

    def get_active_sounds(self) -> list["BaseSound"]:
        """Get list of currently active (playing) sounds.

        Returns:
            List of sounds that are in PLAYING status
        """
        from .core.state import STATUS

        with self._lock:
            return [s for s in self._sounds if s.status() == STATUS.PLAYING]

    def get_next_chunk(self) -> np.ndarray:
        """Mix all active sounds and return combined buffer.

        This method:
        1. Gets the next chunk from each active sound
        2. Applies individual sound volumes
        3. Sums all chunks using NumPy
        4. Clips to prevent overflow/distortion
        5. Applies master volume

        Returns:
            Mixed audio buffer as numpy array with shape (buffer_size, channels)
        """
        active_sounds = self.get_active_sounds()

        if not active_sounds:
            return self._get_silence()

        # Initialize output buffer with zeros
        mixed = np.zeros((self._config.buffer_size, self._config.channels), dtype=np.float32)

        for sound in active_sounds:
            try:
                chunk = sound.get_next_chunk(self._config.buffer_size)
                if chunk is None or chunk.size == 0:
                    continue

                # Apply individual sound volume (convert 0-100 to 0.0-1.0)
                sound_volume = sound._volume / 100.0 if sound._volume is not None else 1.0
                chunk_float = chunk.astype(np.float32) * sound_volume

                # Handle channel mismatch
                if chunk_float.shape[1] != self._config.channels:
                    chunk_float = self._convert_channels(chunk_float, self._config.channels)

                # Ensure chunk size matches buffer size
                if chunk_float.shape[0] != self._config.buffer_size:
                    chunk_float = self._adjust_length(chunk_float, self._config.buffer_size)

                mixed += chunk_float

            except Exception as e:
                logger.warning(f"Error mixing sound {sound}: {e}")
                continue

        # Apply master volume and clip to prevent overflow
        mixed *= self._volume
        mixed = np.clip(
            mixed,
            self._config.min_sample_value,
            self._config.max_sample_value,
        )

        # Convert back to target dtype
        return mixed.astype(self._config.dtype)

    def _get_silence(self) -> np.ndarray:
        """Get a silent buffer.

        Returns:
            Silent audio buffer
        """
        return np.zeros(
            (self._config.buffer_size, self._config.channels),
            dtype=self._config.dtype,
        )

    def _convert_channels(self, chunk: np.ndarray, target_channels: int) -> np.ndarray:
        """Convert audio chunk to target channel count.

        Args:
            chunk: Input audio chunk
            target_channels: Target number of channels (1 or 2)

        Returns:
            Audio chunk with converted channels
        """
        if chunk.shape[1] == target_channels:
            return chunk

        if chunk.shape[1] == 1 and target_channels == 2:
            # Mono to stereo: duplicate the channel
            return np.repeat(chunk, 2, axis=1)

        if chunk.shape[1] == 2 and target_channels == 1:
            # Stereo to mono: average the channels
            return np.mean(chunk, axis=1, keepdims=True)

        return chunk

    def _adjust_length(self, chunk: np.ndarray, target_length: int) -> np.ndarray:
        """Adjust chunk length to match target buffer size.

        Args:
            chunk: Input audio chunk
            target_length: Target number of samples

        Returns:
            Audio chunk with adjusted length
        """
        current_length = chunk.shape[0]

        if current_length == target_length:
            return chunk

        if current_length < target_length:
            # Pad with zeros
            padding = target_length - current_length
            return np.pad(chunk, ((0, padding), (0, 0)), mode="constant")

        # Truncate
        return chunk[:target_length]
