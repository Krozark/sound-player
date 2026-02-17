"""Android PCM audio implementation using MediaExtractor and MediaCodec.

This module provides the AndroidPCMSound class which implements PCM-based
audio decoding on Android using:
- MediaExtractor for reading audio files
- MediaCodec for decoding to PCM
- Proper format conversion (sample rate, channels)
"""

import logging
import threading
import time

import numpy as np

from sound_player.core.base_sound import BaseSound

logger = logging.getLogger(__name__)

try:
    from jnius import PythonJavaClass, autoclass, java_method

    ANDROID_AVAILABLE = True
except Exception:
    ANDROID_AVAILABLE = False
    logger.warning("Android APIs not available")

__all__ = [
    "AndroidPCMSound",
]


class DecodeCallback(PythonJavaClass):
    """Callback for MediaCodec async decoding."""

    __javainterfaces__ = ["android/media/MediaCodec$CallbackHandler"]
    __javacontext__ = "app"

    def __init__(self, sound, **kwargs):
        super().__init__(**kwargs)
        self.sound = sound

    @java_method("(Landroid/media/MediaCodec;IIJ)Landroid/media/MediaCodec$BufferInfo;")
    def onOutputBufferAvailable(self, codec, index, info):
        """Handle decoded output buffer."""
        self.sound._on_decoded_data(index, info)

    @java_method("(Landroid/media/MediaCodec;ILandroid/media/MediaCodec$BufferInfo;)V")
    def onInputBufferAvailable(self, codec, index, info):
        """Handle input buffer (empty, we feed via queue)."""
        pass

    @java_method("(Landroid/media/MediaCodec;)V")
    def onOutputFormatChanged(self, codec):
        """Handle output format change."""
        pass

    @java_method("(Landroid/media/MediaCodec;)V")
    def onError(self, codec, e):
        """Handle codec error."""
        logger.error(f"MediaCodec error: {e}")


