"""Android audio output implementation using AudioTrack.

This module provides the AndroidSoundPlayer class which implements audio
output on Android using the AudioTrack API.
"""

import logging
import threading
import time

import numpy as np

from sound_player.core import STATUS, AudioConfig
from sound_player.core.base_player import BaseSoundPlayer

logger = logging.getLogger(__name__)

try:
    from jnius import autoclass

    ANDROID_AVAILABLE = True
except Exception:
    ANDROID_AVAILABLE = False
    logger.warning("Android APIs not available")

__all__ = [
    "AndroidSoundPlayer",
]


class AndroidSoundPlayer(BaseSoundPlayer):
    """Android audio output using AudioTrack.

    This implementation:
    - Uses AudioTrack in MODE_STREAM for real-time PCM output
    - Runs a background thread to continuously write audio data
    - Supports play/pause/stop control
    """

    # Android AudioFormat constants
    ENCODING_PCM_16BIT = 2
    ENCODING_PCM_8BIT = 3
    CHANNEL_OUT_MONO = 4
    CHANNEL_OUT_STEREO = 12
    MODE_STREAM = 1

    # Android AudioAttributes constants
    USAGE_MEDIA = 1

    def __init__(self, config: AudioConfig | None = None):
        """Initialize the AndroidSoundPlayer.

        Args:
            config: AudioConfig for audio output format

        Raises:
            RuntimeError: If Android APIs are not available
        """
        if not ANDROID_AVAILABLE:
            raise RuntimeError("Android APIs not available")

        super().__init__(config or AudioConfig())
        self._audiotrack = None
        self._output_thread = None
        self._stop_output_thread = threading.Event()
        self._lock = threading.RLock()

    def _create_output_stream(self):
        """Create the AudioTrack for PCM output.

        Creates an AudioTrack instance in stream mode with the configured
        audio format.
        """
        if self._audiotrack is not None:
            return

        try:
            AudioTrack = autoclass("android.media.AudioTrack")
            AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")
            AudioFormatBuilder = autoclass("android.media.AudioFormat$Builder")

            logger.debug(f"Creating AudioTrack: {self._config.sample_rate}Hz, {self._config.channels}ch, 16bit")

            # Create audio attributes
            attrs = AudioAttributesBuilder().setUsage(self.USAGE_MEDIA).build()

            # Determine channel mask
            channel_mask = self.CHANNEL_OUT_STEREO if self._config.channels == 2 else self.CHANNEL_OUT_MONO

            # Create audio format
            fmt = (
                AudioFormatBuilder()
                .setEncoding(self.ENCODING_PCM_16BIT)
                .setSampleRate(self._config.sample_rate)
                .setChannelMask(channel_mask)
                .build()
            )

            # Calculate buffer size in bytes
            buffer_size = self._config.buffer_size * self._config.channels * 2  # 2 bytes per sample (16-bit)

            # Create AudioTrack in stream mode
            self._audiotrack = AudioTrack(
                attrs,
                fmt,
                buffer_size,
                self.MODE_STREAM,
                0,  # sessionId
            )

            logger.debug("AudioTrack created successfully")

        except Exception as e:
            logger.error(f"Failed to create AudioTrack: {e}")
            raise

    def _output_thread_task(self):
        """Background thread task that continuously writes audio data.

        This thread runs continuously while playing, pulling audio data
        from get_next_chunk() and writing it to the AudioTrack.
        """
        logger.debug("Output thread started")

        while not self._stop_output_thread.is_set():
            if self._status == STATUS.PLAYING and self._audiotrack:
                chunk = self.get_next_chunk()
                if chunk is not None:
                    self._write_audio(chunk)
                else:
                    # No audio data, write a small silence buffer
                    silence = np.zeros((self._config.buffer_size // 4, self._config.channels), dtype=self._config.dtype)
                    self._write_audio(silence)

                # Small sleep to prevent busy-waiting
                time.sleep(0.001)
            else:
                # Not playing, wait a bit longer
                time.sleep(0.01)

        logger.debug("Output thread stopped")

    def _write_audio(self, data: np.ndarray):
        """Write PCM data to the AudioTrack.

        Converts the numpy array to bytes and writes to the AudioTrack.

        Args:
            data: Audio data as numpy array
        """
        if self._audiotrack is None:
            return

        try:
            # Convert numpy array to bytes
            bytes_data = data.tobytes()
            self._audiotrack.write(bytes_data, 0, len(bytes_data))
        except Exception as e:
            logger.error(f"Error writing to AudioTrack: {e}")

    def _start_output_thread(self):
        """Start the background output thread."""
        if self._output_thread is None or not self._output_thread.is_alive():
            self._stop_output_thread.clear()
            self._output_thread = threading.Thread(target=self._output_thread_task, daemon=True, name="AudioOutput")
            self._output_thread.start()

    def _stop_output_thread(self):
        """Stop the background output thread."""
        self._stop_output_thread.set()
        if self._output_thread and self._output_thread.is_alive():
            self._output_thread.join(timeout=1.0)

    def _close_output_stream(self):
        """Close and release the AudioTrack.

        Stops playback and releases all AudioTrack resources.
        """
        logger.debug("Closing AudioTrack")
        with self._lock:
            if self._audiotrack:
                try:
                    if self._audiotrack.getPlayState() == 3:  # PLAYSTATE_PLAYING
                        self._audiotrack.stop()
                    self._audiotrack.release()
                except Exception as e:
                    logger.error(f"Error releasing AudioTrack: {e}")
                finally:
                    self._audiotrack = None

    def play(self, layer=None):
        """Start playback of a layer or all layers.

        Args:
            layer: Specific layer to play, or None for all layers

        For the player (layer=None), this also starts the audio output.
        """
        logger.debug("AndroidSoundPlayer.play(%s)", layer)
        with self._lock:
            if layer is not None:
                # Play specific layer only
                return self._audio_layers[layer].play()
            else:
                # Play all layers and start output
                for audio_layer in self._audio_layers.values():
                    if audio_layer.status() != STATUS.PLAYING:
                        audio_layer.play()
                super().play()

                # Create AudioTrack if needed and start playback
                if self._audiotrack is None:
                    self._create_output_stream()

                if self._audiotrack:
                    self._audiotrack.play()
                    self._start_output_thread()

    def pause(self, layer=None):
        """Pause playback of a layer or all layers.

        Args:
            layer: Specific layer to pause, or None for all layers

        For the player (layer=None), this also pauses the AudioTrack.
        """
        logger.debug("AndroidSoundPlayer.pause(%s)", layer)
        with self._lock:
            if layer is not None:
                # Pause specific layer only
                return self._audio_layers[layer].pause()
            else:
                # Pause all layers and pause AudioTrack
                for audio_layer in self._audio_layers.values():
                    if audio_layer.status() != STATUS.PAUSED:
                        audio_layer.pause()
                super().pause()

                # Pause the AudioTrack
                if self._audiotrack:
                    self._audiotrack.pause()

    def stop(self, layer=None):
        """Stop playback of a layer or all layers.

        Args:
            layer: Specific layer to stop, or None for all layers

        For the player (layer=None), this also stops the AudioTrack and
        closes the output stream.
        """
        logger.debug("AndroidSoundPlayer.stop(%s)", layer)
        with self._lock:
            if layer is not None:
                # Stop specific layer only
                return self._audio_layers[layer].stop()
            else:
                # Stop all layers and close output
                for audio_layer in self._audio_layers.values():
                    audio_layer.stop()
                super().stop()

                # Stop output thread and close AudioTrack
                self._stop_output_thread()
                self._close_output_stream()

    def __del__(self):
        """Cleanup on deletion."""
        self._stop_output_thread()
        self._close_output_stream()
