"""Tests for RandomRepeatSound."""

import wave
from unittest.mock import MagicMock, patch

import pytest

from sound_player.core.audio_config import AudioConfig
from sound_player.sounds import RandomRepeatSound

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def audio_config():
    return AudioConfig(sample_rate=44100, channels=2, sample_width=2, buffer_size=512)


@pytest.fixture
def wav_file(tmp_path):
    """Single minimal WAV file."""
    path = tmp_path / "a.wav"
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\x00\x00" * 2 * 100)
    return str(path)


@pytest.fixture
def wav_files(tmp_path):
    """Two minimal WAV files."""
    paths = []
    for name in ("a.wav", "b.wav"):
        path = tmp_path / name
        with wave.open(str(path), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(44100)
            f.writeframes(b"\x00\x00" * 2 * 100)
        paths.append(str(path))
    return paths


@pytest.fixture
def mock_layer():
    return MagicMock()


@pytest.fixture
def rrs(wav_file, mock_layer, audio_config):
    """Default RandomRepeatSound (loop=None → infinite)."""
    return RandomRepeatSound([wav_file], layer=mock_layer, config=audio_config)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestRandomRepeatSoundInit:
    def test_filepaths_stored(self, wav_files, mock_layer, audio_config):
        s = RandomRepeatSound(wav_files, layer=mock_layer, config=audio_config)
        assert s._filepaths == wav_files

    def test_layer_stored(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, config=audio_config)
        assert s._layer is mock_layer

    def test_loop_none_means_infinite(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, config=audio_config)
        assert s._repeat_remaining is None

    def test_loop_zero_plays_once(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=0, config=audio_config)
        assert s._repeat_remaining == 0

    def test_loop_n_stored(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=5, config=audio_config)
        assert s._repeat_remaining == 5

    def test_min_max_wait_stored(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, min_wait=1.5, max_wait=3.0, config=audio_config)
        assert s._min_wait == 1.5
        assert s._max_wait == 3.0

    def test_on_end_stored_as_final(self, wav_file, mock_layer, audio_config):
        def cb():
            pass

        s = RandomRepeatSound([wav_file], layer=mock_layer, on_end=cb, config=audio_config)
        assert s._final_on_end is cb

    def test_initial_filepath_from_list(self, wav_file, mock_layer, audio_config):
        """Single-file list → always that file."""
        s = RandomRepeatSound([wav_file], layer=mock_layer, config=audio_config)
        assert s._filepath == wav_file

    def test_internal_on_end_is_check_callback(self, wav_file, mock_layer, audio_config):
        """BaseSound._on_end must be wired to _check_for_another_sound.

        Bound methods compare equal (same __self__ + __func__) but are not
        identical objects, so we use == rather than is.
        """
        s = RandomRepeatSound([wav_file], layer=mock_layer, config=audio_config)
        assert s._on_end == s._check_for_another_sound


# ---------------------------------------------------------------------------
# Repeat count semantics  (loop=0, 1, N, None)
# ---------------------------------------------------------------------------


class TestRepeatCountSemantics:
    def test_loop0_does_not_enqueue_again(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=0, config=audio_config)
        s._check_for_another_sound()
        mock_layer.enqueue.assert_not_called()

    def test_loop0_fires_final_on_end(self, wav_file, mock_layer, audio_config):
        called = []
        s = RandomRepeatSound(
            [wav_file], layer=mock_layer, loop=0, on_end=lambda: called.append(1), config=audio_config
        )
        s._check_for_another_sound()
        assert called == [1]

    def test_loop0_no_callback_does_not_raise(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=0, config=audio_config)
        s._check_for_another_sound()  # must not raise

    def test_loop1_first_call_enqueues(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=1, config=audio_config)
        s._check_for_another_sound()
        assert mock_layer.enqueue.call_count == 1

    def test_loop1_second_call_fires_on_end(self, wav_file, mock_layer, audio_config):
        called = []
        s = RandomRepeatSound(
            [wav_file], layer=mock_layer, loop=1, on_end=lambda: called.append(1), config=audio_config
        )
        s._check_for_another_sound()
        s._check_for_another_sound()
        assert called == [1]

    def test_loop1_total_enqueue_count(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=1, config=audio_config)
        s._check_for_another_sound()
        s._check_for_another_sound()
        assert mock_layer.enqueue.call_count == 1

    def test_loop_n_enqueues_exactly_n_times(self, wav_file, mock_layer, audio_config):
        n = 4
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=n, config=audio_config)
        for _ in range(n + 1):  # n enqueue + 1 final stop
            s._check_for_another_sound()
        assert mock_layer.enqueue.call_count == n

    def test_loop_n_final_on_end_fires_once(self, wav_file, mock_layer, audio_config):
        called = []
        n = 3
        s = RandomRepeatSound(
            [wav_file], layer=mock_layer, loop=n, on_end=lambda: called.append(1), config=audio_config
        )
        for _ in range(n + 1):
            s._check_for_another_sound()
        assert called == [1]

    def test_loop_n_final_on_end_not_fired_on_intermediates(self, wav_file, mock_layer, audio_config):
        called = []
        n = 3
        s = RandomRepeatSound(
            [wav_file], layer=mock_layer, loop=n, on_end=lambda: called.append(1), config=audio_config
        )
        for _ in range(n):
            s._check_for_another_sound()
        assert called == []

    def test_infinite_never_fires_final_on_end(self, wav_file, mock_layer, audio_config):
        called = []
        s = RandomRepeatSound(
            [wav_file], layer=mock_layer, loop=None, on_end=lambda: called.append(1), config=audio_config
        )
        for _ in range(10):
            s._check_for_another_sound()
        assert called == []

    def test_infinite_always_enqueues(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, config=audio_config)
        for _ in range(10):
            s._check_for_another_sound()
        assert mock_layer.enqueue.call_count == 10


