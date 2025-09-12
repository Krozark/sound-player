import numpy as np
import wave
import threading
import time
from typing import Optional, Dict, Any, Tuple, Protocol, runtime_checkable
from enum import Enum
import io
import struct
from abc import ABC, abstractmethod

class PlaybackState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"

class FadeState(Enum):
    NONE = "none"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"

@runtime_checkable
class AudioSource(Protocol):
    """Interface for an audio source"""

    def get_audio_data(self, num_samples: int, sample_rate: int) -> np.ndarray:
        """Returns audio samples (stereo)"""
        ...

    def get_sample_rate(self) -> int:
        """Returns the sample rate of the source"""
        ...

    def get_duration_samples(self) -> int:
        """Returns total duration in samples (-1 if infinite)"""
        ...

    def reset(self):
        """Resets the source to the beginning"""
        ...

    def is_finished(self) -> bool:
        """Indicates if the source has finished"""
        ...

class AudioTrack(AudioSource):
    """
    Audio source based on a local WAV file
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

        # Load the WAV file
        self.sample_rate, self.audio_data = self._load_wav_file(file_path)
        self.duration_samples = len(self.audio_data)
        self.duration_ms = (self.duration_samples / self.sample_rate) * 1000

        # Playback position
        self.position_samples = 0
        self.lock = threading.Lock()

    def _load_wav_file(self, file_path: str) -> Tuple[int, np.ndarray]:
        """Load a WAV file and return sample rate and data"""
        try:
            with wave.open(file_path, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                n_channels = wav_file.getnchannels()
                n_frames = wav_file.getnframes()
                sample_width = wav_file.getsampwidth()

                # Read raw data
                raw_data = wav_file.readframes(n_frames)

                # Convert based on bit depth
                if sample_width == 1:  # 8-bit
                    audio_array = np.frombuffer(raw_data, dtype=np.uint8)
                    audio_array = (audio_array.astype(np.float32) - 128) / 128.0
                elif sample_width == 2:  # 16-bit
                    audio_array = np.frombuffer(raw_data, dtype=np.int16)
                    audio_array = audio_array.astype(np.float32) / 32768.0
                elif sample_width == 4:  # 32-bit
                    audio_array = np.frombuffer(raw_data, dtype=np.int32)
                    audio_array = audio_array.astype(np.float32) / 2147483648.0
                else:
                    raise ValueError(f"Unsupported bit depth: {sample_width} bytes")

                # Convert to stereo if mono
                if n_channels == 1:
                    audio_array = np.column_stack([audio_array, audio_array])
                elif n_channels == 2:
                    audio_array = audio_array.reshape(-1, 2)
                else:
                    # For more than 2 channels, take only the first 2
                    audio_array = audio_array.reshape(-1, n_channels)[:, :2]

                return sample_rate, audio_array

        except Exception as e:
            raise Exception(f"Error loading file {file_path}: {e}")

    def get_audio_data(self, num_samples: int, sample_rate: int) -> np.ndarray:
        """Get audio data for a given number of samples"""
        with self.lock:
            if self.position_samples >= self.duration_samples:
                return np.zeros((num_samples, 2), dtype=np.float32)

            # Extract samples
            end_pos = min(self.position_samples + num_samples, self.duration_samples)
            audio_chunk = self.audio_data[self.position_samples:end_pos].copy()

            # Advance position
            self.position_samples = end_pos

            # Fill with silence if necessary
            if len(audio_chunk) < num_samples:
                silence = np.zeros((num_samples - len(audio_chunk), 2), dtype=np.float32)
                if len(audio_chunk) > 0:
                    audio_chunk = np.vstack([audio_chunk, silence])
                else:
                    audio_chunk = silence

            return audio_chunk

    def get_sample_rate(self) -> int:
        return self.sample_rate

    def get_duration_samples(self) -> int:
        return self.duration_samples

    def reset(self):
        with self.lock:
            self.position_samples = 0

    def is_finished(self) -> bool:
        with self.lock:
            return self.position_samples >= self.duration_samples

class StreamSource(AudioSource):
    """
    Audio source based on real-time data stream
    Example implementation for network streams, microphone, etc.
    """

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 8192):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.audio_buffer = io.BytesIO()
        self.lock = threading.Lock()
        self.is_active = True

    def feed_data(self, audio_data: np.ndarray):
        """Feed the source with audio data (called by producer)"""
        with self.lock:
            if self.is_active:
                # Convert to bytes and add to buffer
                audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                self.audio_buffer.write(audio_bytes)

    def get_audio_data(self, num_samples: int, sample_rate: int) -> np.ndarray:
        """Get samples from stream buffer"""
        with self.lock:
            if not self.is_active:
                return np.zeros((num_samples, 2), dtype=np.float32)

            bytes_needed = num_samples * 2 * 2  # 2 channels, 2 bytes per sample
            data = self.audio_buffer.read(bytes_needed)

            if len(data) < bytes_needed:
                # Not enough data, fill with silence
                silence_bytes = bytes_needed - len(data)
                data += b'\x00' * silence_bytes

            # Convert bytes to numpy array
            audio_array = np.frombuffer(data, dtype=np.int16)
            audio_array = audio_array.astype(np.float32) / 32768.0
            return audio_array.reshape(-1, 2)

    def get_sample_rate(self) -> int:
        return self.sample_rate

    def get_duration_samples(self) -> int:
        return -1  # Infinite duration for stream

    def reset(self):
        with self.lock:
            self.audio_buffer = io.BytesIO()

    def is_finished(self) -> bool:
        return not self.is_active

    def close(self):
        """Close the stream"""
        with self.lock:
            self.is_active = False

class AudioProcessor(AudioSource):
    """
    Class to process and modify a SINGLE audio source with real-time controls
    Implements AudioSource to enable full composability
    """

    def __init__(self, audio_source: AudioSource):
        self.audio_source = audio_source
        self.lock = threading.Lock()

        # Playback states
        self.state = PlaybackState.STOPPED
        self.start_time = None
        self.pause_position_samples = 0

        # Audio controls
        self.volume = 1.0
        self.repeat_count = 0  # -1 for infinite, 0 for no repeat
        self.current_loop = 0

        # Fade controls
        self.fade_state = FadeState.NONE
        self.fade_duration_samples = 0
        self.fade_current_samples = 0
        self.fade_start_volume = 0.0
        self.fade_target_volume = 1.0

        # Virtual playback position
        self.virtual_position_samples = 0

    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)"""
        with self.lock:
            self.volume = max(0.0, min(1.0, volume))

    def set_repeat_count(self, count: int):
        """Set number of repetitions (-1 for infinite)"""
        with self.lock:
            self.repeat_count = count

    def play(self):
        """Start playback"""
        with self.lock:
            if self.state == PlaybackState.PAUSED:
                # Resume from pause
                self.start_time = time.time()
                self.virtual_position_samples = self.pause_position_samples
            else:
                # New playback
                self.start_time = time.time()
                self.virtual_position_samples = 0
                self.current_loop = 0
                self.audio_source.reset()
            self.state = PlaybackState.PLAYING

    def pause(self):
        """Pause playback"""
        with self.lock:
            if self.state == PlaybackState.PLAYING:
                elapsed_time = time.time() - self.start_time
                elapsed_samples = int(elapsed_time * self.audio_source.get_sample_rate())
                self.pause_position_samples = self.virtual_position_samples + elapsed_samples
                self.state = PlaybackState.PAUSED

    def stop(self):
        """Stop playback"""
        with self.lock:
            self.state = PlaybackState.STOPPED
            self.virtual_position_samples = 0
            self.pause_position_samples = 0
            self.current_loop = 0
            self.start_time = None
            self.audio_source.reset()
            self._stop_fade()

    def fade_in(self, duration_ms: float):
        """Start fade in"""
        with self.lock:
            if self.state == PlaybackState.PLAYING:
                self.fade_state = FadeState.FADE_IN
                self.fade_duration_samples = int(duration_ms * self.audio_source.get_sample_rate() / 1000)
                self.fade_current_samples = 0
                self.fade_start_volume = 0.0
                self.fade_target_volume = self.volume

    def fade_out(self, duration_ms: float):
        """Start fade out"""
        with self.lock:
            if self.state == PlaybackState.PLAYING:
                self.fade_state = FadeState.FADE_OUT
                self.fade_duration_samples = int(duration_ms * self.audio_source.get_sample_rate() / 1000)
                self.fade_current_samples = 0
                self.fade_start_volume = self.volume
                self.fade_target_volume = 0.0

    def _stop_fade(self):
        """Stop current fade"""
        self.fade_state = FadeState.NONE
        self.fade_current_samples = 0

    def _calculate_fade_volume(self, num_samples: int) -> np.ndarray:
        """Calculate fade volumes for samples"""
        if self.fade_state == FadeState.NONE:
            return np.full(num_samples, self.volume, dtype=np.float32)

        volumes = np.zeros(num_samples, dtype=np.float32)

        for i in range(num_samples):
            if self.fade_current_samples >= self.fade_duration_samples:
                # Fade complete
                if self.fade_state == FadeState.FADE_OUT:
                    volumes[i] = 0.0
                    # Stop playback after fade out
                    if i == num_samples - 1:
                        self.state = PlaybackState.STOPPED
                else:
                    volumes[i] = self.volume
                self._stop_fade()
            else:
                # Linear interpolation
                progress = self.fade_current_samples / self.fade_duration_samples
                fade_volume = self.fade_start_volume + (self.fade_target_volume - self.fade_start_volume) * progress
                volumes[i] = fade_volume
                self.fade_current_samples += 1

        return volumes

    def get_current_position_samples(self) -> int:
        """Get current position in samples"""
        with self.lock:
            if self.state == PlaybackState.PLAYING and self.start_time:
                elapsed_time = time.time() - self.start_time
                elapsed_samples = int(elapsed_time * self.audio_source.get_sample_rate())
                return self.virtual_position_samples + elapsed_samples
            elif self.state == PlaybackState.PAUSED:
                return self.pause_position_samples
            return self.virtual_position_samples

    # AudioSource interface implementation
    def get_audio_data(self, num_samples: int, sample_rate: int) -> np.ndarray:
        """AudioSource interface - returns processed audio data"""
        return self.get_stream_data(num_samples, sample_rate)

    def get_sample_rate(self) -> int:
        """AudioSource interface - returns underlying source sample rate"""
        return self.audio_source.get_sample_rate()

    def get_duration_samples(self) -> int:
        """AudioSource interface - returns underlying source duration"""
        return self.audio_source.get_duration_samples()

    def reset(self):
        """AudioSource interface - reset source and processor state"""
        with self.lock:
            self.audio_source.reset()
            self.virtual_position_samples = 0
            self.pause_position_samples = 0
            self.current_loop = 0
            self._stop_fade()

    def is_finished(self) -> bool:
        """AudioSource interface - check if finished"""
        if self.state == PlaybackState.STOPPED:
            return True

        # For infinite sources (streams), never finished if playing
        source_duration = self.audio_source.get_duration_samples()
        if source_duration == -1:
            return False

        # For finite sources, check repetitions
        if self.repeat_count == -1:
            return False  # Infinite repeat

        current_pos = self.get_current_position_samples()
        total_duration = source_duration * (self.repeat_count + 1)
        return current_pos >= total_duration

    def get_state(self) -> PlaybackState:
        """Get playback state"""
        with self.lock:
            return self.state

    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self.get_state() == PlaybackState.PLAYING

    # Convenience methods for compatibility
    def get_stream_data(self, num_samples: int, target_sample_rate: int = None) -> np.ndarray:
        """
        Get processed audio stream (main interface)
        """
        with self.lock:
            if self.state != PlaybackState.PLAYING:
                return np.zeros((num_samples, 2), dtype=np.float32)

            # Handle repetitions
            source_duration = self.audio_source.get_duration_samples()
            if source_duration > 0:  # Finite sources only
                current_pos = self.get_current_position_samples()
                current_pos_in_track = current_pos % source_duration

                if current_pos >= source_duration * (self.current_loop + 1):
                    self.current_loop += 1
                    if self.repeat_count != -1 and self.current_loop > self.repeat_count:
                        self.stop()
                        return np.zeros((num_samples, 2), dtype=np.float32)
                    # Reset source for new loop
                    self.audio_source.reset()

            # Get data from source
            audio_data = self.audio_source.get_audio_data(num_samples, target_sample_rate or self.audio_source.get_sample_rate())

            # Apply volume with fade
            fade_volumes = self._calculate_fade_volume(num_samples)

            # Apply volumes (fade + main volume)
            for i in range(len(audio_data)):
                if i < len(fade_volumes):
                    audio_data[i] *= fade_volumes[i]
                else:
                    audio_data[i] *= self.volume

            return audio_data

