#!/usr/bin/env python3
"""Create seamless loopable audio files.

This script transforms an audio file into a version that loops seamlessly
by finding optimal loop points and applying crossfading techniques.

Usage:
    python create_loop.py input.wav -o output_loop.wav
    python create_loop.py input.wav -o output.wav --crossfade 0.5 --auto-find
    python create_loop.py input.wav -o output.wav --start 1.0 --end 9.5 --crossfade 0.3
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


@dataclass
class LoopPoints:
    """Container for loop point information."""

    start_sample: int
    end_sample: int
    start_time: float
    end_time: float
    quality: float  # 0-1, higher is better


def find_zero_crossings(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Find all zero-crossing positions in the audio.

    Args:
        audio: Audio data as numpy array (samples, channels)
        sample_rate: Sample rate in Hz

    Returns:
        Array of sample indices where zero crossings occur
    """
    # For stereo, check if both channels cross zero
    if audio.ndim == 1:
        mono = audio.astype(np.float64)
    else:
        mono = np.mean(audio, axis=1).astype(np.float64)

    # Find sign changes - vectorized approach
    # A zero crossing happens when adjacent samples have opposite signs
    signs = np.sign(mono)

    # Handle zeros using forward fill (vectorized)
    zero_mask = signs == 0
    if zero_mask.any():
        # Use pandas-style forward fill via numpy
        # Replace zeros with NaN, then forward fill
        signs_float = signs.astype(np.float64)
        signs_float[zero_mask] = np.nan
        # Get indices of non-NaN values
        valid_indices = np.where(~np.isnan(signs_float))[0]
        if len(valid_indices) > 0:
            # Interpolate NaN positions
            nan_indices = np.where(np.isnan(signs_float))[0]
            if len(nan_indices) > 0:
                signs_float[nan_indices] = np.interp(nan_indices, valid_indices, signs_float[valid_indices])
        signs = signs_float
        # Handle any remaining NaNs (at the start)
        signs = np.nan_to_num(signs, nan=1.0)

    # Find where sign changes
    zero_crossings = np.where(np.diff(signs.astype(int)) != 0)[0]
    return zero_crossings


def find_nearest_zero_crossing(audio: np.ndarray, position: int, search_range: int = 1000) -> int:
    """Find the nearest zero-crossing to a given position.

    Args:
        audio: Audio data
        position: Target position in samples
        search_range: Maximum samples to search in each direction

    Returns:
        Sample index of nearest zero crossing, or original position if none found
    """
    zero_crossings = find_zero_crossings(audio, 44100)  # sample_rate not used for finding

    if len(zero_crossings) == 0:
        return position

    # Filter to crossings within search range
    start = max(0, position - search_range)
    end = min(len(audio), position + search_range)

    nearby = zero_crossings[(zero_crossings >= start) & (zero_crossings <= end)]

    if len(nearby) == 0:
        return position

    # Return closest one
    distances = np.abs(nearby - position)
    return int(nearby[np.argmin(distances)])


def compute_correlation(a: np.ndarray, b: np.ndarray) -> float:
    """Compute normalized cross-correlation between two audio segments.

    Args:
        a: First audio segment
        b: Second audio segment

    Returns:
        Correlation coefficient (-1 to 1, higher is better match)
    """
    # Ensure same shape
    min_len = min(len(a), len(b))
    a = a[:min_len]
    b = b[:min_len]

    # Flatten for multi-channel
    if a.ndim > 1:
        a = a.flatten()
    if b.ndim > 1:
        b = b.flatten()

    # Normalize
    a_norm = a - np.mean(a)
    b_norm = b - np.mean(b)

    denom = np.sqrt(np.sum(a_norm**2) * np.sum(b_norm**2))
    if denom < 1e-10:
        return 0.0

    return float(np.sum(a_norm * b_norm) / denom)


