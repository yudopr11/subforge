from pathlib import Path

from subforge.models.project import Segment
from subforge.subtitles.srt import render_srt, write_srt


def sample() -> list[Segment]:
    return [
        Segment(
            id=1,
            start=1.2,
            end=3.4,
            source="Halo semuanya!",
            translations={"en": "Hello everyone!"},
        ),
        Segment(
            id=2,
            start=3.5,
            end=6.8,
            source="Welcome back to my channel.",
            translations={"en": "Welcome back to my channel!"},
        ),
    ]


def test_render_source_text() -> None:
    out = render_srt(sample())
    assert out == (
        "1\n00:00:01,200 --> 00:00:03,400\nHalo semuanya!\n\n"
        "2\n00:00:03,500 --> 00:00:06,800\nWelcome back to my channel.\n"
    )


def test_render_translation_preserves_timing() -> None:
    out = render_srt(sample(), language="en")
    # Timing identical to source rendering; only text changed.
    assert "00:00:01,200 --> 00:00:03,400" in out
    assert "Hello everyone!" in out
    assert "Halo" not in out


def test_missing_translation_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(KeyError):
        render_srt(sample(), language="ja")


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "exports" / "en.srt"
    result = write_srt(sample(), target, language="en")
    assert result == target
    assert "Hello everyone!" in target.read_text()
