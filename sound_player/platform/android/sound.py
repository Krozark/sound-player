"""Android PCM audio implementation using MediaExtractor and MediaCodec (sync mode).

This module provides the AndroidPCMSound class which implements PCM-based
audio decoding on Android using:
- MediaExtractor for reading audio files
- MediaCodec in synchronous mode (dequeueInputBuffer / dequeueOutputBuffer)
- A background decode thread with backpressure to bound RAM usage
- Proper format conversion (sample rate, channels)
"""

import contextlib
import logging
import threading
import time

import numpy as np

from sound_player.core.base_sound import BaseSound
from sound_player.core.mixins import STATUS

from ._android_api import (
    JavaByteBuffer,
    MediaCodec,
    MediaCodecBufferInfo,
    MediaExtractor,
)

logger = logging.getLogger(__name__)

_BUFFER_FLAG_END_OF_STREAM = 4
# Maximum seconds of decoded PCM to keep in the buffer before pausing decoding.
_MAX_BUFFER_SECONDS = 2.0

__all__ = [
    "AndroidPCMSound",
]


class AndroidPCMSound(BaseSound):
    """Android PCM sound implementation using MediaExtractor and MediaCodec (sync).

    This implementation:
    - Decodes audio files using MediaExtractor/MediaCodec in synchronous mode
    - Runs a background decode thread that fills a PCM buffer with backpressure
      (decoding pauses when the buffer exceeds _MAX_BUFFER_SECONDS of audio)
    - Provides PCM audio chunks for mixing via get_next_chunk()
    """

    def __init__(self, *args, **kwargs):
        """Initialize the AndroidPCMSound."""
        super().__init__(*args, **kwargs)

        # MediaExtractor and MediaCodec
        self._extractor = None
        self._codec = None

        # Decoded audio data buffer
        self._pcm_buffer: np.ndarray | None = None
        self._pcm_buffer_position = 0
        self._buffer_lock = threading.Lock()

        # File info
        self._file_sample_rate = 44100
        self._file_channels = 2

        # Loop tracking
        self._loop_count = 0

        # Total output frames for one full pass (set from durationUs in track format)
        self._total_output_frames: int = 0
        # Output frames consumed in the current pass
        self._frames_consumed: int = 0

        # Decoding state
        self._decode_thread = None
        self._stop_decoding = threading.Event()

        logger.debug(f"AndroidPCMSound initialized: {self._filepath}")

    def _do_play(self, *args, **kwargs):
        """Start or resume playback."""
        logger.debug("AndroidPCMSound._do_play()")
        if self._extractor is None:
            self._start_decoding()

    def _do_pause(self, *args, **kwargs):
        """Pause playback."""
        logger.debug("AndroidPCMSound._do_pause()")
        # Decoding continues in background; data simply won't be consumed.

    def _do_stop(self, *args, **kwargs):
        """Stop playback and reset state."""
        logger.debug("AndroidPCMSound._do_stop()")
        self._stop_decoding.set()
        self._release_decoder()
        with self._buffer_lock:
            self._pcm_buffer = None
            self._pcm_buffer_position = 0
        self._stop_decoding.clear()
        self._loop_count = 0
        self._frames_consumed = 0

    def _start_decoding(self, seek_to: float = 0.0):
        """Initialize extractor + codec and start the decode thread.

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
                    if fmt.containsKey("durationUs"):
                        duration_us = fmt.getLong("durationUs")
                        self._total_output_frames = int(duration_us * self.config.sample_rate / 1_000_000)
                    break

            if audio_track_index < 0:
                raise ValueError("No audio track found in file")

            self._extractor.selectTrack(audio_track_index)

            if seek_to > 0.0:
                self._extractor.seekTo(int(seek_to * 1_000_000), MediaExtractor.SEEK_TO_PREVIOUS_SYNC)

            input_format = self._extractor.getTrackFormat(audio_track_index)
            mime = input_format.getString("mime")

            self._codec = MediaCodec.createDecoderByType(mime)

            # Configure with the input (compressed) format from the extractor.
            # The codec determines its own output format after decoding.
            self._codec.configure(input_format, None, None, 0)
            self._codec.start()

            self._frames_consumed = 0

            self._decode_thread = threading.Thread(
                target=self._decode_thread_task,
                daemon=True,
                name=f"Decode-{self._filepath}",
            )
            self._decode_thread.start()

            logger.debug(
                f"Sync decoder started: file={self._file_sample_rate}Hz/{self._file_channels}ch, "
                f"output={self.config.sample_rate}Hz/{self.config.channels}ch"
            )

        except Exception as e:
            logger.error(f"Failed to start sync decoder: {e}")
            self._release_decoder()
            raise

    def _decode_thread_task(self):
        """Background thread: feeds compressed data into the codec and collects PCM output.

        Uses the standard MediaCodec synchronous decoding pattern:
        1. Feed input until EOS is signaled
        2. Always collect output (even when no input buffer is available)
        3. Drain remaining output after input EOS until output EOS is received
        """
        logger.debug("Decode thread started")

        config = self.config
        max_buffered_samples = int(_MAX_BUFFER_SECONDS * config.sample_rate * config.channels)

        try:
            input_eos = False
            output_eos = False

            while not self._stop_decoding.is_set() and not output_eos:
                # Backpressure: pause when the PCM buffer is large enough.
                with self._buffer_lock:
                    buffered = len(self._pcm_buffer) - self._pcm_buffer_position if self._pcm_buffer is not None else 0
                if buffered > max_buffered_samples:
                    time.sleep(0.05)
                    continue

                # Grab local references; _do_stop() may set these to None.
                codec = self._codec
                extractor = self._extractor
                if codec is None or extractor is None:
                    break

                try:
                    # --- Feed input (skip if we already sent EOS) ---
                    if not input_eos:
                        input_buffer_id = codec.dequeueInputBuffer(10_000)  # 10 ms
                        if input_buffer_id >= 0:
                            input_buffer = codec.getInputBuffer(input_buffer_id)
                            input_buffer.clear()
                            size = extractor.readSampleData(input_buffer, 0)

                            if size < 0:
                                codec.queueInputBuffer(input_buffer_id, 0, 0, 0, _BUFFER_FLAG_END_OF_STREAM)
                                input_eos = True
                                logger.debug("Input EOS signaled")
                            else:
                                codec.queueInputBuffer(input_buffer_id, 0, size, 0, 0)
                                extractor.advance()

                    # --- Collect output (always, to avoid deadlock) ---
                    if self._stop_decoding.is_set():
                        break

                    buffer_info = MediaCodecBufferInfo()
                    output_buffer_id = codec.dequeueOutputBuffer(buffer_info, 10_000)

                    if output_buffer_id >= 0:
                        self._on_decoded_data(codec, output_buffer_id, buffer_info)
                        if buffer_info.flags & _BUFFER_FLAG_END_OF_STREAM:
                            output_eos = True
                            logger.debug("Output EOS received")
                    elif output_buffer_id == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED:
                        logger.debug(f"Output format changed: {codec.getOutputFormat()}")
                    # INFO_TRY_AGAIN_LATER: just loop

                except Exception as e:
                    if self._stop_decoding.is_set():
                        logger.debug("Decode thread: codec released during stop")
                    else:
                        logger.error(f"Decode thread codec error: {e}")
                    break

        except Exception as e:
            logger.error(f"Decode thread error: {e}")
        finally:
            logger.debug("Decode thread ended")

    def _on_decoded_data(self, codec, buffer_id, buffer_info):
        """Append a decoded PCM buffer to the internal numpy buffer.

        Args:
            codec: MediaCodec instance (local reference to avoid race with _do_stop).
            buffer_id: Output buffer index from MediaCodec.
            buffer_info: BufferInfo containing the valid byte count.
        """
        try:
            output_buffer = codec.getOutputBuffer(buffer_id)
            size = buffer_info.size

            if size > 0:
                # MediaCodec returns direct ByteBuffers; .array() is unsupported.
                # Copy into a heap-backed buffer to access the backing array.
                output_buffer.position(buffer_info.offset)
                output_buffer.limit(buffer_info.offset + size)
                heap_buf = JavaByteBuffer.allocate(size)
                heap_buf.put(output_buffer)
                heap_buf.flip()
                data = heap_buf.array()
                config = self.config
                chunk = np.frombuffer(bytes(data), dtype=config.dtype)

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
        except Exception as e:
            logger.error(f"Error handling decoded data: {e}")
        finally:
            with contextlib.suppress(Exception):
                codec.releaseOutputBuffer(buffer_id, False)

    def _resample(self, data: np.ndarray) -> np.ndarray:
        """Resample audio data to the target sample rate (linear interpolation)."""
        config = self.config
        ratio = self._file_sample_rate / config.sample_rate
        output_length = int(len(data) / ratio)
        indices = np.linspace(0, len(data) - 1, output_length)
        return np.interp(indices, np.arange(len(data)), data).astype(config.dtype)

    def _release_decoder(self):
        """Stop and release all decoder resources."""
        if self._decode_thread and self._decode_thread.is_alive():
            self._decode_thread.join(timeout=1.0)
        self._decode_thread = None

        if self._codec:
            with contextlib.suppress(Exception):
                self._codec.stop()
                self._codec.release()
            self._codec = None

        if self._extractor:
            with contextlib.suppress(Exception):
                self._extractor.release()
            self._extractor = None

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
                samples = self._pcm_buffer[self._pcm_buffer_position : end_pos]
                self._pcm_buffer_position += samples_to_return

                if self._pcm_buffer_position >= len(self._pcm_buffer):
                    self._pcm_buffer = None
                    self._pcm_buffer_position = 0

                frames = len(samples) // config.channels
                samples = samples[: frames * config.channels].reshape((frames, config.channels))
                self._frames_consumed += frames
                if frames < size:
                    padding = np.zeros((size - frames, config.channels), dtype=config.dtype)
                    samples = np.concatenate((samples, padding))
                return samples[:size]

        # available == 0: handle loop / stop outside the lock so _start_decoding is
        # not called while holding _buffer_lock (avoids deadlock with the decode thread).
        if should_loop:
            self._release_decoder()
            self._start_decoding()
            time.sleep(0.01)
            return np.zeros((size, config.channels), dtype=config.dtype)
        else:
            self._do_stop()
            self._status = STATUS.STOPPED
            return None

    def _get_remaining_samples(self) -> int | None:
        """Return remaining output samples until end of the last loop.

        Returns None for infinite loops or when duration is unknown.
        Called with the lock held.
        """
        if self._extractor is None or self._loop == -1 or self._total_output_frames == 0:
            return None

        # Check if we are on the last loop iteration
        is_last_loop = self._loop is None or self._loop_count >= self._loop - 1
        if not is_last_loop:
            return None

        remaining = self._total_output_frames - self._frames_consumed
        return max(0, remaining)

    def _check_loop(self) -> bool:
        """Increment the loop counter and return True if playback should loop."""
        self._loop_count += 1
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