class AndroidPCMSound(BaseSound):
    """Android PCM sound implementation using MediaExtractor and MediaCodec.

    This implementation:
    - Decodes audio files using MediaExtractor/MediaCodec
    - Provides PCM audio chunks for mixing via get_next_chunk()
    - Supports real-time mixing through the AudioMixer
    """

    def __init__(self, *args, **kwargs):
        """Initialize the AndroidPCMSound."""
        super().__init__(*args, **kwargs)

        if not ANDROID_AVAILABLE:
            raise RuntimeError("Android APIs not available")

        # MediaExtractor and MediaCodec
        self._extractor = None
        self._codec = None
        self._callback_handler = None

        # Decoded audio data buffer
        self._pcm_buffer: np.ndarray | None = None
        self._pcm_buffer_position = 0
        self._buffer_lock = threading.Lock()

        # File info
        self._file_sample_rate = 44100
        self._file_channels = 2

        # Decoding state
        self._decoding = False
        self._decode_thread = None
        self._stop_decoding = threading.Event()

        logger.debug(f"AndroidPCMSound initialized: {self._filepath}")

    def _do_play(self):
        """Start or resume playback."""
        logger.debug("AndroidPCMSound._do_play()")

        if self._extractor is None:
            self._start_decoding()

    def _do_pause(self):
        """Pause playback."""
        logger.debug("AndroidPCMSound._do_pause()")
        # Decoding continues but data won't be consumed

    def _do_stop(self):
        """Stop playback and reset state."""
        logger.debug("AndroidPCMSound._do_stop()")
        self._stop_decoding.set()
        self._release_decoder()

        with self._buffer_lock:
            self._pcm_buffer = None
            self._pcm_buffer_position = 0

        self._stop_decoding.clear()

    def _start_decoding(self):
        """Initialize and start the decoder."""
        try:
            MediaExtractor = autoclass("android.media.MediaExtractor")
            MediaFormat = autoclass("android.media.MediaFormat")
            MediaCodec = autoclass("android.media.MediaCodec")

            # Create extractor
            self._extractor = MediaExtractor()
            self._extractor.setDataSource(self._filepath)

            # Find audio track
            num_tracks = self._extractor.getTrackCount()
            audio_track_index = -1

            for i in range(num_tracks):
                format = self._extractor.getTrackFormat(i)
                mime = format.getString("mime")
                if mime and mime.startswith("audio/"):
                    audio_track_index = i
                    # Get audio format info
                    if format.containsKey("sample-rate"):
                        self._file_sample_rate = format.getInteger("sample-rate")
                    if format.containsKey("channel-count"):
                        self._file_channels = format.getInteger("channel-count")
                    break

            if audio_track_index < 0:
                raise ValueError("No audio track found in file")

            # Select audio track
            self._extractor.selectTrack(audio_track_index)

            # Get input format
            input_format = self._extractor.getTrackFormat(audio_track_index)
            mime = input_format.getString("mime")

            # Create decoder for PCM output
            self._codec = MediaCodec.createDecoderByType(mime)

            # Configure codec for PCM output
            output_format = MediaFormat.createAudioFormat("audio/raw", self._config.sample_rate, self._config.channels)
            output_format.setInteger("pcm-encoding", android.media.AudioFormat.ENCODING_PCM_16BIT)

            self._codec.configure(output_format, None, None, 0)
            self._codec.start()

            # Start decode thread
            self._decoding = True
            self._decode_thread = threading.Thread(
                target=self._decode_thread_task, daemon=True, name=f"Decode-{self._filepath}"
            )
            self._decode_thread.start()

            logger.debug(
                f"Decoder started: file={self._file_sample_rate}Hz/{self._file_channels}ch, "
                f"output={self._config.sample_rate}Hz/{self._config.channels}ch"
            )

        except Exception as e:
            logger.error(f"Failed to start decoder: {e}")
            self._release_decoder()
            raise

    def _decode_thread_task(self):
        """Background thread that decodes audio data."""
        logger.debug("Decode thread started")

        MediaCodec = autoclass("android.media.MediaCodec")
        BUFFER_FLAG_CODEC_CONFIG = 2
        BUFFER_FLAG_END_OF_STREAM = 4

        try:
            input_buffer_id = -1
            eof = False

            while not self._stop_decoding.is_set() and not eof:
                # Try to get input buffer
                try:
                    input_buffer_id = self._codec.dequeueInputBuffer(10000)  # 10ms timeout
                except:
                    continue

                if input_buffer_id < 0:
                    if input_buffer_id == MediaCodec.INFO_TRY_AGAIN_LATER:
                        time.sleep(0.001)
                        continue
                    elif input_buffer_id == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED:
                        continue
                    else:
                        logger.warning(f"Unexpected input buffer id: {input_buffer_id}")
                        continue

                # Read sample data from extractor
                sample_data = self._extractor.readSampleData(input_buffer_id)
                size = self._extractor.getSampleSize()

                flags = 0
                if size < 0:
                    # End of stream
                    flags |= BUFFER_FLAG_END_OF_STREAM
                    eof = True
                    size = 0

                # Queue to codec
                if size > 0 or eof:
                    self._codec.queueInputBuffer(input_buffer_id, 0, size, 0, flags)

                    # Advance extractor
                    if not eof:
                        self._extractor.advance()

                # Get decoded output
                buffer_info = autoclass("android.media.MediaCodec$BufferInfo")()
                output_buffer_id = self._codec.dequeueOutputBuffer(buffer_info, 10000)

                if output_buffer_id >= 0:
                    self._on_decoded_data(output_buffer_id, buffer_info)
                elif output_buffer_id == MediaCodec.INFO_TRY_AGAIN_LATER:
                    pass
                elif output_buffer_id == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED:
                    output_format = self._codec.getOutputFormat()
                    logger.debug(f"Output format changed: {output_format}")

        except Exception as e:
            logger.error(f"Decode thread error: {e}")
        finally:
            logger.debug("Decode thread ended")

    def _on_decoded_data(self, buffer_id, buffer_info):
        """Handle decoded PCM data from MediaCodec.

        Args:
            buffer_id: Output buffer index
            buffer_info: BufferInfo containing size and presentation time
        """
        try:
            output_buffer = self._codec.getOutputBuffer(buffer_id)
            data = output_buffer.array()
            size = buffer_info.size

            if size > 0:
                # Convert to numpy array (int16 PCM)
                chunk = np.frombuffer(data[:size], dtype=np.int16)

                # Handle channels (MediaCodec gives interleaved PCM)
                if self._file_channels == 1 and self._config.channels == 2:
                    # Mono to stereo
                    chunk = np.column_stack((chunk, chunk)).flatten()
                elif self._file_channels == 2 and self._config.channels == 1:
                    # Stereo to mono
                    chunk = chunk.reshape(-1, 2).mean(axis=1).astype(np.int16)

                # Resample if needed
                if self._file_sample_rate != self._config.sample_rate:
                    chunk = self._resample(chunk)

                # Convert to config dtype
                if self._config.dtype == np.int16:
                    pass  # Already int16
                elif self._config.dtype == np.int32:
                    chunk = (chunk.astype(np.int32) * 65536).astype(np.int32)

                # Add to PCM buffer
                with self._buffer_lock:
                    if self._pcm_buffer is None:
                        self._pcm_buffer = chunk
                    else:
                        self._pcm_buffer = np.concatenate((self._pcm_buffer, chunk))

            self._codec.releaseOutputBuffer(buffer_id, False)

        except Exception as e:
            logger.error(f"Error handling decoded data: {e}")

    def _resample(self, data: np.ndarray) -> np.ndarray:
        """Resample audio data to target sample rate.

        Uses simple linear interpolation for resampling.
        """
        if self._file_sample_rate == self._config.sample_rate:
            return data

        ratio = self._file_sample_rate / self._config.sample_rate
        output_length = int(len(data) / ratio)

        # Use numpy's linear interpolation
        indices = np.linspace(0, len(data) - 1, output_length)
        return np.interp(indices, np.arange(len(data)), data).astype(np.int16)

    def _release_decoder(self):
        """Release decoder resources."""
        if self._codec:
            try:
                self._codec.stop()
                self._codec.release()
            except:
                pass
            self._codec = None

        if self._extractor:
            try:
                self._extractor.release()
            except:
                pass
            self._extractor = None

        self._decoding = False

    def _do_get_next_chunk(self, size: int) -> np.ndarray | None:
        """Get the next chunk of audio data.

        Args:
            size: Number of samples to return

        Returns:
            Audio data as numpy array with shape (size, channels)
            Returns None if sound has ended and no more loops
        """
        with self._buffer_lock:
            if self._pcm_buffer is None:
                return None

            # Get available samples
            available = len(self._pcm_buffer) - self._pcm_buffer_position
            samples_needed = size * self._config.channels

            if available == 0:
                # Check if we should loop
                if self._check_loop():
                    # Restart decoder
                    self._release_decoder()
                    self._start_decoding()
                    # Wait a bit for data
                    time.sleep(0.01)
                    return np.zeros((size, self._config.channels), dtype=self._config.dtype)
                else:
                    self.stop()
                    return None

            # Determine how many samples we can return
            samples_to_return = min(samples_needed, available)

            # Extract samples
            end_pos = self._pcm_buffer_position + samples_to_return
            samples = self._pcm_buffer[self._pcm_buffer_position : end_pos]

            # Update position
            self._pcm_buffer_position += samples_to_return

            # Check if buffer is exhausted
            if self._pcm_buffer_position >= len(self._pcm_buffer):
                self._pcm_buffer = None
                self._pcm_buffer_position = 0

            # Reshape to (frames, channels)
            frames = len(samples) // self._config.channels
            samples = samples[: frames * self._config.channels]
            samples = samples.reshape((frames, self._config.channels))

            # Pad with zeros if needed
            if frames < size:
                padding = np.zeros((size - frames, self._config.channels), dtype=self._config.dtype)
                samples = np.concatenate((samples, padding))

            return samples[:size]

    def _check_loop(self) -> bool:
        """Check if we should loop and update loop counter.

        Returns:
            True if looping should continue, False otherwise
        """
        # Check with base class loop counter
        if hasattr(self, "_loop_count"):
            self._loop_count += 1
        else:
            self._loop_count = 1

        if self._loop == -1:
            # Infinite loop
            return True
        # Return True if we should continue looping
        return self._loop is not None and self._loop_count < self._loop

    def _do_seek(self, position: float) -> None:
        """Seek to position in seconds.

        Args:
            position: Position in seconds
        """
        # Restart decoder and seek to position
        self._release_decoder()

        try:
            MediaExtractor = autoclass("android.media.MediaExtractor")
            self._extractor = MediaExtractor()
            self._extractor.setDataSource(self._filepath)

            # Seek to approximate position
            self._extractor.seekTo(int(position * 1_000_000), MediaExtractor.SEEK_TO_PREVIOUS_SYNC)
            self._extractor.advance()

            # Restart decoding
            self._start_decoding()
            time.sleep(0.01)  # Let decoder buffer some data

        except Exception as e:
            logger.error(f"Seek failed: {e}")

    def __del__(self):
        """Cleanup on deletion."""
        self._do_stop()


# Import android.media for constants
try:
    android = autoclass("android.media.AudioFormat")
except:
    android = None
