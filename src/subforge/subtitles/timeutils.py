"""Timestamp conversion between seconds and subtitle formats."""

_MS_PER_HOUR = 3_600_000
_MS_PER_MINUTE = 60_000


def _check_non_negative(seconds: float) -> None:
    if seconds < 0:
        raise ValueError(f"timestamp must be non-negative, got {seconds}")


def format_srt(seconds: float) -> str:
    """Seconds -> ``HH:MM:SS,mmm`` (SRT uses comma milliseconds)."""
    _check_non_negative(seconds)
    ms = round(seconds * 1000)
    h, rem = divmod(ms, _MS_PER_HOUR)
    m, rem = divmod(rem, _MS_PER_MINUTE)
    s, ms2 = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms2:03}"


def format_ass(seconds: float) -> str:
    """Seconds -> ``H:MM:SS.cc`` (ASS uses centiseconds)."""
    _check_non_negative(seconds)
    cs = round(seconds * 100)
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs2 = divmod(rem, 100)
    return f"{h}:{m:02}:{s:02}.{cs2:02}"


def parse_srt(stamp: str) -> float:
    """``HH:MM:SS,mmm`` -> seconds."""
    hms, _, msmillis = stamp.partition(",")
    h, m, s = (int(part) for part in hms.split(":"))
    return h * 3600 + m * 60 + s + int(msmillis) / 1000
