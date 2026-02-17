"""Tests for FadeMixin class."""

import numpy as np

from sound_player.core import AudioConfig, FadeCurve, FadeMixin, FadeState, StatusMixin
from sound_player.core.mixins import AudioConfigMixin


class ConcreteFadeMixin(StatusMixin, AudioConfigMixin, FadeMixin):
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

    def test_default_curve_is_scurve(self):
        """Test that the default fade curve is SCURVE."""
        assert FadeCurve.DEFAULT == FadeCurve.SCURVE


class TestFadeMixin:
    """Tests for the FadeMixin class."""

    def test_initial_fade_state_is_none(self):
        """Test that FadeMixin initializes with NONE fade state."""
        obj = ConcreteFadeMixin()
        assert obj.fade_state == FadeState.NONE
        assert not obj.is_fading

    def test_initial_fade_curve_is_scurve(self):
        """Test that FadeMixin initializes with SCURVE (DEFAULT) fade curve."""
        obj = ConcreteFadeMixin()
        assert obj.fade_curve == FadeCurve.SCURVE

    def test_set_fade_curve_enum(self):
        """Test setting fade curve with enum."""
        obj = ConcreteFadeMixin()
        obj.set_fade_curve(FadeCurve.EXPONENTIAL)
        assert obj.fade_curve == FadeCurve.EXPONENTIAL

    def test_start_fade_in(self):
        """Test starting a fade-in."""
        obj = ConcreteFadeMixin(config=AudioConfig(sample_rate=44100))
        obj.start_fade_in(1.0, 0.5)
        assert obj.fade_state == FadeState.FADING_IN
        assert obj.is_fading

    def test_start_fade_out(self):
        """Test starting a fade-out."""
        obj = ConcreteFadeMixin(config=AudioConfig(sample_rate=44100))
        obj.set_volume(0.8)
        obj.start_fade_out(1.0, 0.0)
        assert obj.fade_state == FadeState.FADING_OUT
        assert obj.is_fading

    def test_fade_multiplier_array_no_fade(self):
        """Test that fade multiplier is target volume when not fading."""
        obj = ConcreteFadeMixin(config=AudioConfig(sample_rate=44100))
        multipliers = obj._get_fade_multiplier_array(512)
        assert multipliers.shape == (512,)
        # Default target volume is 1.0 when no fade has occurred
        np.testing.assert_array_almost_equal(multipliers, np.ones(512))

    def test_fade_multiplier_array_during_fade_in(self):
        """Test fade multiplier array during fade-in."""
        config = AudioConfig(sample_rate=1000)  # 1000 samples/sec for easy math
        obj = ConcreteFadeMixin(config=config, fade_curve=FadeCurve.LINEAR)
        obj.start_fade_in(1.0, 1.0)  # 1 second fade-in = 1000 samples
        # Get first 500 samples (first half of fade)
        multipliers = obj._get_fade_multiplier_array(500)
        # With linear curve, multipliers should ramp from 0 to ~0.5
        assert multipliers[0] < 0.01  # Start near 0
        assert 0.4 < multipliers[-1] < 0.6  # End near 0.5

    def test_fade_multiplier_array_completes(self):
        """Test that fade completes after total samples are consumed."""
        config = AudioConfig(sample_rate=1000)
        obj = ConcreteFadeMixin(config=config, fade_curve=FadeCurve.LINEAR)
        obj.start_fade_in(0.1, 1.0)  # 100 samples total
        # Consume all 100 samples in one chunk
        multipliers = obj._get_fade_multiplier_array(100)
        assert obj.fade_state == FadeState.NONE
        # Last value should be target volume
        assert abs(multipliers[-1] - 1.0) < 0.01

    def test_fade_multiplier_array_during_fade_out(self):
        """Test fade multiplier array during fade-out."""
        config = AudioConfig(sample_rate=1000)
        obj = ConcreteFadeMixin(config=config, fade_curve=FadeCurve.LINEAR, volume=1.0)
        obj.start_fade_out(1.0, 0.0)  # 1 second fade-out
        # Get first 500 samples
        multipliers = obj._get_fade_multiplier_array(500)
        # Should ramp from 1.0 down to ~0.5
        assert multipliers[0] > 0.9
        assert 0.4 < multipliers[-1] < 0.6

    def test_apply_curve_vectorized_linear(self):
        """Test linear fade curve."""
        obj = ConcreteFadeMixin(fade_curve=FadeCurve.LINEAR)
        progress = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float32)
        result = obj._apply_curve_vectorized(progress)
        np.testing.assert_array_almost_equal(result, progress)

    def test_apply_curve_vectorized_exponential(self):
        """Test exponential fade curve (x^2)."""
        obj = ConcreteFadeMixin(fade_curve=FadeCurve.EXPONENTIAL)
        progress = np.array([0.0, 0.5, 1.0], dtype=np.float32)
        result = obj._apply_curve_vectorized(progress)
        expected = np.array([0.0, 0.25, 1.0], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)
        # Exponential should be lower than linear in the middle
        assert result[1] < 0.5

    def test_apply_curve_vectorized_scurve(self):
        """Test s-curve (smoothstep: 3x^2 - 2x^3)."""
        obj = ConcreteFadeMixin(fade_curve=FadeCurve.SCURVE)
        progress = np.array([0.0, 0.5, 1.0], dtype=np.float32)
        result = obj._apply_curve_vectorized(progress)
        # Endpoints
        assert abs(result[0] - 0.0) < 0.01
        assert abs(result[2] - 1.0) < 0.01
        # Symmetric: at 0.5, should be exactly 0.5
        assert abs(result[1] - 0.5) < 0.01

    def test_apply_curve_vectorized_logarithmic(self):
        """Test logarithmic fade curve (sine-based equal power)."""
        obj = ConcreteFadeMixin(fade_curve=FadeCurve.LOGARITHMIC)
        progress = np.array([0.0, 0.5, 1.0], dtype=np.float32)
        result = obj._apply_curve_vectorized(progress)
        # Endpoints
        assert abs(result[0] - 0.0) < 0.01
        assert abs(result[2] - 1.0) < 0.01
        # Logarithmic should be higher than linear in the middle
        assert result[1] > 0.5

    def test_zero_duration_fade(self):
        """Test that zero duration fade doesn't start."""
        obj = ConcreteFadeMixin(config=AudioConfig(sample_rate=44100))
        obj.start_fade_in(0.0, 1.0)
        assert obj.fade_state == FadeState.NONE

    def test_negative_duration_fade(self):
        """Test that negative duration fade doesn't start."""
        obj = ConcreteFadeMixin(config=AudioConfig(sample_rate=44100))
        obj.start_fade_in(-1.0, 1.0)
        assert obj.fade_state == FadeState.NONE