class AudioMixer(AudioSource):
    """
    Class to mix multiple AudioProcessor into a single stream
    Implements AudioSource to enable composability (mixer of mixers)
    """

    def __init__(self, sample_rate: int = 44100, chunk_duration_ms: int = 100):
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_size_samples = int(sample_rate * chunk_duration_ms / 1000)

        # Audio processor management
        self.processors: list[AudioProcessor] = []
        self.lock = threading.Lock()

        # Global mixer states (acts as an AudioProcessor)
        self.mixer_volume = 1.0
        self.mixer_state = PlaybackState.STOPPED
        self.mixer_fade_state = FadeState.NONE
        self.mixer_fade_duration_samples = 0
        self.mixer_fade_current_samples = 0
        self.mixer_fade_start_volume = 0.0
        self.mixer_fade_target_volume = 1.0

        # Output buffer in RAM
        self.output_buffer = io.BytesIO()
        self.is_streaming = False
        self.stream_thread = None

        # Statistics
        self.total_chunks_mixed = 0

    def add_processor(self, audio_source: AudioSource) -> AudioProcessor:
        """Add an audio processor to the mixer"""
        with self.lock:
            processor = AudioProcessor(audio_source)
            self.processors.append(processor)
            return processor

    def add_track(self, file_path: str) -> AudioProcessor:
        """Add an audio track to the mixer (convenience method)"""
        audio_track = AudioTrack(file_path)
        return self.add_processor(audio_track)

    def remove_processor(self, processor: AudioProcessor) -> bool:
        """Remove a processor from the mixer"""
        with self.lock:
            if processor in self.processors:
                processor.stop()
                self.processors.remove(processor)
                return True
            return False

    def remove_processor_by_index(self, index: int) -> bool:
        """Remove a processor by index"""
        with self.lock:
            if 0 <= index < len(self.processors):
                self.processors[index].stop()
                del self.processors[index]
                return True
            return False

    def get_processor(self, index: int) -> Optional[AudioProcessor]:
        """Get a processor by index"""
        with self.lock:
            if 0 <= index < len(self.processors):
                return self.processors[index]
            return None

    def get_processor_count(self) -> int:
        """Get number of processors"""
        with self.lock:
            return len(self.processors)

    def clear_all_processors(self):
        """Remove all processors"""
        with self.lock:
            for processor in self.processors:
                processor.stop()
            self.processors.clear()

    # AudioProcessor-like interface for global mixer control
    def set_volume(self, volume: float):
        """Set global mixer volume"""
        with self.lock:
            self.mixer_volume = max(0.0, min(1.0, volume))

    def play(self):
        """Play all tracks"""
        with self.lock:
            self.mixer_state = PlaybackState.PLAYING
            for processor in self.processors:
                processor.play()

    def pause(self):
        """Pause all tracks"""
        with self.lock:
            self.mixer_state = PlaybackState.PAUSED
            for processor in self.processors:
                processor.pause()

    def stop(self):
        """Stop all tracks"""
        with self.lock:
            self.mixer_state = PlaybackState.STOPPED
            self.mixer_fade_state = FadeState.NONE
            for processor in self.processors:
                processor.stop()

    def fade_in(self, duration_ms: float):
        """Global fade in for mixer"""
        with self.lock:
            if self.mixer_state == PlaybackState.PLAYING:
                self.mixer_fade_state = FadeState.FADE_IN
                self.mixer_fade_duration_samples = int(duration_ms * self.sample_rate / 1000)
                self.mixer_fade_current_samples = 0
                self.mixer_fade_start_volume = 0.0
                self.mixer_fade_target_volume = self.mixer_volume

    def fade_out(self, duration_ms: float):
        """Global fade out for mixer"""
        with self.lock:
            if self.mixer_state == PlaybackState.PLAYING:
                self.mixer_fade_state = FadeState.FADE_OUT
                self.mixer_fade_duration_samples = int(duration_ms * self.sample_rate / 1000)
                self.mixer_fade_current_samples = 0
                self.mixer_fade_start_volume = self.mixer_volume
                self.mixer_fade_target_volume = 0.0

    def _calculate_mixer_fade_volume(self, num_samples: int) -> np.ndarray:
        """Calculate fade volume for mixer"""
        if self.mixer_fade_state == FadeState.NONE:
            return np.full(num_samples, self.mixer_volume, dtype=np.float32)

        volumes = np.zeros(num_samples, dtype=np.float32)

        for i in range(num_samples):
            if self.mixer_fade_current_samples >= self.mixer_fade_duration_samples:
                if self.mixer_fade_state == FadeState.FADE_OUT:
                    volumes[i] = 0.0
                    if i == num_samples - 1:
                        self.stop()
                else:
                    volumes[i] = self.mixer_volume
                self.mixer_fade_state = FadeState.NONE
            else:
                progress = self.mixer_fade_current_samples / self.mixer_fade_duration_samples
                fade_volume = self.mixer_fade_start_volume + (self.mixer_fade_target_volume - self.mixer_fade_start_volume) * progress
                volumes[i] = fade_volume
                self.mixer_fade_current_samples += 1

        return volumes

    # AudioSource interface implementation for composability
    def get_audio_data(self, num_samples: int, sample_rate: int) -> np.ndarray:
        """AudioSource interface - allows using mixer as a source"""
        return self.get_stream_data(num_samples, sample_rate)

    def get_sample_rate(self) -> int:
        """AudioSource interface"""
        return self.sample_rate

    def get_duration_samples(self) -> int:
        """AudioSource interface - infinite duration for mixer"""
        return -1

    def reset(self):
        """AudioSource interface - reset all processors"""
        with self.lock:
            for processor in self.processors:
                if hasattr(processor.audio_source, 'reset'):
                    processor.audio_source.reset()

    def is_finished(self) -> bool:
        """AudioSource interface - mixer is never finished"""
        return False

    def get_stream_data(self, num_samples: int = None, target_sample_rate: int = None) -> np.ndarray:
        """
        Get mixed stream (AudioProcessor interface)
        """
        if num_samples is None:
            num_samples = self.chunk_size_samples
        if target_sample_rate is None:
            target_sample_rate = self.sample_rate

        processors = self.processors.copy()

        if not processors or self.mixer_state != PlaybackState.PLAYING:
            return np.zeros((num_samples, 2), dtype=np.float32)

        # Mix all tracks
        mixed_audio = None

        for processor in processors:
            processor_data = processor.get_stream_data(num_samples, target_sample_rate)

            if mixed_audio is None:
                mixed_audio = processor_data.copy()
            else:
                mixed_audio += processor_data

        # Apply global mixer volume and fade
        mixer_fade_volumes = self._calculate_mixer_fade_volume(num_samples)

        for i in range(len(mixed_audio)):
            if i < len(mixer_fade_volumes):
                mixed_audio[i] *= mixer_fade_volumes[i]

        # Soft normalization
        max_val = np.max(np.abs(mixed_audio))
        if max_val > 1.0:
            mixed_audio = mixed_audio / (1.0 + max_val - 1.0)

        return mixed_audio

    # Advanced mixer methods
    def set_all_volumes(self, volume: float):
        """Set volume for all processors"""
        with self.lock:
            for processor in self.processors:
                processor.set_volume(volume)

    def set_all_repeat_counts(self, repeat_count: int):
        """Set repeat count for all processors"""
        with self.lock:
            for processor in self.processors:
                processor.set_repeat_count(repeat_count)

    def fade_all_in(self, duration_ms: float):
        """Fade in all processors"""
        with self.lock:
            for processor in self.processors:
                processor.fade_in(duration_ms)

    def fade_all_out(self, duration_ms: float):
        """Fade out all processors"""
        with self.lock:
            for processor in self.processors:
                processor.fade_out(duration_ms)

    def crossfade(self, from_processor: AudioProcessor, to_processor: AudioProcessor, duration_ms: float):
        """Crossfade between two processors"""
        if from_processor in self.processors and to_processor in self.processors:
            from_processor.fade_out(duration_ms)
            to_processor.fade_in(duration_ms)
            if to_processor.get_state() != PlaybackState.PLAYING:
                to_processor.play()

    def solo_processor(self, solo_processor: AudioProcessor):
        """Solo a processor (mute others)"""
        with self.lock:
            for processor in self.processors:
                if processor == solo_processor:
                    processor.set_volume(1.0)
                else:
                    processor.set_volume(0.0)

    def unsolo_all(self, default_volume: float = 1.0):
        """Disable solo and restore default volume"""
        with self.lock:
            for processor in self.processors:
                processor.set_volume(default_volume)

    def start_streaming(self):
        """Start streaming the mix to RAM"""
        with self.lock:
            if not self.is_streaming:
                self.is_streaming = True
                self.output_buffer = io.BytesIO()
                self.total_chunks_mixed = 0
                self.stream_thread = threading.Thread(target=self._stream_worker)
                self.stream_thread.daemon = True
                self.stream_thread.start()

    def stop_streaming(self):
        """Stop streaming"""
        with self.lock:
            self.is_streaming = False

        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join()

    def _stream_worker(self):
        """Worker thread for continuous streaming"""
        while self.is_streaming:
            start_time = time.time()

            # Get mixed data
            mixed_chunk = self.get_stream_data()

            # Convert to int16 for audio
            audio_int16 = (mixed_chunk * 32767).astype(np.int16)

            # Write to buffer
            with self.lock:
                self.output_buffer.write(audio_int16.tobytes())
                self.total_chunks_mixed += 1

            # Precise timing
            processing_time = time.time() - start_time
            sleep_time = max(0, (self.chunk_duration_ms / 1000.0) - processing_time)

            if sleep_time > 0:
                time.sleep(sleep_time)

    def get_output_stream(self) -> io.BytesIO:
        """Get output stream in RAM"""
        with self.lock:
            return self.output_buffer

    def get_output_data(self, clear_after_read: bool = True) -> bytes:
        """Get output buffer data"""
        with self.lock:
            data = self.output_buffer.getvalue()
            if clear_after_read:
                self.output_buffer = io.BytesIO()
            return data

    def clear_output_buffer(self):
        """Clear output buffer"""
        with self.lock:
            self.output_buffer = io.BytesIO()

    def get_stats(self) -> Dict[str, Any]:
        """Get mixer statistics"""
        with self.lock:
            return {
                "is_streaming": self.is_streaming,
                "sample_rate": self.sample_rate,
                "chunk_duration_ms": self.chunk_duration_ms,
                "total_chunks_mixed": self.total_chunks_mixed,
                "buffer_size_bytes": len(self.output_buffer.getvalue()),
                "total_processors": len(self.processors),
                "playing_processors": len([p for p in self.processors if p.is_playing()]),
                "mixer_volume": self.mixer_volume,
                "mixer_state": self.mixer_state.value
            }