def compute_spectral_similarity(a: np.ndarray, b: np.ndarray, sample_rate: int) -> float:
    """Compute spectral similarity between two audio segments using FFT.

    Args:
        a: First audio segment
        b: Second audio segment
        sample_rate: Sample rate

    Returns:
        Similarity score (0-1, higher is better)
    """
    # Ensure same length for FFT comparison
    min_len = min(len(a), len(b))
    a = a[:min_len]
    b = b[:min_len]

    # Convert to mono if stereo
    if a.ndim > 1:
        a = np.mean(a, axis=1)
    if b.ndim > 1:
        b = np.mean(b, axis=1)

    # Compute FFT
    fft_a = np.abs(np.fft.rfft(a.astype(np.float32)))
    fft_b = np.abs(np.fft.rfft(b.astype(np.float32)))

    # Normalize
    fft_a = fft_a / (np.sum(fft_a) + 1e-10)
    fft_b = fft_b / (np.sum(fft_b) + 1e-10)

    # Compute cosine similarity
    similarity = np.dot(fft_a, fft_b) / (np.linalg.norm(fft_a) * np.linalg.norm(fft_b) + 1e-10)
    return float(similarity)


def find_nearest_zero_crossing_fast(position: int, zero_crossings: np.ndarray, search_range: int = 1000) -> int:
    """Find the nearest zero-crossing to a given position from pre-computed crossings.

    Args:
        position: Target position in samples
        zero_crossings: Pre-computed array of zero crossing positions
        search_range: Maximum samples to search in each direction

    Returns:
        Sample index of nearest zero crossing, or original position if none found
    """
    if len(zero_crossings) == 0:
        return position

    # Filter to crossings within search range
    start = max(0, position - search_range)
    end = position + search_range

    nearby = zero_crossings[(zero_crossings >= start) & (zero_crossings <= end)]

    if len(nearby) == 0:
        return position

    # Return closest one
    distances = np.abs(nearby - position)
    return int(nearby[np.argmin(distances)])


