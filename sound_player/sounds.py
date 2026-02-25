import logging
import random

from currentplatform import platform

from .audiolayer import AudioLayer

logger = logging.getLogger(__name__)

__all__ = [
    "Sound",
    "RandomRepeatSound",
]

if platform in ("linux", "windows"):
    # Linux and Windows share the same sounddevice/soundfile-based implementation
    from .platform.linux import LinuxPCMSound as Sound
elif platform == "android":
    # Select the Android decoder via environment variable).
    from .platform.android import AndroidPCMSound as Sound
else:
    logger.critical("No implementation found for platform %s", platform)
    raise NotImplementedError(f"No implementation available for platform: {platform}")


class RandomRepeatSound(Sound):
    """A Sound that, when it ends, waits a random duration then enqueues a new
    randomly-selected file from the same list — repeating up to *repeat* times.

    Parameters
    ----------
    filepaths:
        Absolute paths to the candidate audio files.
    player:
        The SoundPlayer instance used to re-enqueue the next sound.
    layer:
        The audio-layer name passed to ``player.enqueue()``.
    repeat:
        How many additional times to play after the first.
        ``None`` (default) means infinite.  ``0`` plays exactly once.
    min_wait / max_wait:
        Bounds (in seconds) of the uniform random pause between the end of
        one file and the start of the next.
    on_end:
        Optional callback invoked once all repeats are exhausted (the action
        lifecycle ``_on_end`` hook).  Not fired on intermediate repeats.
    """

    def __init__(
        self,
        filepaths: list[str],
        layer: AudioLayer,
        loop: int | None = None,
        min_wait: float = 0.0,
        max_wait: float = 0.0,
        on_end=None,
        **kwargs,
    ):
        self._filepaths = filepaths
        self._layer = layer
        self._repeat_remaining = 0 if loop is None else loop
        self._min_wait = min_wait
        self._max_wait = max_wait
        self._final_on_end = on_end

        # Pass on_end=None so BaseSound stores None; we override it below.
        super().__init__(filepath=random.choice(filepaths), on_end=self._check_for_another_sound, **kwargs)

    def _check_for_another_sound(self) -> None:
        """Invoked by the audio layer when the current file finishes playing."""
        repeat_remaining = self._repeat_remaining - 1

        if repeat_remaining <= 0:
            logger.debug("RandomRepeatSound: all repeats exhausted on layer %s", self._layer)
            if self._final_on_end is not None:
                self._final_on_end()
            return

        wait = random.uniform(self._min_wait, self._max_wait)
        logger.debug("RandomRepeatSound: scheduling next file in %.2fs (repeats left: %s)", wait, repeat_remaining)

        next_sound = RandomRepeatSound(
            filepaths=self._filepaths,
            layer=self._layer,
            loop=repeat_remaining,
            min_wait=self._min_wait,
            max_wait=self._max_wait,
            on_end=self._final_on_end,
            on_start=None,  # on_start intentionally omitted: only the initial sounds fire it
        )
        self._layer.enqueue(next_sound, delay=wait)
