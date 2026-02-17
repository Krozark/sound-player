"""Android PCM audio implementation using MediaExtractor and MediaCodec (async mode).

This module provides the AndroidPCMSoundAsync class which implements PCM-based
audio decoding on Android using:
- MediaExtractor for reading audio files
- MediaCodec in async (callback) mode — Android calls Python when buffers are ready
- No decode thread: MediaCodec drives decoding from its own internal thread
- Backpressure enforced in onInputBufferAvailable to bound RAM usage
- Proper format conversion (sample rate, channels)

Differences from AndroidPCMSound (sync):
- Event-driven instead of polling: lower CPU overhead, no 10 ms poll latency
- No decode thread owned by this class; MediaCodec manages its own thread
- Slightly more complex wiring (setCallback must be called before configure)
"""

import logging
import threading
import time

import numpy as np

from sound_player.core.base_sound import BaseSound
from sound_player.core.mixins import STATUS

from ._android_api import (
    ENCODING_BY_DTYPE,
    ENCODING_PCM_16BIT,
    MediaCodec,
    MediaExtractor,
    MediaFormat,
    PythonJavaClass,
    java_method,
)

logger = logging.getLogger(__name__)

_BUFFER_FLAG_END_OF_STREAM = 4
# Maximum seconds of decoded PCM to keep in the buffer before pausing decoding.
_MAX_BUFFER_SECONDS = 2.0

__all__ = [
    "AndroidPCMSoundAsync",
]


class _DecodeCallback(PythonJavaClass):
    """Bridges MediaCodec's async Java callbacks to Python.

    Android calls these methods from MediaCodec's internal thread whenever
    a buffer becomes available.  The class feeds compressed input from the
    MediaExtractor and appends decoded PCM output to the sound's buffer.

    Correct Java interface: android.media.MediaCodec.Callback  (inner class, so '$' notation).
    """

    __javainterfaces__ = ["android/media/MediaCodec$Callback"]
    __javacontext__ = "app"

    def __init__(self, sound: "AndroidPCMSoundAsync", extractor, **kwargs):
        super().__init__(**kwargs)
        self._sound = sound
        self._extractor = extractor
        self._extractor_lock = threading.Lock()
        self._eof = False
        config = sound.config
        self._max_buffered_samples = int(_MAX_BUFFER_SECONDS * config.sample_rate * config.channels)

    # ------------------------------------------------------------------
    # MediaCodec.Callback methods — JNI signatures must match exactly.
    # ------------------------------------------------------------------

    @java_method("(Landroid/media/MediaCodec;I)V")
    def onInputBufferAvailable(self, codec, index):
        """Feed the next compressed chunk into a free codec input buffer.

        JNI signature: void onInputBufferAvailable(MediaCodec codec, int index)
        """
        if self._eof or self._sound._stop_decoding.is_set():
            return

        # Backpressure: block this callback until the PCM buffer drains enough.
        # Blocking here pauses input → pauses output naturally.
        while not self._sound._stop_decoding.is_set():
            with self._sound._buffer_lock:
                buffered = (
                    len(self._sound._pcm_buffer) - self._sound._pcm_buffer_position
                    if self._sound._pcm_buffer is not None
                    else 0
                )
            if buffered <= self._max_buffered_samples:
                break
            time.sleep(0.05)

        if self._sound._stop_decoding.is_set():
            return

        with self._extractor_lock:
            input_buffer = codec.getInputBuffer(index)
            input_buffer.clear()
            size = self._extractor.readSampleData(input_buffer, 0)
            if size < 0:
                codec.queueInputBuffer(index, 0, 0, 0, _BUFFER_FLAG_END_OF_STREAM)
                self._eof = True
            else:
                pts = self._extractor.getSampleTime()
                codec.queueInputBuffer(index, 0, size, pts, 0)
                self._extractor.advance()

    @java_method("(Landroid/media/MediaCodec;ILandroid/media/MediaCodec$BufferInfo;)V")
    def onOutputBufferAvailable(self, codec, index, info):
        """Handle a buffer of decoded PCM data.

        JNI signature: void onOutputBufferAvailable(MediaCodec codec, int index, MediaCodec.BufferInfo info)
        """
        self._sound._on_decoded_data(codec, index, info)

    @java_method("(Landroid/media/MediaCodec;Landroid/media/MediaFormat;)V")
    def onOutputFormatChanged(self, codec, format):
        """Called when the output format changes (e.g. after the first decoded frame).

        JNI signature: void onOutputFormatChanged(MediaCodec codec, MediaFormat format)
        """
        logger.debug(f"MediaCodec output format changed: {format}")

    @java_method("(Landroid/media/MediaCodec;Landroid/media/MediaCodec$CodecException;)V")
    def onError(self, codec, e):
        """Handle a codec error.

        JNI signature: void onError(MediaCodec codec, MediaCodec.CodecException e)
        """
        logger.error(f"MediaCodec async error: {e}")


