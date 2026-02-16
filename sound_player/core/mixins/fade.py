"""Fade mixin for managing fade-in/fade-out effects."""

import logging
import math
import time
from enum import IntEnum

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


class FadeMixin(VolumeMixin):
    """Mixin for managing fade-in/fade-out state with time-based volume curves.

    Provides fade state tracking and calculation with configurable curve types.
    Thread-safe via inherited VolumeMixin (which inherits from LockMixin).
    """

    def __init__(self, fade_curve: FadeCurve = FadeCurve.LINEAR, *args, **kwargs):
        """Initialize the fade mixin.

        Args:
            fade_curve: Type of fade curve to use
            volume: Initial volume (0.0-1.0), defaults to 1.0
        """
        super().__init__(*args, **kwargs)
        self._fade_curve = fade_curve

        self._fade_state = FadeState.NONE
        self._fade_start_time = 0.0
        self._fade_duration = 0.0
        self._fade_start_volume = 1.0
        self._fade_target_volume = 1.0

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
            self._fade_start_time = time.time()
            self._fade_duration = duration
            self._fade_start_volume = 0.0
            self._fade_target_volume = max(0.0, min(1.0, target_volume))

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
            self._fade_start_time = time.time()
            self._fade_duration = duration
            self._fade_start_volume = self._volume
            self._fade_target_volume = max(0.0, min(1.0, target_volume))

    def get_fade_multiplier(self) -> float:
        """Get current fade multiplier based on elapsed time.

        Returns:
            Current fade multiplier (0.0-1.0). Returns 1.0 if not fading.
        """
        with self._lock:
            if self._fade_state == FadeState.NONE:
                return 1.0

            elapsed = time.time() - self._fade_start_time
            progress = min(1.0, max(0.0, elapsed / self._fade_duration))

            # Apply curve
            curved_progress = self._apply_curve(progress)

            # Calculate multiplier based on fade direction
            if self._fade_state == FadeState.FADING_IN:
                multiplier = (
                    self._fade_start_volume + (self._fade_target_volume - self._fade_start_volume) * curved_progress
                )
            else:  # FADING_OUT
                multiplier = (
                    self._fade_start_volume + (self._fade_target_volume - self._fade_start_volume) * curved_progress
                )

            # Check if fade is complete
            if progress >= 1.0:
                self._fade_state = FadeState.NONE

            return max(0.0, min(1.0, multiplier))

    def _apply_curve(self, progress: float) -> float:
        """Apply fade curve to progress (0.0-1.0).

        Args:
            progress: Linear progress value (0.0-1.0)

        Returns:
            Curved progress value (0.0-1.0)
        """
        if self._fade_curve == FadeCurve.EXPONENTIAL:
            # Power curve for more natural audio fade
            return progress**2
        elif self._fade_curve == FadeCurve.LOGARITHMIC:
            # Logarithmic curve (using base-10 log)
            # Map 0-1 to 1-10, apply log10, then map back to 0-1
            return math.log10(1 + progress * 9) / math.log10(10)
        elif self._fade_curve == FadeCurve.SCURVE:
            # Smooth step function (ease-in-ease-out)
            return progress * progress * (3 - 2 * progress)
        return progress  # LINEAR

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
