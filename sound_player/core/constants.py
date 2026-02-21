"""Audio-related constants for the sound-player library."""

# Maximum sample values for integer bit depths
# Used for clipping PCM audio to valid range

# 16-bit: 2^15 - 1 = 32767
MAX_INT16 = 2**15 - 1  # 32767

# 32-bit: 2^31 - 1 = 2147483647
MAX_INT32 = 2**31 - 1  # 2147483647

# Minimum sample values (two's complement signed integers)
MIN_INT16 = -(2**15)  # -32768
MIN_INT32 = -(2**31)  # -2147483648

__all__ = [
    "MAX_INT16",
    "MAX_INT32",
    "MIN_INT16",
    "MIN_INT32",
]
