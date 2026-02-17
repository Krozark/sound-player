"""Fade mixin for managing fade-in/fade-out effects."""

import logging
from enum import IntEnum

import numpy as np

from .volume import VolumeMixin

logger = logging.getLogger(__name__)


class FadeState(IntEnum):
    """Fade state enumeration for tracking fade operations."""

    NONE = 0
    FADING_IN = 1
    FADING_OUT = 2


class FadeCurve(IntEnum):
    """Fade curve types for volume interpolation."""

    LINEAR = 0
    EXPONENTIAL = 1  # Power curve (more natural for audio)
    LOGARITHMIC = 2  # Logarithmic curve
    SCURVE = 3  # S-curve (ease-in-ease-out)
    DEFAULT = SCURVE


class FadeMixin(VolumeMixin):
    """Mixin for managing fade-in/fade-out state with time-based volume curves.

    Provides fade state tracking and calculation with configurable curve types.
    Thread-safe via inherited VolumeMixin (which inherits from LockMixin).
    """

    def __init__(self, fade_curve: FadeCurve = FadeCurve.DEFAULT, *args, **kwargs):
        """Initialize the fade mixin.

        Args:
            fade_curve: Type of fade curve to use
            volume: Initial volume (0.0-1.0), defaults to 1.0
        """
        super().__init__(*args, **kwargs)
        self._fade_curve = fade_curve

        self._fade_state = FadeState.NONE
        self._fade_start_volume = 1.0
        self._fade_target_volume = 1.0
        self._samples_processed = 0
        self._total_fade_samples = 0

    def start_fade_in(self, duration: float, target_volume: float = 1.0) -> None:
        """Start a fade-in from 0 to target_volume over duration seconds.

        Args:
            duration: Fade duration in seconds
            target_volume: Target volume (0.0-1.0)
        """
        logger.debug(f"start_fade_in(duration={duration}, target_volume={target_volume})")
        with self._lock:
            if duration <= 0:
                logger.debug("Fade duration <= 0, setting volume directly")
                return
            self._fade_state = FadeState.FADING_IN
            self._fade_start_volume = 0.0
            self._fade_target_volume = max(0.0, min(1.0, target_volume))
            self._samples_processed = 0
            self._total_fade_samples = int(duration * self.config.sample_rate) or 1  # Avoid division by zero

    def start_fade_out(self, duration: float, target_volume: float = 0.0) -> None:
        """Start a fade-out from current volume to target_volume.

        Args:
            duration: Fade duration in seconds
            target_volume: Target volume (0.0-1.0)
        """
        logger.debug(f"start_fade_out(duration={duration}, target_volume={target_volume})")
        with self._lock:
            if duration <= 0:
                logger.debug("Fade duration <= 0, setting volume directly")
                return
            self._fade_state = FadeState.FADING_OUT
            self._fade_start_volume = self._volume
            self._fade_target_volume = max(0.0, min(1.0, target_volume))
            self._samples_processed = 0
            # Calculate fade progress based on samples
            self._total_fade_samples = int(duration * self.config.sample_rate) or 1  # Avoid division by zero

    def _get_fade_multiplier_array(self, size: int) -> np.ndarray:
        """Calculate the fade multiplier array for the current chunk.

        Uses sample counting instead of time.time() for sample-accurate transitions.
        """
        with self._lock:
            # If no fade, return constant target volume array
            if self._fade_state == FadeState.NONE:
                return np.full(size, self._fade_target_volume, dtype=np.float32)

            total = self._total_fade_samples
            start_pos = self._samples_processed
            end_pos = start_pos + size

            # Check if fade completes within this chunk
            fade_complete = end_pos >= total

            # Generate linear progress ramp for this chunk
            start_progress = start_pos / total
            end_progress = min(end_pos / total, 1.0)
            progress_steps = np.linspace(start_progress, end_progress, size, dtype=np.float32)

            # Apply the selected curve (vectorized)
            curved_progress = self._apply_curve_vectorized(progress_steps)

            # Calculate actual volume multipliers: Start + (Diff * Progress)
            vol_diff = self._fade_target_volume - self._fade_start_volume
            multipliers = self._fade_start_volume + vol_diff * curved_progress

            # Update internal counter
            self._samples_processed = end_pos

            # Handle fade completion
            if fade_complete:
                self._fade_state = FadeState.NONE
                self._samples_processed = 0
                # Force exact target volume at the end to avoid float drift
                multipliers[-1] = self._fade_target_volume

            return multipliers

    def _apply_curve_vectorized(self, progress: np.ndarray) -> np.ndarray:
        """Apply fade curve to a numpy array of progress values (0.0-1.0).

        Vectorized version for high-performance buffer processing.
        """
        if self._fade_curve == FadeCurve.EXPONENTIAL:
            # Power curve (x^2) - smoother natural fade
            return np.power(progress, 2)
        elif self._fade_curve == FadeCurve.LOGARITHMIC:
            # Equal Power approximation using Sine window
            # Best for crossfades to maintain constant energy
            return np.sin(progress * (np.pi / 2))
        elif self._fade_curve == FadeCurve.SCURVE:
            # Smoothstep (3x^2 - 2x^3)
            # Standard easing function for polished feel
            return progress * progress * (3 - 2 * progress)

        # Default: LINEAR
        return progress

    def set_fade_curve(self, curve: FadeCurve) -> None:
        """Set the fade curve type.

        Args:
            curve: FadeCurve enum value
        """
        logger.debug(f"set_fade_curve({curve})")
        with self._lock:
            self._fade_curve = curve

    @property
    def fade_state(self) -> FadeState:
        """Get the current fade state."""
        return self._fade_state

    @property
    def fade_curve(self) -> FadeCurve:
        """Get the current fade curve type."""
        return self._fade_curve

    @property
    def is_fading(self) -> bool:
        """Check if currently fading in or out.

        Returns:
            True if currently fading
        """
        return self._fade_state != FadeState.NONE

    def fade_in(self, duration: float, target_volume: float = 1.0) -> None:
        """Start a fade-in from 0 to target_volume over duration seconds.

        Args:
            duration: Fade duration in seconds
            target_volume: Target volume (0.0-1.0)
        """
        logger.debug(f"fade_in(duration={duration}, target_volume={target_volume})")
        self.start_fade_in(duration, target_volume)

    def fade_out(self, duration: float, target_volume: float = 0.0) -> None:
        """Start a fade-out from current volume to target_volume.

        Args:
            duration: Fade duration in seconds
            target_volume: Target volume (0.0-1.0)
        """
        logger.debug(f"fade_out(duration={duration}, target_volume={target_volume})")
        self.start_fade_out(duration, target_volume)
