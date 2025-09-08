import logging
import os
import queue
import signal
import subprocess
import tempfile
import threading
from enum import Enum, auto

import numpy as np

from .sound import STATUS, BaseSound

logger = logging.getLogger(__name__)


class AudioEffect(Enum):
    """Available audio effect types"""

    FADE_IN = auto()
    FADE_OUT = auto()
    SET_VOLUME = auto()
    CROSSFADE = auto()
    ECHO = auto()
    REVERB = auto()


# Platform detection
try:
    from android import api_version
    from jnius import PythonJavaClass, autoclass, cast, java_method

    IS_ANDROID = True

    # Android classes for audio
    MediaPlayer = autoclass("android.media.MediaPlayer")
    AudioManager = autoclass("android.media.AudioManager")
    MediaExtractor = autoclass("android.media.MediaExtractor")
    MediaCodec = autoclass("android.media.MediaCodec")
    MediaFormat = autoclass("android.media.MediaFormat")
    AudioTrack = autoclass("android.media.AudioTrack")
    AudioFormat = autoclass("android.media.AudioFormat")
    ByteBuffer = autoclass("java.nio.ByteBuffer")

    if api_version >= 21:
        AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")

except ImportError:
    IS_ANDROID = False


class AudioProcessor:
    """
    Unified audio processor for real-time effects processing
    """

    def __init__(self):
        # Effect state
        self.current_volume = 1.0
        self.target_volume = 1.0
        self.fade_samples_remaining = 0
        self.fade_step = 0.0
        self.command_queue = queue.Queue()

    def process_samples(self, samples_bytes, sample_rate):
        """Process audio samples with effects"""
        # Convert bytes to numpy array (16-bit PCM)
        samples = np.frombuffer(samples_bytes, dtype=np.int16).astype(np.float32)
        samples = samples / 32768.0  # Normalize to [-1, 1]

        # Process pending commands
        self._process_commands()

        # Apply effects
        processed_samples = self._apply_effects(samples, sample_rate)

        # Convert back to int16
        processed_samples = np.clip(processed_samples * 32768.0, -32768, 32767)
        return processed_samples.astype(np.int16).tobytes()

    def process_samples_float32(self, samples_bytes, sample_rate):
        """Process float32 samples (for Linux FFmpeg pipeline)"""
        # Convert bytes to numpy array (32-bit float)
        samples = np.frombuffer(samples_bytes, dtype=np.float32)

        # Process pending commands
        self._process_commands()

        # Apply effects
        processed_samples = self._apply_effects(samples, sample_rate)

        # Return as float32 bytes
        return processed_samples.astype(np.float32).tobytes()

    def _process_commands(self):
        """Process pending commands"""
        while not self.command_queue.empty():
            try:
                command = self.command_queue.get_nowait()
                self._execute_command(command)
            except queue.Empty:
                break

    def _execute_command(self, command):
        """Execute a command"""
        effect_type = command.get("effect")

        if effect_type == AudioEffect.FADE_IN:
            duration = command.get("duration", 1.0)
            sample_rate = command.get("sample_rate", 44100)
            self.current_volume = 0.0
            self.target_volume = command.get("target", 1.0)
            self._start_fade(duration, sample_rate)

        elif effect_type == AudioEffect.FADE_OUT:
            duration = command.get("duration", 1.0)
            sample_rate = command.get("sample_rate", 44100)
            self.target_volume = 0.0
            self._start_fade(duration, sample_rate)

        elif effect_type == AudioEffect.SET_VOLUME:
            duration = command.get("duration", 0.1)
            sample_rate = command.get("sample_rate", 44100)
            self.target_volume = command.get("volume", 1.0)
            self._start_fade(duration, sample_rate)

    def _start_fade(self, duration, sample_rate):
        """Start a fade effect"""
        samples_needed = int(duration * sample_rate)
        self.fade_samples_remaining = samples_needed
        if samples_needed > 0:
            self.fade_step = (self.target_volume - self.current_volume) / samples_needed

    def _apply_effects(self, samples, sample_rate):
        """Apply effects to audio samples"""
        if self.fade_samples_remaining > 0:
            samples_to_process = min(len(samples), self.fade_samples_remaining)

            # Progressive fade
            for i in range(samples_to_process):
                samples[i] = samples[i] * self.current_volume
                self.current_volume += self.fade_step

            self.fade_samples_remaining -= samples_to_process

            # Constant volume on remaining samples
            if samples_to_process < len(samples):
                samples[samples_to_process:] = samples[samples_to_process:] * self.current_volume
        else:
            samples = samples * self.current_volume

        return samples

    def fade_in(self, duration=1.0, target_volume=1.0, sample_rate=44100):
        """Trigger a fade in effect"""
        self.command_queue.put(
            {"effect": AudioEffect.FADE_IN, "duration": duration, "target": target_volume, "sample_rate": sample_rate}
        )

    def fade_out(self, duration=1.0, sample_rate=44100):
        """Trigger a fade out effect"""
        self.command_queue.put({"effect": AudioEffect.FADE_OUT, "duration": duration, "sample_rate": sample_rate})

    def set_volume(self, volume, duration=0.1, sample_rate=44100):
        """Change volume with transition"""
        self.command_queue.put(
            {"effect": AudioEffect.SET_VOLUME, "volume": volume, "duration": duration, "sample_rate": sample_rate}
        )

    def apply_effect(self, effect_type: AudioEffect, **kwargs):
        """Apply an effect with custom parameters"""
        command = {"effect": effect_type, **kwargs}
        self.command_queue.put(command)