class AndroidPCMSoundAsync(BaseSound):
    """Android PCM sound using MediaExtractor + MediaCodec in async (callback) mode.

    This implementation:
    - Registers a _DecodeCallback with MediaCodec before configure/start
    - Android calls back into Python whenever an input or output buffer is ready
    - No polling thread is created by this class; decoding is fully event-driven
    - Backpressure is enforced in onInputBufferAvailable
    - Provides PCM audio chunks for mixing via get_next_chunk()
    """

    def __init__(self, *args, **kwargs):
        """Initialize the AndroidPCMSoundAsync."""
        super().__init__(*args, **kwargs)

        self._extractor = None
        self._codec = None
        self._callback: _DecodeCallback | None = None

        # Decoded audio data buffer
        self._pcm_buffer: np.ndarray | None = None
        self._pcm_buffer_position = 0
        self._buffer_lock = threading.Lock()

        # File info
        self._file_sample_rate = 44100
        self._file_channels = 2

        self._stop_decoding = threading.Event()

        logger.debug(f"AndroidPCMSoundAsync initialized: {self._filepath}")

    def _do_play(self):
        """Start or resume playback."""
        logger.debug("AndroidPCMSoundAsync._do_play()")
        if self._extractor is None:
            self._start_decoding()

    def _do_pause(self):
        """Pause playback."""
        logger.debug("AndroidPCMSoundAsync._do_pause()")
        # Decoding continues; data simply won't be consumed.

    def _do_stop(self):
        """Stop playback and reset state."""
        logger.debug("AndroidPCMSoundAsync._do_stop()")
        self._stop_decoding.set()
        self._release_decoder()
        with self._buffer_lock:
            self._pcm_buffer = None
            self._pcm_buffer_position = 0
        self._stop_decoding.clear()

    def _start_decoding(self, seek_to: float = 0.0):
        """Initialize extractor + codec in async callback mode.

        Args:
            seek_to: Optional position in seconds to seek to before decoding.
        """
        try:
            self._extractor = MediaExtractor()
            self._extractor.setDataSource(self._filepath)

            # Find the first audio track.
            audio_track_index = -1
            for i in range(self._extractor.getTrackCount()):
                fmt = self._extractor.getTrackFormat(i)
                mime = fmt.getString("mime")
                if mime and mime.startswith("audio/"):
                    audio_track_index = i
                    if fmt.containsKey("sample-rate"):
                        self._file_sample_rate = fmt.getInteger("sample-rate")
                    if fmt.containsKey("channel-count"):
                        self._file_channels = fmt.getInteger("channel-count")
                    break

            if audio_track_index < 0:
                raise ValueError("No audio track found in file")

            self._extractor.selectTrack(audio_track_index)

            if seek_to > 0.0:
                self._extractor.seekTo(int(seek_to * 1_000_000), MediaExtractor.SEEK_TO_PREVIOUS_SYNC)

            input_format = self._extractor.getTrackFormat(audio_track_index)
            mime = input_format.getString("mime")

            self._codec = MediaCodec.createDecoderByType(mime)

            # Register callback BEFORE configure — Android requirement for async mode.
            self._callback = _DecodeCallback(self, self._extractor)
            self._codec.setCallback(self._callback)

            config = self.config
            output_format = MediaFormat.createAudioFormat("audio/raw", config.sample_rate, config.channels)
            encoding = ENCODING_BY_DTYPE.get(config.dtype, ENCODING_PCM_16BIT)
            output_format.setInteger("pcm-encoding", encoding)
            self._codec.configure(output_format, None, None, 0)
            self._codec.start()

            logger.debug(
                f"Async decoder started: file={self._file_sample_rate}Hz/{self._file_channels}ch, "
                f"output={config.sample_rate}Hz/{config.channels}ch"
            )

        except Exception as e:
            logger.error(f"Failed to start async decoder: {e}")
            self._release_decoder()
            raise

    def _on_decoded_data(self, codec, buffer_id, buffer_info):
        """Append a decoded PCM buffer to the internal numpy buffer.

        Called from _DecodeCallback.onOutputBufferAvailable on MediaCodec's thread.

        Args:
            codec: The MediaCodec instance (needed to release the buffer).
            buffer_id: Output buffer index.
            buffer_info: BufferInfo containing the valid byte count.
        """
        try:
            output_buffer = codec.getOutputBuffer(buffer_id)
            data = output_buffer.array()
            size = buffer_info.size

            if size > 0:
                config = self.config
                chunk = np.frombuffer(data[:size], dtype=config.dtype)

                if self._file_channels == 1 and config.channels == 2:
                    chunk = np.column_stack((chunk, chunk)).flatten()
                elif self._file_channels == 2 and config.channels == 1:
                    chunk = chunk.reshape(-1, 2).mean(axis=1).astype(config.dtype)

                if self._file_sample_rate != config.sample_rate:
                    chunk = self._resample(chunk)

                with self._buffer_lock:
                    if self._pcm_buffer is None:
                        self._pcm_buffer = chunk
                    else:
                        self._pcm_buffer = np.concatenate((self._pcm_buffer, chunk))

            codec.releaseOutputBuffer(buffer_id, False)

        except Exception as e:
            logger.error(f"Error handling decoded data: {e}")

    def _resample(self, data: np.ndarray) -> np.ndarray:
        """Resample audio data to the target sample rate (linear interpolation)."""
        config = self.config
        ratio = self._file_sample_rate / config.sample_rate
        output_length = int(len(data) / ratio)
        indices = np.linspace(0, len(data) - 1, output_length)
        return np.interp(indices, np.arange(len(data)), data).astype(config.dtype)

    def _release_decoder(self):
        """Stop and release all decoder resources."""
        import contextlib

        if self._codec:
            with contextlib.suppress(Exception):
                self._codec.stop()
                self._codec.release()
            self._codec = None

        if self._extractor:
            with contextlib.suppress(Exception):
                self._extractor.release()
            self._extractor = None

        self._callback = None

    def _do_get_next_chunk(self, size: int) -> np.ndarray | None:
        """Return the next chunk of decoded PCM data.

        Args:
            size: Number of frames to return.

        Returns:
            Numpy array of shape (size, channels), or None when playback ends.
        """
        config = self.config

        with self._buffer_lock:
            if self._pcm_buffer is None:
                return None

            available = len(self._pcm_buffer) - self._pcm_buffer_position
            if available == 0:
                should_loop = self._check_loop()
                # Clear buffer state before leaving the lock.
                self._pcm_buffer = None
                self._pcm_buffer_position = 0
            else:
                samples_needed = size * config.channels
                samples_to_return = min(samples_needed, available)
                end_pos = self._pcm_buffer_position + samples_to_return
                samples = self._pcm_buffer[self._pcm_buffer_position:end_pos]
                self._pcm_buffer_position += samples_to_return

                if self._pcm_buffer_position >= len(self._pcm_buffer):
                    self._pcm_buffer = None
                    self._pcm_buffer_position = 0

                frames = len(samples) // config.channels
                samples = samples[: frames * config.channels].reshape((frames, config.channels))
                if frames < size:
                    padding = np.zeros((size - frames, config.channels), dtype=config.dtype)
                    samples = np.concatenate((samples, padding))
                return samples[:size]

        # available == 0: handle loop / stop outside the lock so _start_decoding is
        # not called while holding _buffer_lock (avoids deadlock with the callback thread).
        if should_loop:
            self._release_decoder()
            self._start_decoding()
            time.sleep(0.01)
            return np.zeros((size, config.channels), dtype=config.dtype)
        else:
            self._do_stop()
            self._status = STATUS.STOPPED
            return None

    def _check_loop(self) -> bool:
        """Increment the loop counter and return True if playback should loop."""
        if hasattr(self, "_loop_count"):
            self._loop_count += 1
        else:
            self._loop_count = 1
        if self._loop == -1:
            return True
        return self._loop is not None and self._loop_count < self._loop

    def _do_seek(self, position: float) -> None:
        """Seek to a position in seconds.

        Args:
            position: Target position in seconds.
        """
        self._stop_decoding.set()
        self._release_decoder()
        with self._buffer_lock:
            self._pcm_buffer = None
            self._pcm_buffer_position = 0
        self._stop_decoding.clear()
        try:
            self._start_decoding(seek_to=position)
            time.sleep(0.01)
        except Exception as e:
            logger.error(f"Seek failed: {e}")

    def __del__(self):
        """Cleanup on deletion."""
        self._do_stop()
