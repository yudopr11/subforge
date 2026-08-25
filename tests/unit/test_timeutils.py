import pytest

from subforge.subtitles.timeutils import format_ass, format_srt, parse_srt


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (1.2, "00:00:01,200"),
        (3661.5, "01:01:01,500"),
        (0.0, "00:00:00,000"),
        (59.9996, "00:01:00,000"),  # rounds up cleanly
    ],
)
def test_format_srt(seconds: float, expected: str):
    assert format_srt(seconds) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (1.2, "0:00:01.20"),
        (3661.5, "1:01:01.50"),
        (0.0, "0:00:00.00"),
    ],
)
def test_format_ass(seconds: float, expected: str):
    assert format_ass(seconds) == expected


def test_parse_srt_roundtrip():
    assert parse_srt("00:00:01,200") == 1.2
    assert format_srt(parse_srt("01:01:01,500")) == "01:01:01,500"


def test_negative_raises():
    with pytest.raises(ValueError):
        format_srt(-1.0)
