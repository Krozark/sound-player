"""Tests for SoundPlayer class."""

import pytest

from sound_player.core.mixins import STATUS
from sound_player.platform.linux.player import LinuxSoundPlayer


class TestBaseSoundPlayerInit:
    """Tests for BaseSoundPlayer initialization."""

    def test_initialization(self):
        """Test BaseSoundPlayer initializes correctly."""
        player = LinuxSoundPlayer()
        assert player._audio_layers == {}
        assert player.status() == STATUS.STOPPED


class TestBaseSoundPlayerCreateAudioLayer:
    """Tests for create_audio_layer method."""

    def test_create_audio_layer_default_params(self):
        """Test creating audio layer with default parameters."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        assert "layer1" in player._audio_layers

    def test_create_audio_layer_with_params(self):
        """Test creating audio layer with custom parameters."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1", concurrency=3, replace=True)
        layer = player._audio_layers["layer1"]
        assert layer._concurrency == 3
        assert layer._replace_on_add is True

    def test_create_multiple_audio_layers(self):
        """Test creating multiple audio layers."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")
        player.create_audio_layer("layer3")
        assert len(player._audio_layers) == 3

    def test_create_duplicate_layer_does_not_overwrite(self):
        """Test that creating a layer with existing ID does not overwrite it."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1", concurrency=2)
        player.create_audio_layer("layer1", concurrency=5)
        # Should keep the original layer with concurrency=2
        assert player._audio_layers["layer1"]._concurrency == 2

    def test_create_duplicate_layer_with_force_overwrites(self):
        """Test that creating a layer with force=True overwrites existing layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1", concurrency=2)
        player.create_audio_layer("layer1", force=True, concurrency=5)
        # Should overwrite with the new layer having concurrency=5
        assert player._audio_layers["layer1"]._concurrency == 5

    def test_create_layer_with_force_false_does_not_overwrite(self):
        """Test that force=False explicitly preserves existing layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1", concurrency=2, replace=True)
        player.create_audio_layer("layer1", force=False, concurrency=5, replace=False)
        # Should keep the original layer's settings
        assert player._audio_layers["layer1"]._concurrency == 2
        assert player._audio_layers["layer1"]._replace_on_add is True


class TestBaseSoundPlayerEnqueue:
    """Tests for enqueue method."""

    def test_enqueue_to_existing_layer(self, mock_sound):
        """Test enqueuing sound to existing layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        sound = mock_sound()

        player.enqueue(sound, "layer1")

        # Sound should be in the layer's waiting queue
        assert len(player._audio_layers["layer1"]._queue_waiting) == 1

    def test_enqueue_to_nonexistent_layer(self, mock_sound, caplog):
        """Test enqueuing to non-existent layer logs error."""
        player = LinuxSoundPlayer()
        sound = mock_sound()

        player.enqueue(sound, "nonexistent")

        # Should not crash, just log error
        assert "nonexistent" not in player._audio_layers

    def test_enqueue_starts_layer_if_player_playing(self, mock_sound):
        """Test that enqueue starts layer if player is playing."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        sound = mock_sound()

        player.play()
        player.enqueue(sound, "layer1")

        # Layer should be playing
        assert player._audio_layers["layer1"].status() == STATUS.PLAYING

        # Cleanup
        player.stop()

    def test_enqueue_pauses_layer_if_player_paused(self, mock_sound):
        """Test that enqueue pauses layer if player is paused."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        sound = mock_sound()

        player.play()
        player.pause()
        player.enqueue(sound, "layer1")

        # Layer should be paused
        assert player._audio_layers["layer1"].status() == STATUS.PAUSED

        # Cleanup
        player.stop()


class TestBaseSoundPlayerStatus:
    """Tests for status method."""

    def test_status_no_argument_returns_player_status(self):
        """Test status() with no argument returns player status."""
        player = LinuxSoundPlayer()
        assert player.status() == STATUS.STOPPED

    def test_status_with_layer_id_returns_layer_status(self):
        """Test status(layer_id) returns specific layer status."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")

        # Layer should be stopped initially
        assert player.status("layer1") == STATUS.STOPPED

        # Play the layer and check again
        player._audio_layers["layer1"].play()
        assert player.status("layer1") == STATUS.PLAYING

        # Cleanup
        player.stop()


