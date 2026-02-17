"""Tests for FadeMixin class."""

import time

from sound_player.core import FadeCurve, FadeMixin, FadeState, StatusMixin


class ConcreteFadeMixin(StatusMixin, FadeMixin):
    """Concrete implementation of FadeMixin for testing."""

    def _do_play(self):
        pass

    def _do_pause(self):
        pass

    def _do_stop(self):
        pass


class TestFadeState:
    """Tests for the FadeState enum."""

    def test_fade_state_values(self):
        """Test that FadeState enum has correct values."""
        assert FadeState.NONE.value == 0
        assert FadeState.FADING_IN.value == 1
        assert FadeState.FADING_OUT.value == 2

    def test_fade_state_equality(self):
        """Test FadeState enum equality."""
        assert FadeState.FADING_IN == FadeState.FADING_IN
        assert FadeState.FADING_IN != FadeState.FADING_OUT
        assert FadeState.NONE != FadeState.FADING_IN


class TestFadeCurve:
    """Tests for the FadeCurve enum."""

    def test_fade_curve_values(self):
        """Test that FadeCurve enum has correct values."""
        assert FadeCurve.LINEAR.value == 0
        assert FadeCurve.EXPONENTIAL.value == 1
        assert FadeCurve.LOGARITHMIC.value == 2
        assert FadeCurve.SCURVE.value == 3


class TestFadeMixin:
    """Tests for the FadeMixin class."""

    def test_initial_fade_state_is_none(self):
        """Test that FadeMixin initializes with NONE fade state."""
        obj = ConcreteFadeMixin()
        assert obj.fade_state == FadeState.NONE
        assert not obj.is_fading

    def test_initial_fade_curve_is_linear(self):
        """Test that FadeMixin initializes with LINEAR fade curve."""
        obj = ConcreteFadeMixin()
        assert obj.fade_curve == FadeCurve.LINEAR

    def test_set_fade_curve_enum(self):
        """Test setting fade curve with enum."""
        obj = ConcreteFadeMixin()
        obj.set_fade_curve(FadeCurve.EXPONENTIAL)
        assert obj.fade_curve == FadeCurve.EXPONENTIAL

    def test_start_fade_in(self):
        """Test starting a fade-in."""
        obj = ConcreteFadeMixin()
        obj.start_fade_in(1.0, 0.5)
        assert obj.fade_state == FadeState.FADING_IN
        assert obj.is_fading

    def test_start_fade_out(self):
        """Test starting a fade-out."""
        obj = ConcreteFadeMixin()
        obj.set_volume(0.8)
        obj.start_fade_out(1.0, 0.0)
        assert obj.fade_state == FadeState.FADING_OUT
        assert obj.is_fading

    def test_fade_multiplier_no_fade(self):
        """Test that fade multiplier is 1.0 when not fading."""
        obj = ConcreteFadeMixin()
        assert obj.get_fade_multiplier() == 1.0

    def test_fade_multiplier_during_fade_in(self):
        """Test fade multiplier during fade-in (approximately)."""
        obj = ConcreteFadeMixin()
        obj.start_fade_in(0.1, 1.0)
        time.sleep(0.05)  # Halfway through
        multiplier = obj.get_fade_multiplier()
        # Should be approximately 0.5 (allowing for timing variance)
        assert 0.3 < multiplier < 0.7

    def test_fade_multiplier_after_fade_complete(self):
        """Test that fade multiplier returns to 1.0 after fade completes."""
        obj = ConcreteFadeMixin()
        obj.start_fade_in(0.05, 1.0)
        time.sleep(0.1)  # Past completion
        multiplier = obj.get_fade_multiplier()
        assert multiplier == 1.0
        assert obj.fade_state == FadeState.NONE

    def test_fade_multiplier_during_fade_out(self):
        """Test fade multiplier during fade-out (approximately)."""
        obj = ConcreteFadeMixin()
        obj.set_volume(1.0)
        obj.start_fade_out(0.1, 0.0)
        time.sleep(0.05)  # Halfway through
        multiplier = obj.get_fade_multiplier()
        # Should be approximately 0.5 (allowing for timing variance)
        assert 0.3 < multiplier < 0.7

    def test_fade_curve_linear(self):
        """Test linear fade curve."""
        obj = ConcreteFadeMixin(fade_curve=FadeCurve.LINEAR)
        # Check internal curve application
        assert obj._apply_curve(0.0) == 0.0
        assert obj._apply_curve(0.5) == 0.5
        assert obj._apply_curve(1.0) == 1.0

    def test_fade_curve_exponential(self):
        """Test exponential fade curve."""
        obj = ConcreteFadeMixin(fade_curve=FadeCurve.EXPONENTIAL)
        # Exponential curve should have different values
        assert obj._apply_curve(0.0) == 0.0
        assert obj._apply_curve(0.5) == 0.25  # 0.5^2
        assert obj._apply_curve(1.0) == 1.0
        # Exponential should be lower than linear in the middle
        assert obj._apply_curve(0.5) < 0.5

    def test_fade_curve_scurve(self):
        """Test s-curve fade curve."""
        obj = ConcreteFadeMixin(fade_curve=FadeCurve.SCURVE)
        # S-curve properties
        assert obj._apply_curve(0.0) == 0.0
        assert obj._apply_curve(1.0) == 1.0
        # At 0.5, should be exactly 0.5 (symmetric)
        assert abs(obj._apply_curve(0.5) - 0.5) < 0.01

    def test_zero_duration_fade(self):
        """Test that zero duration fade doesn't start."""
        obj = ConcreteFadeMixin()
        obj.start_fade_in(0.0, 1.0)
        # Should not start fading with zero duration
        assert obj.fade_state == FadeState.NONE

    def test_negative_duration_fade(self):
        """Test that negative duration fade doesn't start."""
        obj = ConcreteFadeMixin()
        obj.start_fade_in(-1.0, 1.0)
        # Should not start fading with negative duration
        assert obj.fade_state == FadeState.NONE
