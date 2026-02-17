"""Android platform implementation for the sound-player library.

Two Sound implementations are available; choose one by editing the import below:

    AndroidPCMSound      — synchronous decode thread, polling with backpressure
    AndroidPCMSoundAsync — async MediaCodec callbacks, event-driven, no poll thread

The SoundPlayer (AudioTrack output) is shared by both.
"""

from .player import AndroidSoundPlayer
from .sound import AndroidPCMSound
from .sound_async import AndroidPCMSoundAsync

__all__ = [
    "AndroidPCMSound",
    "AndroidPCMSoundAsync",
    "AndroidSoundPlayer",
]
