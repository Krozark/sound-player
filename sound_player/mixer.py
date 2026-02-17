"""Audio mixing engine using NumPy.

This module provides the AudioMixer class which handles real-time mixing
of multiple audio streams with support for volume control at multiple levels.
"""

import logging

import numpy as np

from .core.audio_config import AudioConfig
from .core.base_sound import BaseSound
from .core.mixins import STATUS, LockMixin

logger = logging.getLogger(__name__)

__all__ = [
    "AudioMixer",
]


class AudioMixer(LockMixin):
    """Mixes multiple audio streams into a single output buffer.

    The mixer handles:
    - Mixing multiple audio streams
    - Individual sound volume control
    - Master volume control
    - Clipping prevention to avoid distortion

    Volume hierarchy: final = (sound1 * vol1 + sound2 * vol2 + ...) * master_volume
    """

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self._sounds: list[BaseSound] = []
        self._silence: np.ndarray | None = None

    @property
    def config(self) -> AudioConfig:
        """Get the audio configuration."""
        return self._owner.config

    @property
    def volume(self) -> float:
        return self._owner.volume

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

        # Cache config lookups (avoid repeated property access in hot loop)
        cfg = self.config
        buffer_size = cfg.buffer_size
        channels = cfg.channels
        min_val = cfg.min_sample_value
        max_val = cfg.max_sample_value
        target_dtype = cfg.dtype

        # Initialize output buffer with zeros
        mixed = np.zeros((buffer_size, channels), dtype=np.float32)

        for sound in active_sounds:
            try:
                chunk = sound.get_next_chunk(buffer_size)
                if chunk is None or chunk.size == 0:
                    continue

                # Apply individual sound volume (0.0-1.0)
                # Avoid copy if already float32
                if chunk.dtype == np.float32:
                    chunk_float = chunk * sound.volume
                else:
                    chunk_float = chunk.astype(np.float32) * sound.volume

                # Handle channel mismatch
                if chunk_float.shape[1] != channels:
                    chunk_float = self._convert_channels(chunk_float, channels)

                # Ensure chunk size matches buffer size
                if chunk_float.shape[0] != buffer_size:
                    chunk_float = self._adjust_length(chunk_float, buffer_size)

                mixed += chunk_float

            except Exception as e:
                logger.warning(f"Error mixing sound {sound}: {e}")
                continue

        # Apply master volume and clip to prevent overflow
        master_vol = self.volume
        if master_vol != 1.0:
            mixed *= master_vol
        np.clip(mixed, min_val, max_val, out=mixed)

        # Convert back to target dtype
        return mixed.astype(target_dtype)

    def _get_silence(self) -> np.ndarray:
        """Get a silent buffer (cached).

        Returns:
            Silent audio buffer
        """
        cfg = self.config
        expected_shape = (cfg.buffer_size, cfg.channels)
        if self._silence is None or self._silence.shape != expected_shape or self._silence.dtype != cfg.dtype:
            self._silence = np.zeros(expected_shape, dtype=cfg.dtype)
        return self._silence

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