class TestBaseSoundPlayerGetAudioLayers:
    """Tests for get_audio_layers method."""

    def test_get_audio_layers_returns_keys(self):
        """Test get_audio_layers returns layer IDs."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")
        player.create_audio_layer("layer3")

        keys = player.get_audio_layers()
        assert set(keys) == {"layer1", "layer2", "layer3"}

    def test_get_audio_layers_empty_player(self):
        """Test get_audio_layers returns empty set when no layers."""
        player = LinuxSoundPlayer()
        assert set(player.get_audio_layers()) == set()


class TestBaseSoundPlayerClear:
    """Tests for clear method."""

    def test_clear_specific_layer(self, mock_sound):
        """Test clearing a specific audio layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")

        sound = mock_sound()
        player._audio_layers["layer1"].enqueue(sound)
        player._audio_layers["layer2"].enqueue(sound)

        player.clear("layer1")

        # Only layer1 should be cleared
        assert len(player._audio_layers["layer1"]._queue_waiting) == 0
        assert len(player._audio_layers["layer2"]._queue_waiting) == 1

    def test_clear_all_layers(self, mock_sound):
        """Test clearing all audio layers."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")
        player.create_audio_layer("layer3")

        sound = mock_sound()
        player._audio_layers["layer1"].enqueue(sound)
        player._audio_layers["layer2"].enqueue(sound)
        player._audio_layers["layer3"].enqueue(sound)

        player.clear()

        # All layers should be cleared
        assert len(player._audio_layers["layer1"]._queue_waiting) == 0
        assert len(player._audio_layers["layer2"]._queue_waiting) == 0
        assert len(player._audio_layers["layer3"]._queue_waiting) == 0

    def test_clear_clears_current_queue(self, mock_sound):
        """Test that clear also clears the current queue."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")

        sound = mock_sound()
        player._audio_layers["layer1"]._queue_current.append(sound)

        player.clear("layer1")

        assert len(player._audio_layers["layer1"]._queue_current) == 0


class TestBaseSoundPlayerDeleteAudioLayer:
    """Tests for delete_audio_layer method."""

    def test_delete_audio_layer(self):
        """Test deleting an audio layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        assert "layer1" in player._audio_layers

        player.delete_audio_layer("layer1")
        assert "layer1" not in player._audio_layers

    def test_delete_audio_layer_stops_layer(self):
        """Test deleting a layer stops it first."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        layer = player._audio_layers["layer1"]
        layer.play()

        player.delete_audio_layer("layer1")

        # Layer should be stopped before deletion
        assert layer.status() == STATUS.STOPPED


class TestBaseSoundPlayerPlay:
    """Tests for play method."""

    def test_play_no_argument_starts_all_layers(self):
        """Test play() with no argument starts all layers."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")
        player.create_audio_layer("layer3")

        player.play()

        for layer_id in ["layer1", "layer2", "layer3"]:
            assert player._audio_layers[layer_id].status() == STATUS.PLAYING

        # Cleanup
        player.stop()

    def test_play_starts_only_stopped_layers(self):
        """Test play() only starts layers that aren't already playing."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")

        # Start layer1 manually
        player._audio_layers["layer1"].play()

        player.play()

        # Both should be playing now
        assert player._audio_layers["layer1"].status() == STATUS.PLAYING
        assert player._audio_layers["layer2"].status() == STATUS.PLAYING

        # Cleanup
        player.stop()

    def test_play_specific_layer(self):
        """Test play(layer_id) starts only that layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")

        player.play("layer1")

        assert player._audio_layers["layer1"].status() == STATUS.PLAYING
        assert player._audio_layers["layer2"].status() == STATUS.STOPPED

        # Cleanup
        player.stop()

    def test_play_changes_player_status(self):
        """Test play() changes player status to PLAYING."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.play()
        assert player.status() == STATUS.PLAYING
        player.stop()


class TestBaseSoundPlayerPause:
    """Tests for pause method."""

    def test_pause_no_argument_pauses_all_layers(self):
        """Test pause() with no argument pauses all layers."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")

        player.play()
        player.pause()

        for layer_id in ["layer1", "layer2"]:
            assert player._audio_layers[layer_id].status() == STATUS.PAUSED

        # Cleanup
        player.stop()

    def test_pause_specific_layer(self):
        """Test pause(layer_id) pauses only that layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")

        player.play()
        player.pause("layer1")

        assert player._audio_layers["layer1"].status() == STATUS.PAUSED
        assert player._audio_layers["layer2"].status() == STATUS.PLAYING

        # Cleanup
        player.stop()

    def test_pause_changes_player_status(self):
        """Test pause() changes player status to PAUSED."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.play()
        player.pause()
        assert player.status() == STATUS.PAUSED
        player.stop()


class TestBaseSoundPlayerStop:
    """Tests for stop method."""

    def test_stop_no_argument_stops_all_layers(self):
        """Test stop() with no argument stops all layers."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")

        player.play()
        player.stop()

        for layer_id in ["layer1", "layer2"]:
            assert player._audio_layers[layer_id].status() == STATUS.STOPPED

    def test_stop_specific_layer(self):
        """Test stop(layer_id) stops only that layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.create_audio_layer("layer2")

        player.play()
        player.stop("layer1")

        assert player._audio_layers["layer1"].status() == STATUS.STOPPED
        assert player._audio_layers["layer2"].status() == STATUS.PLAYING

        # Cleanup
        player.stop()

    def test_stop_changes_player_status(self):
        """Test stop() changes player status to STOPPED."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")
        player.play()
        player.stop()
        assert player.status() == STATUS.STOPPED


class TestBaseSoundPlayerGetItem:
    """Tests for __getitem__ method."""

    def test_getitem_returns_layer(self):
        """Test that player[layer_id] returns the audio layer."""
        player = LinuxSoundPlayer()
        player.create_audio_layer("layer1")

        layer = player["layer1"]
        assert layer is player._audio_layers["layer1"]

    def test_getitem_nonexistent_layer(self):
        """Test that player[nonexistent] raises KeyError."""
        player = LinuxSoundPlayer()

        with pytest.raises(KeyError):
            _ = player["nonexistent"]