# Utility function to create test WAV files
def create_test_wav(filename: str, frequency: float = 440.0, duration: float = 5.0, sample_rate: int = 44100):
    """Create a test WAV file with a sine wave tone"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave_data = np.sin(2 * np.pi * frequency * t)
    stereo_wave = np.column_stack([wave_data, wave_data])

    audio_data = (stereo_wave * 32767).astype(np.int16)

    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

# Advanced usage example with composability
if __name__ == "__main__":
# Advanced usage example with composability
if __name__ == "__main__":
    import os

    # Create test files
    test_files = ["test_440hz.wav", "test_880hz.wav", "test_220hz.wav"]

    for i, filename in enumerate(test_files):
        if not os.path.exists(filename):
            frequency = 440.0 * (2 ** (i-1)) if i > 0 else 220.0
            create_test_wav(filename, frequency, 4.0)
            print(f"Test file created: {filename} ({frequency}Hz)")

    try:
        # === COMPOSABILITY DEMONSTRATION ===
        print("=== Creating composed mixers ===")

        # Main mixer
        main_mixer = AudioMixer(sample_rate=44100, chunk_duration_ms=50)

        # Sub-mixer 1: Bass frequencies
        bass_mixer = AudioMixer(sample_rate=44100, chunk_duration_ms=50)
        bass_proc = bass_mixer.add_track(test_files[2])  # 220Hz
        bass_proc.set_volume(0.4)
        bass_proc.set_repeat_count(-1)

        # Sub-mixer 2: Treble frequencies
        treble_mixer = AudioMixer(sample_rate=44100, chunk_duration_ms=50)
        treble_proc1 = treble_mixer.add_track(test_files[0])  # 440Hz
        treble_proc2 = treble_mixer.add_track(test_files[1])  # 880Hz
        treble_proc1.set_volume(0.3)
        treble_proc2.set_volume(0.2)
        treble_proc1.set_repeat_count(-1)
        treble_proc2.set_repeat_count(-1)

        # Add sub-mixers to main mixer (FULL COMPOSABILITY!)
        main_mixer.add_processor(bass_mixer)
        main_mixer.add_processor(treble_mixer)

        print("=== Stream Source demonstration ===")

        # Create stream source for simulation
        stream_source = StreamSource(sample_rate=44100)
        stream_processor = main_mixer.add_processor(stream_source)
        stream_processor.set_volume(0.3)

        # Simulate stream data feeding
        def feed_stream():
            """Simulation of a data producer for stream"""
            for i in range(100):  # 100 data chunks
                t = np.linspace(i*0.1, (i+1)*0.1, 1024, False)
                # Sine wave that changes frequency
                freq = 300 + 100 * np.sin(i * 0.1)
                wave_data = np.sin(2 * np.pi * freq * t) * 0.1
                stereo_data = np.column_stack([wave_data, wave_data])
                stream_source.feed_data(stereo_data)
                time.sleep(0.1)
            stream_source.close()

        # Start stream producer in background
        stream_thread = threading.Thread(target=feed_stream)
        stream_thread.daemon = True
        stream_thread.start()

        print("=== Advanced controls testing ===")

        # Start streaming
        main_mixer.start_streaming()

        # Start all sub-mixers
        bass_mixer.play()
        treble_mixer.play()
        stream_processor.play()

        # Main mixer controls
        main_mixer.set_volume(0.8)
        main_mixer.play()

        print("Phase 1: Normal playback (3s)")
        time.sleep(3)

        print("Phase 2: Crossfade bass -> treble (2s)")
        # Create wrapper processors for crossfade
        bass_wrapper = AudioProcessor(bass_mixer)
        treble_wrapper = AudioProcessor(treble_mixer)
        main_mixer.processors[0] = bass_wrapper  # Replace temporarily
        main_mixer.processors[1] = treble_wrapper
        main_mixer.crossfade(bass_wrapper, treble_wrapper, 2000)
        time.sleep(3)

        print("Phase 3: Solo treble mixer")
        main_mixer.solo_processor(treble_wrapper)
        time.sleep(2)

        print("Phase 4: Unsolo and global fade out")
        main_mixer.unsolo_all(0.5)
        main_mixer.fade_out(3000)
        time.sleep(4)

        print("Phase 5: Global fade in")
        main_mixer.fade_in(2000)
        main_mixer.play()  # Restart if stopped by fade out
        time.sleep(3)

        # Individual processor controls
        print("Phase 6: Individual controls")
        treble_proc1.fade_out(1000)  # Fade out one track from treble mixer
        time.sleep(2)
        treble_proc1.fade_in(1500)   # Fade in
        time.sleep(2)

        # Final statistics
        print("\n=== Statistics ===")
        print(f"Main mixer: {main_mixer.get_stats()}")
        print(f"Bass mixer processors: {bass_mixer.get_processor_count()}")
        print(f"Treble mixer processors: {treble_mixer.get_processor_count()}")

        # Clean shutdown
        main_mixer.stop_streaming()
        bass_mixer.stop()
        treble_mixer.stop()

        output_data = main_mixer.get_output_data()
        print(f"Total data generated: {len(output_data)} bytes")

        print("=== Mix save test ===")
        if len(output_data) > 0:
            # Save mix to WAV
            audio_array = np.frombuffer(output_data, dtype=np.int16)
            audio_array = audio_array.reshape(-1, 2)

            with wave.open("mixed_output.wav", 'wb') as wav_file:
                wav_file.setnchannels(2)
                wav_file.setsampwidth(2)
                wav_file.setframerate(44100)
                wav_file.writeframes(output_data)
            print("Mix saved to 'mixed_output.wav'")

        # === NESTED MIXER EXAMPLE ===
        print("\n=== Nested mixer architecture test ===")

        # Create a complex nested structure
        master = AudioMixer(sample_rate=44100)

        # Level 1 mixers
        drums_mixer = AudioMixer()
        instruments_mixer = AudioMixer()
        vocals_mixer = AudioMixer()

        # Level 2 processors
        kick_proc = drums_mixer.add_track(test_files[2])    # Low freq as kick
        snare_proc = drums_mixer.add_track(test_files[0])   # Mid freq as snare

        guitar_proc = instruments_mixer.add_track(test_files[0])
        bass_proc = instruments_mixer.add_track(test_files[2])

        vocal_proc = vocals_mixer.add_track(test_files[1])  # High freq as vocal

        # Configure individual tracks
        kick_proc.set_volume(0.8)
        snare_proc.set_volume(0.6)
        guitar_proc.set_volume(0.4)
        bass_proc.set_volume(0.7)
        vocal_proc.set_volume(0.5)

        # Add level 1 mixers to master (nested structure)
        master.add_processor(drums_mixer)
        master.add_processor(instruments_mixer)
        master.add_processor(vocals_mixer)

        print("Nested structure created:")
        print("Master Mixer")
        print("├── Drums Mixer")
        print("│   ├── Kick (220Hz)")
        print("│   └── Snare (440Hz)")
        print("├── Instruments Mixer")
        print("│   ├── Guitar (440Hz)")
        print("│   └── Bass (220Hz)")
        print("└── Vocals Mixer")
        print("    └── Vocal (880Hz)")

        # Test the nested structure
        master.start_streaming()

        # Start individual mixers
        drums_mixer.play()
        instruments_mixer.play()
        vocals_mixer.play()
        master.play()

        time.sleep(2)

        # Individual mixer control
        print("Fading out drums mixer...")
        drums_mixer.fade_out(1500)
        time.sleep(2)

        print("Soloing vocals...")
        master.solo_processor(master.get_processor(2))  # Vocals mixer
        time.sleep(2)

        print("Restoring all...")
        master.unsolo_all(0.6)
        drums_mixer.fade_in(1000)
        time.sleep(2)

        # Final cleanup
        master.stop_streaming()
        drums_mixer.stop()
        instruments_mixer.stop()
        vocals_mixer.stop()

        nested_output = master.get_output_data()
        print(f"Nested mix data: {len(nested_output)} bytes")

        if len(nested_output) > 0:
            with wave.open("nested_mix_output.wav", 'wb') as wav_file:
                wav_file.setnchannels(2)
                wav_file.setsampwidth(2)
                wav_file.setframerate(44100)
                wav_file.writeframes(nested_output)
            print("Nested mix saved to 'nested_mix_output.wav'")

        print("\n=== Performance test ===")

        # Test with many processors
        perf_mixer = AudioMixer(sample_rate=44100, chunk_duration_ms=20)  # Smaller chunks

        # Add many processors
        processors = []
        for i in range(10):
            proc = perf_mixer.add_track(test_files[i % len(test_files)])
            proc.set_volume(0.1)  # Low volume to prevent clipping
            proc.set_repeat_count(-1)
            processors.append(proc)

        print(f"Created performance test with {len(processors)} processors")

        perf_mixer.start_streaming()
        perf_mixer.play()

        # Run for a short time and measure
        start_time = time.time()
        time.sleep(3)
        end_time = time.time()

        perf_mixer.stop_streaming()

        perf_stats = perf_mixer.get_stats()
        processing_ratio = perf_stats['total_chunks_mixed'] / ((end_time - start_time) * 1000 / 20)

        print(f"Performance stats:")
        print(f"  - Chunks mixed: {perf_stats['total_chunks_mixed']}")
        print(f"  - Processing ratio: {processing_ratio:.2f}")
        print(f"  - Buffer size: {perf_stats['buffer_size_bytes']} bytes")
        print(f"  - Active processors: {perf_stats['playing_processors']}")

        perf_output = perf_mixer.get_output_data()
        if len(perf_output) > 0:
            with wave.open("performance_test.wav", 'wb') as wav_file:
                wav_file.setnchannels(2)
                wav_file.setsampwidth(2)
                wav_file.setframerate(44100)
                wav_file.writeframes(perf_output)
            print("Performance test saved to 'performance_test.wav'")

        print("\n=== All tests completed successfully ===")

        # === SPEAKER TESTS ===
        print("\n" + "="*50)
        print("SPEAKER PLAYBACK TESTS")
        print("="*50)

        # Run speaker tests
        user_input = input("\nRun speaker tests? (y/n): ").strip().lower()
        if user_input == 'y':
            print("\nChoose test type:")
            print("1 - Interactive test (full mixer control)")
            print("2 - Simple tone test (quick verification)")
            print("3 - Advanced automated test")

            test_choice = input("Enter choice (1-3): ").strip()

            if test_choice == '1':
                test_speaker_playback()
            elif test_choice == '2':
                simple_speaker_test()
            elif test_choice == '3':
                advanced_speaker_test()
            else:
                print("Invalid choice")
        else:
            print("Skipping speaker tests")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
