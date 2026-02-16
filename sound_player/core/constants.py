"""Audio-related constants for the sound-player library."""

# Maximum sample values for different integer bit depths
# These are used for converting float audio [-1, 1] to integer formats

# 8-bit: 2^7 - 1 = 127 (unsigned, typically used with offset of 128)
MAX_INT8 = 2**7 - 1  # 127

# 16-bit: 2^15 - 1 = 32767
MAX_INT16 = 2**15 - 1  # 32767

# 24-bit: 2^23 - 1 = 8388607
MAX_INT24 = 2**23 - 1  # 8388607

# 32-bit: 2^31 - 1 = 2147483647
MAX_INT32 = 2**31 - 1  # 2147483647

# Minimum sample values (two's complement signed integers)
# For n-bit signed: -2^(n-1)
MIN_INT8 = -(2**7)  # -128
MIN_INT16 = -(2**15)  # -32768
MIN_INT24 = -(2**23)  # -8388608
MIN_INT32 = -(2**31)  # -2147483648

__all__ = [
    "MAX_INT8",
    "MAX_INT16",
    "MAX_INT24",
    "MAX_INT32",
    "MIN_INT8",
    "MIN_INT16",
    "MIN_INT24",
    "MIN_INT32",
]