def find_optimal_loop_points(
    audio: np.ndarray,
    sample_rate: int,
    min_loop_duration: float = 1.0,
    max_loop_duration: float | None = None,
    crossfade_duration: float = 0.1,
    search_granularity: int = 50,
) -> LoopPoints:
    """Find optimal loop points using correlation and spectral analysis.

    This algorithm searches for the best start and end points that create
    a seamless loop by analyzing waveform similarity and spectral matching.

    Args:
        audio: Audio data as numpy array
        sample_rate: Sample rate in Hz
        min_loop_duration: Minimum loop duration in seconds
        max_loop_duration: Maximum loop duration in seconds (None for entire file)
        crossfade_duration: Expected crossfade duration for alignment
        search_granularity: Number of candidate positions to evaluate per dimension

    Returns:
        LoopPoints with the best found positions
    """
    total_samples = len(audio)
    crossfade_samples = int(crossfade_duration * sample_rate)
    min_samples = int(min_loop_duration * sample_rate)
    max_samples = int(max_loop_duration * sample_rate) if max_loop_duration else total_samples

    # Limit max to file length
    max_samples = min(max_samples, total_samples)

    logger.info(f"Searching for optimal loop points (min={min_loop_duration}s, max={max_loop_duration}s)")

    # Pre-compute zero crossings once for efficiency
    logger.debug("Computing zero crossings...")
    zero_crossings = find_zero_crossings(audio, sample_rate)
    logger.debug(f"Found {len(zero_crossings)} zero crossings")

    best_score = -1.0
    best_start = 0
    best_end = total_samples

    # Generate candidate start positions (search in the beginning portion)
    start_search_end = min(total_samples // 4, int(5 * sample_rate))  # Search first 5 seconds or 1/4 of file
    start_candidates = np.linspace(0, start_search_end, search_granularity, dtype=int)

    # Find zero crossings near start positions for cleaner cuts
    start_candidates = np.array(
        [find_nearest_zero_crossing_fast(int(s), zero_crossings, 500) for s in start_candidates]
    )
    # Remove duplicates
    start_candidates = np.unique(start_candidates)

    total_iterations = len(start_candidates) * search_granularity
    iteration = 0

    for start in start_candidates:
        # For each start, search for best end position
        end_search_start = start + min_samples
        end_search_end = min(start + max_samples, total_samples)

        if end_search_start >= end_search_end:
            continue

        end_candidates = np.linspace(end_search_start, end_search_end, search_granularity, dtype=int)
        end_candidates = np.array(
            [find_nearest_zero_crossing_fast(int(e), zero_crossings, 500) for e in end_candidates]
        )
        # Remove duplicates
        end_candidates = np.unique(end_candidates)

        for end in end_candidates:
            iteration += 1
            if end >= total_samples:
                continue

            # Extract segments for comparison
            # Compare the crossfade region at the end with the beginning
            if end - crossfade_samples < start:
                continue

            end_segment = audio[end - crossfade_samples : end]
            start_segment = audio[start : start + crossfade_samples]

            if len(end_segment) < crossfade_samples or len(start_segment) < crossfade_samples:
                continue

            # Compute similarity scores
            waveform_score = compute_correlation(end_segment, start_segment)
            spectral_score = compute_spectral_similarity(end_segment, start_segment, sample_rate)

            # Combined score (weighted average)
            combined_score = 0.6 * waveform_score + 0.4 * spectral_score

            # Prefer longer loops to avoid unnecessarily short output files.
            # Use an additive blend so that length preference works correctly
            # even when similarity scores are similar (e.g. ambient sounds).
            loop_length = end - start
            length_ratio = loop_length / max_samples
            similarity_score = combined_score
            combined_score = 0.7 * similarity_score + 0.3 * length_ratio

            if combined_score > best_score:
                best_score = combined_score
                best_start = start
                best_end = end

        # Progress logging
        if iteration % 100 == 0:
            logger.debug(f"Progress: {iteration}/{total_iterations} iterations, best score: {best_score:.3f}")

    best_start_time = best_start / sample_rate
    best_end_time = best_end / sample_rate
    quality = max(0, min(1, (best_score + 1) / 2))  # Map -1..1 to 0..1

    logger.info(f"Found loop points: {best_start_time:.3f}s - {best_end_time:.3f}s (quality: {quality:.2f})")

    return LoopPoints(
        start_sample=best_start,
        end_sample=best_end,
        start_time=best_start_time,
        end_time=best_end_time,
        quality=quality,
    )


def create_crossfade_curve(length: int, curve_type: str = "equal_power") -> np.ndarray:
    """Generate a crossfade curve.

    Args:
        length: Number of samples
        curve_type: Type of curve ('linear', 'equal_power', 'smooth')

    Returns:
        Array of fade-in values (0 to 1) and fade-out values (1 to 0)
    """
    t = np.linspace(0, 1, length)

    if curve_type == "linear":
        fade_in = t
        fade_out = 1 - t
    elif curve_type == "equal_power":
        # Equal power crossfade: maintains constant perceived volume
        fade_in = np.sqrt(t)
        fade_out = np.sqrt(1 - t)
    elif curve_type == "smooth":
        # Smooth S-curve using cosine interpolation
        fade_in = (1 - np.cos(t * np.pi)) / 2
        fade_out = (1 - np.cos((1 - t) * np.pi)) / 2
    else:
        raise ValueError(f"Unknown curve type: {curve_type}")

    return fade_in, fade_out


def apply_crossfade(
    audio: np.ndarray,
    sample_rate: int,
    crossfade_duration: float,
    curve_type: str = "equal_power",
    loop_start: int = 0,
    loop_end: int | None = None,
) -> np.ndarray:
    """Apply crossfade to create seamless loop.

    This function extracts the loop region and applies a crossfade between
    the end and beginning of the loop.

    Args:
        audio: Full audio data
        sample_rate: Sample rate in Hz
        crossfade_duration: Duration of crossfade in seconds
        curve_type: Type of crossfade curve
        loop_start: Start sample of the loop region
        loop_end: End sample of the loop region (None for end of file)

    Returns:
        Audio data with crossfade applied, ready for seamless looping
    """
    if loop_end is None:
        loop_end = len(audio)

    crossfade_samples = int(crossfade_duration * sample_rate)

    # Extract the loop region
    loop_audio = audio[loop_start:loop_end].copy()
    loop_length = len(loop_audio)

    if crossfade_samples >= loop_length:
        raise ValueError(
            f"Crossfade duration ({crossfade_duration}s) is too long for loop ({loop_length / sample_rate:.2f}s)"
        )

    logger.info(f"Applying {crossfade_duration}s crossfade ({curve_type} curve)")

    # Generate crossfade curves
    fade_in, fade_out = create_crossfade_curve(crossfade_samples, curve_type)

    # Handle multi-channel audio
    if loop_audio.ndim == 1:
        fade_in = fade_in.reshape(-1, 1)
        fade_out = fade_out.reshape(-1, 1)
    else:
        fade_in = fade_in.reshape(-1, 1)
        fade_out = fade_out.reshape(-1, 1)

    # Get segments for crossfading
    end_segment = loop_audio[-crossfade_samples:].astype(np.float64)
    start_segment = loop_audio[:crossfade_samples].astype(np.float64)

    # Apply crossfade
    crossfaded = end_segment * fade_out + start_segment * fade_in

    # Convert back to original dtype
    if audio.dtype == np.int16:
        crossfaded = np.clip(crossfaded, -32768, 32767).astype(np.int16)
    elif audio.dtype == np.int32:
        crossfaded = np.clip(crossfaded, -2147483648, 2147483647).astype(np.int32)
    elif audio.dtype == np.float32:
        crossfaded = crossfaded.astype(np.float32)
    else:
        crossfaded = crossfaded.astype(np.float64)

    # Construct output: body + crossfaded region
    # Remove the original end segment that was crossfaded
    body = loop_audio[:-crossfade_samples]

    # The output is: body + crossfaded tail
    # When this loops, the crossfaded tail blends with the beginning
    output = np.concatenate([body, crossfaded], axis=0)

    logger.info(f"Output length: {len(output) / sample_rate:.2f}s")

    return output


def process_audio_for_loop(
    input_path: str | Path,
    output_path: str | Path,
    crossfade_duration: float = 0.1,
    curve_type: Literal["linear", "equal_power", "smooth"] = "equal_power",
    auto_find: bool = False,
    start_time: float | None = None,
    end_time: float | None = None,
    min_loop_duration: float | None = None,
    max_loop_duration: float | None = None,
) -> dict:
    """Process an audio file to create a seamless loop.

    Args:
        input_path: Path to input audio file
        output_path: Path for output audio file
        crossfade_duration: Duration of crossfade in seconds
        curve_type: Type of crossfade curve
        auto_find: Automatically find optimal loop points
        start_time: Manual start time in seconds (overrides auto_find)
        end_time: Manual end time in seconds (overrides auto_find)
        min_loop_duration: Minimum loop duration for auto-find (None = 50% of file)
        max_loop_duration: Maximum loop duration for auto-find

    Returns:
        Dictionary with processing information
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    # Read input file
    logger.info(f"Reading: {input_path}")
    audio, sample_rate = sf.read(input_path, dtype="float32")

    # Ensure 2D array (samples, channels)
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)

    # Convert to int16 for processing (better for finding zero crossings)
    original_dtype = audio.dtype
    audio_int = (audio * 32767).astype(np.int16)

    total_duration = len(audio) / sample_rate
    logger.info(f"Input: {total_duration:.2f}s, {sample_rate}Hz, {audio.shape[1]} channel(s)")

    # Smart default for min_loop_duration: use 50% of file length so
    # auto-find doesn't produce unexpectedly short output files.
    if min_loop_duration is None:
        min_loop_duration = max(1.0, total_duration * 0.5)
        logger.debug(f"Auto min_loop_duration: {min_loop_duration:.1f}s")

    # Determine loop points
    if start_time is not None or end_time is not None:
        # Manual mode
        start_sample = int((start_time or 0) * sample_rate)
        end_sample = int((end_time or total_duration) * sample_rate)
        loop_points = LoopPoints(
            start_sample=start_sample,
            end_sample=end_sample,
            start_time=start_sample / sample_rate,
            end_time=end_sample / sample_rate,
            quality=1.0,
        )
        logger.info(f"Using manual loop points: {loop_points.start_time:.3f}s - {loop_points.end_time:.3f}s")
    elif auto_find:
        # Automatic mode
        loop_points = find_optimal_loop_points(
            audio_int,
            sample_rate,
            min_loop_duration=min_loop_duration,
            max_loop_duration=max_loop_duration,
            crossfade_duration=crossfade_duration,
        )
    else:
        # Default: use entire file
        loop_points = LoopPoints(
            start_sample=0,
            end_sample=len(audio),
            start_time=0.0,
            end_time=total_duration,
            quality=1.0,
        )
        logger.info("Using entire file for loop")

    # Apply crossfade
    result = apply_crossfade(
        audio,
        sample_rate,
        crossfade_duration,
        curve_type,
        loop_points.start_sample,
        loop_points.end_sample,
    )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output file
    logger.info(f"Writing: {output_path}")
    sf.write(output_path, result, sample_rate)

    output_duration = len(result) / sample_rate

    return {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "sample_rate": sample_rate,
        "channels": audio.shape[1],
        "input_duration": total_duration,
        "output_duration": output_duration,
        "loop_start": loop_points.start_time,
        "loop_end": loop_points.end_time,
        "crossfade_duration": crossfade_duration,
        "curve_type": curve_type,
        "quality": loop_points.quality,
    }


def main():
    """Main entry point for the loop creator script."""
    parser = argparse.ArgumentParser(
        description="Create seamless loopable audio files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.wav -o loop.wav
      Create a loop using the entire file with default crossfade

  %(prog)s input.wav -o loop.wav --crossfade 0.5 --curve smooth
      Use a 0.5 second smooth crossfade

  %(prog)s input.wav -o loop.wav --auto-find
      Automatically find optimal loop points

  %(prog)s input.wav -o loop.wav --start 2.0 --end 8.5
      Use specific start and end times

  %(prog)s input.wav -o loop.wav --auto-find --min-loop 2.0 --max-loop 10.0
      Find optimal loop between 2 and 10 seconds
        """,
    )

    parser.add_argument("input", type=str, help="Input audio file")
    parser.add_argument("-o", "--output", type=str, required=True, help="Output audio file")

    parser.add_argument(
        "--crossfade",
        type=float,
        default=0.1,
        help="Crossfade duration in seconds (default: 0.1)",
    )

    parser.add_argument(
        "--curve",
        type=str,
        choices=["linear", "equal_power", "smooth"],
        default="equal_power",
        help="Crossfade curve type (default: equal_power)",
    )

    parser.add_argument(
        "--auto-find",
        action="store_true",
        help="Automatically find optimal loop points",
    )

    parser.add_argument(
        "--start",
        type=float,
        help="Loop start time in seconds",
    )

    parser.add_argument(
        "--end",
        type=float,
        help="Loop end time in seconds",
    )

    parser.add_argument(
        "--min-loop",
        type=float,
        default=None,
        help="Minimum loop duration in seconds for auto-find (default: 50%% of file duration)",
    )

    parser.add_argument(
        "--max-loop",
        type=float,
        help="Maximum loop duration in seconds for auto-find (default: entire file)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Check if input file exists
    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    try:
        result = process_audio_for_loop(
            input_path=args.input,
            output_path=args.output,
            crossfade_duration=args.crossfade,
            curve_type=args.curve,
            auto_find=args.auto_find,
            start_time=args.start,
            end_time=args.end,
            min_loop_duration=args.min_loop,
            max_loop_duration=args.max_loop,
        )

        print("\n=== Loop Creation Complete ===")
        print(f"Input:  {result['input_file']} ({result['input_duration']:.2f}s)")
        print(f"Output: {result['output_file']} ({result['output_duration']:.2f}s)")
        print(f"Format: {result['sample_rate']}Hz, {result['channels']} channel(s)")
        print(f"Crossfade: {result['crossfade_duration']}s ({result['curve_type']})")
        if result["loop_start"] > 0 or result["loop_end"] < result["input_duration"]:
            print(f"Loop region: {result['loop_start']:.3f}s - {result['loop_end']:.3f}s")
        print(f"Quality score: {result['quality']:.2f}")

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