class AndroidNativeStreamingSound(BaseSound):
    """
    Android streaming audio using MediaExtractor + MediaCodec + AudioTrack
    """

    def __init__(self, filepath, **kwargs):
        super().__init__(filepath, **kwargs)
        self.processor = AudioProcessor()

        # Android components
        self.extractor = None
        self.decoder = None
        self.audio_track = None

        # Streaming state
        self.is_streaming = False
        self.streaming_thread = None
        self.sample_rate = 44100
        self.channels = 2
        self.loop_count = 0

    def _setup_extractor(self):
        """Setup MediaExtractor"""
        self.extractor = MediaExtractor()
        self.extractor.setDataSource(self._filepath)

        # Find audio track
        num_tracks = self.extractor.getTrackCount()
        audio_track_index = -1

        for i in range(num_tracks):
            format = self.extractor.getTrackFormat(i)
            mime = format.getString(MediaFormat.KEY_MIME)
            if mime.startswith("audio/"):
                audio_track_index = i
                self.sample_rate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                self.channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                break

        if audio_track_index == -1:
            raise Exception("No audio track found")

        self.extractor.selectTrack(audio_track_index)
        return self.extractor.getTrackFormat(audio_track_index)

    def _setup_decoder(self, format):
        """Setup MediaCodec for decoding"""
        mime = format.getString(MediaFormat.KEY_MIME)
        self.decoder = MediaCodec.createDecoderByType(mime)
        self.decoder.configure(format, None, None, 0)
        self.decoder.start()

    def _setup_audio_track(self):
        """Setup AudioTrack for playback"""
        channel_config = AudioFormat.CHANNEL_OUT_STEREO if self.channels == 2 else AudioFormat.CHANNEL_OUT_MONO
        audio_format = AudioFormat.ENCODING_PCM_16BIT

        buffer_size = AudioTrack.getMinBufferSize(self.sample_rate, channel_config, audio_format)

        if api_version >= 21:
            audio_attributes = AudioAttributesBuilder().setLegacyStreamType(AudioManager.STREAM_MUSIC).build()
            audio_format_obj = (
                autoclass("android.media.AudioFormat$Builder")()
                .setSampleRate(self.sample_rate)
                .setChannelMask(channel_config)
                .setEncoding(audio_format)
                .build()
            )

            self.audio_track = AudioTrack(audio_attributes, audio_format_obj, buffer_size, AudioTrack.MODE_STREAM, 0)
        else:
            self.audio_track = AudioTrack(
                AudioManager.STREAM_MUSIC,
                self.sample_rate,
                channel_config,
                audio_format,
                buffer_size,
                AudioTrack.MODE_STREAM,
            )

    def _streaming_loop(self):
        """Main streaming loop"""
        logger.debug("Starting Android native streaming")

        input_buffers = self.decoder.getInputBuffers()
        output_buffers = self.decoder.getOutputBuffers()

        info = autoclass("android.media.MediaCodec$BufferInfo")()
        end_of_stream = False

        while self.is_streaming and not end_of_stream:
            # Feed the decoder
            input_buffer_index = self.decoder.dequeueInputBuffer(10000)  # 10ms timeout
            if input_buffer_index >= 0:
                input_buffer = input_buffers[input_buffer_index]
                sample_size = self.extractor.readSampleData(input_buffer, 0)

                if sample_size < 0:
                    # End of file
                    if self._loop == -1 or self.loop_count < self._loop:
                        # Restart for loop
                        self.extractor.seekTo(0, MediaExtractor.SEEK_TO_CLOSEST_SYNC)
                        self.loop_count += 1
                        continue
                    else:
                        # Really finished
                        self.decoder.queueInputBuffer(input_buffer_index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                        end_of_stream = True
                else:
                    presentation_time = self.extractor.getSampleTime()
                    self.decoder.queueInputBuffer(input_buffer_index, 0, sample_size, presentation_time, 0)
                    self.extractor.advance()

            # Get decoded data
            output_buffer_index = self.decoder.dequeueOutputBuffer(info, 10000)
            if output_buffer_index >= 0:
                output_buffer = output_buffers[output_buffer_index]

                # Extract PCM data
                output_buffer.rewind()
                pcm_data = bytearray(info.size)
                output_buffer.get(pcm_data)

                # Process with our effects
                processed_data = self.processor.process_samples(bytes(pcm_data), self.sample_rate)

                # Write to AudioTrack
                if len(processed_data) > 0:
                    self.audio_track.write(processed_data, 0, len(processed_data))

                self.decoder.releaseOutputBuffer(output_buffer_index, False)

                if info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM:
                    end_of_stream = True
            elif output_buffer_index == MediaCodec.INFO_OUTPUT_BUFFERS_CHANGED:
                output_buffers = self.decoder.getOutputBuffers()

        logger.debug("Android streaming ended")
        # Signal that playback is complete
        super().stop()

    def fade_in(self, duration=1.0):
        """Real-time fade in"""
        target_vol = (self._volume or 100) / 100.0
        self.processor.apply_effect(
            AudioEffect.FADE_IN, duration=duration, target=target_vol, sample_rate=self.sample_rate
        )

    def fade_out(self, duration=1.0):
        """Real-time fade out"""
        self.processor.apply_effect(AudioEffect.FADE_OUT, duration=duration, sample_rate=self.sample_rate)

    def set_volume_realtime(self, volume, duration=0.1):
        """Change volume in real-time"""
        self.processor.apply_effect(
            AudioEffect.SET_VOLUME, volume=volume / 100.0, duration=duration, sample_rate=self.sample_rate
        )
        super().set_volume(volume)

    def apply_audio_effect(self, effect_type: AudioEffect, **kwargs):
        """Apply any audio effect with custom parameters"""
        # Add sample_rate if not provided
        if "sample_rate" not in kwargs:
            kwargs["sample_rate"] = self.sample_rate
        self.processor.apply_effect(effect_type, **kwargs)

    def _do_play(self):
        logger.debug("AndroidNativeStreamingSound._do_play()")
        if not self.is_streaming:
            self.is_streaming = True
            self.loop_count = 0

            try:
                # Setup decoding/playback chain
                format = self._setup_extractor()
                self._setup_decoder(format)
                self._setup_audio_track()

                # Start playback
                self.audio_track.play()

                # Launch streaming thread
                self.streaming_thread = threading.Thread(target=self._streaming_loop)
                self.streaming_thread.daemon = True
                self.streaming_thread.start()

            except Exception as e:
                logger.error(f"Failed to start Android streaming: {e}")
                self._cleanup()
                raise

    def _do_pause(self):
        logger.debug("AndroidNativeStreamingSound._do_pause()")
        if self.audio_track:
            self.audio_track.pause()

    def _do_stop(self):
        logger.debug("AndroidNativeStreamingSound._do_stop()")
        self.is_streaming = False
        self._cleanup()

    def _cleanup(self):
        """Clean up resources"""
        if self.audio_track:
            try:
                self.audio_track.stop()
                self.audio_track.release()
            except:
                pass
            self.audio_track = None

        if self.decoder:
            try:
                self.decoder.stop()
                self.decoder.release()
            except:
                pass
            self.decoder = None

        if self.extractor:
            try:
                self.extractor.release()
            except:
                pass
            self.extractor = None

    def status(self):
        """Check streaming status"""
        if self.streaming_thread and not self.streaming_thread.is_alive() and self._status != STATUS.STOPPED:
            self.stop()
        return super().status()


class LinuxStreamingSound(BaseSound):
    """
    Linux version using FFmpeg with named pipes for real-time streaming
    """

    def __init__(self, filepath, **kwargs):
        super().__init__(filepath, **kwargs)
        self.processor = AudioProcessor()
        self.player_process = None
        self.decoder_process = None
        self.is_streaming = False
        self.streaming_thread = None
        self.sample_rate = 44100
        self.channels = 2
        self.temp_fifo = None

    def _which(self, program):
        """Find executable in PATH"""
        from currentplatform import platform

        # Add .exe program extension for windows support
        if platform == "windows" and not program.endswith(".exe"):
            program += ".exe"

        envdir_list = [os.curdir] + os.environ["PATH"].split(os.pathsep)

        for envdir in envdir_list:
            program_path = os.path.join(envdir, program)
            if os.path.isfile(program_path) and os.access(program_path, os.X_OK):
                return program_path
        return None

    def _create_fifo(self):
        """Create a named pipe for streaming"""
        self.temp_fifo = tempfile.mktemp(suffix=".fifo")
        os.mkfifo(self.temp_fifo)
        return self.temp_fifo

    def _create_decoder_process(self):
        """Create FFmpeg process for decoding"""
        cmd = [
            "ffmpeg",
            "-i",
            self._filepath,
            "-f",
            "f32le",  # Float 32-bit little endian
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(self.sample_rate),
            "-ac",
            str(self.channels),
            "-",
        ]

        logger.debug(f"Decoder command: {cmd}")
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _create_player_process(self):
        """Create player process for playback"""
        fifo_path = self._create_fifo()

        # Try ffplay first, then avplay
        player = None
        if self._which("ffplay"):
            player = "ffplay"
        elif self._which("avplay"):
            player = "avplay"
        else:
            raise RuntimeError("Neither ffplay nor avplay found")

        cmd = [
            player,
            "-f",
            "f32le",
            "-ar",
            str(self.sample_rate),
            "-ac",
            str(self.channels),
            "-nodisp",
            "-autoexit",
            "-hide_banner",
            "-loglevel",
            "error",
            fifo_path,
        ]

        if self._volume is not None:
            cmd.insert(-1, "-volume")
            cmd.insert(-1, str(self._volume))

        logger.debug(f"Player command: {cmd}")
        return subprocess.Popen(cmd, stderr=subprocess.PIPE)

    def _streaming_thread(self):
        """Main streaming thread"""
        logger.debug("Starting Linux streaming thread")

        chunk_size = 4096

        # Open the FIFO for writing
        try:
            with open(self.temp_fifo, "wb") as fifo:
                while self.is_streaming:
                    # Read chunk from decoder
                    raw_data = self.decoder_process.stdout.read(chunk_size * 4)  # 4 bytes per float32
                    if not raw_data:
                        break

                    # Process with effects
                    processed_data = self.processor.process_samples_float32(raw_data, self.sample_rate)

                    # Write to FIFO
                    try:
                        fifo.write(processed_data)
                        fifo.flush()
                    except BrokenPipeError:
                        break

        except Exception as e:
            logger.error(f"Streaming thread error: {e}")
            raise

        logger.debug("Linux streaming thread ended")
        # Signal completion
        super().stop()

    def fade_in(self, duration=1.0):
        """Real-time fade in"""
        target_vol = (self._volume or 100) / 100.0
        self.processor.apply_effect(
            AudioEffect.FADE_IN, duration=duration, target=target_vol, sample_rate=self.sample_rate
        )

    def fade_out(self, duration=1.0):
        """Real-time fade out"""
        self.processor.apply_effect(AudioEffect.FADE_OUT, duration=duration, sample_rate=self.sample_rate)

    def set_volume_realtime(self, volume, duration=0.1):
        """Change volume in real-time"""
        self.processor.apply_effect(
            AudioEffect.SET_VOLUME, volume=volume / 100.0, duration=duration, sample_rate=self.sample_rate
        )
        super().set_volume(volume)

    def apply_audio_effect(self, effect_type: AudioEffect, **kwargs):
        """Apply any audio effect with custom parameters"""
        if "sample_rate" not in kwargs:
            kwargs["sample_rate"] = self.sample_rate
        self.processor.apply_effect(effect_type, **kwargs)

    def _do_play(self):
        logger.debug("LinuxStreamingSound._do_play()")
        if not self.is_streaming:
            self.is_streaming = True

            try:
                # Create processes
                self.decoder_process = self._create_decoder_process()
                self.player_process = self._create_player_process()

                # Start streaming thread
                self.streaming_thread = threading.Thread(target=self._streaming_thread)
                self.streaming_thread.daemon = True
                self.streaming_thread.start()

            except Exception as e:
                logger.error(f"Failed to start Linux streaming: {e}")
                self._cleanup()
                raise
        elif self._status == STATUS.PAUSED:
            # Resume from pause
            if self.player_process:
                self.player_process.send_signal(signal.SIGCONT)

    def _do_pause(self):
        logger.debug("LinuxStreamingSound._do_pause()")
        if self.player_process:
            self.player_process.send_signal(signal.SIGSTOP)

    def _do_stop(self):
        logger.debug("LinuxStreamingSound._do_stop()")
        self.is_streaming = False
        self._cleanup()

    def _cleanup(self):
        """Clean up resources"""
        if self.player_process:
            try:
                self.player_process.terminate()
                self.player_process.wait(timeout=1)
            except:
                try:
                    self.player_process.kill()
                except:
                    pass
            self.player_process = None

        if self.decoder_process:
            try:
                self.decoder_process.terminate()
                self.decoder_process.wait(timeout=1)
            except:
                try:
                    self.decoder_process.kill()
                except:
                    pass
            self.decoder_process = None

        if self.temp_fifo and os.path.exists(self.temp_fifo):
            try:
                os.unlink(self.temp_fifo)
            except:
                pass
            self.temp_fifo = None

    def status(self):
        """Check status of processes"""
        if self.decoder_process and self.decoder_process.poll() is not None:
            if self._status != STATUS.STOPPED:
                self.stop()
        if self.player_process and self.player_process.poll() is not None:
            if self._status != STATUS.STOPPED:
                self.stop()
        return super().status()

    def wait(self, timeout=None):
        """Wait for playback to complete"""
        if self.streaming_thread:
            self.streaming_thread.join(timeout)
        return super().wait(timeout)


# Automatic platform selection
if IS_ANDROID:
    LinuxSound = AndroidNativeStreamingSound
else:
    LinuxSound = LinuxStreamingSound