# ---------------------------------------------------------------------------
# Instance reuse
# ---------------------------------------------------------------------------


class TestInstanceReuse:
    def test_same_object_passed_to_enqueue(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=3, config=audio_config)
        for _ in range(3):
            s._check_for_another_sound()
        for call in mock_layer.enqueue.call_args_list:
            assert call.args[0] is s

    def test_infinite_same_object_passed_to_enqueue(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, config=audio_config)
        for _ in range(5):
            s._check_for_another_sound()
        for call in mock_layer.enqueue.call_args_list:
            assert call.args[0] is s


# ---------------------------------------------------------------------------
# Delay / wait
# ---------------------------------------------------------------------------


class TestWaitDelay:
    def test_delay_within_bounds(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, min_wait=1.0, max_wait=2.0, config=audio_config)
        s._check_for_another_sound()
        delay = mock_layer.enqueue.call_args.kwargs["delay"]
        assert 1.0 <= delay <= 2.0

    def test_zero_wait_gives_zero_delay(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, min_wait=0.0, max_wait=0.0, config=audio_config)
        s._check_for_another_sound()
        delay = mock_layer.enqueue.call_args.kwargs["delay"]
        assert delay == 0.0

    def test_delay_passed_as_keyword(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, config=audio_config)
        s._check_for_another_sound()
        assert "delay" in mock_layer.enqueue.call_args.kwargs


# ---------------------------------------------------------------------------
# File selection
# ---------------------------------------------------------------------------


class TestFileSelection:
    def test_next_filepath_from_filepaths(self, wav_files, mock_layer, audio_config):
        s = RandomRepeatSound(wav_files, layer=mock_layer, loop=None, config=audio_config)
        s._check_for_another_sound()
        assert s._filepath in wav_files

    def test_random_choice_called_with_filepaths(self, wav_files, mock_layer, audio_config):
        s = RandomRepeatSound(wav_files, layer=mock_layer, loop=None, config=audio_config)
        with patch("sound_player.sounds.random.choice", return_value=wav_files[1]) as mock_choice:
            s._check_for_another_sound()
        mock_choice.assert_called_once_with(wav_files)
        assert s._filepath == wav_files[1]


# ---------------------------------------------------------------------------
# State reset via _load_filepath
# ---------------------------------------------------------------------------


class TestStateResetOnReload:
    def test_loop_count_reset(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, config=audio_config)
        s._loop_count = 7
        s._check_for_another_sound()
        assert s._loop_count == 0

    def test_on_start_fired_reset(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, config=audio_config)
        s._on_start_fired = True
        s._check_for_another_sound()
        assert s._on_start_fired is False

    def test_on_end_fired_reset(self, wav_file, mock_layer, audio_config):
        s = RandomRepeatSound([wav_file], layer=mock_layer, loop=None, config=audio_config)
        s._on_end_fired = True
        s._check_for_another_sound()
        assert s._on_end_fired is False

    def test_file_info_updated_for_new_file(self, wav_files, mock_layer, audio_config):
        s = RandomRepeatSound(wav_files, layer=mock_layer, loop=None, config=audio_config)
        with patch("sound_player.sounds.random.choice", return_value=wav_files[1]):
            s._check_for_another_sound()
        assert s._file_info is not None
        assert s._filepath == wav_files[1]
