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
        ),
        Segment(
            id=2,
            start=3.5,
            end=6.8,
            source="Welcome back to my channel.",
        ),
    ]


def test_render_source_text() -> None:
    out = render_srt(sample())
    assert out == (
        "1\n00:00:01,200 --> 00:00:03,400\nHalo semuanya!\n\n"
        "2\n00:00:03,500 --> 00:00:06,800\nWelcome back to my channel.\n"
    )


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "exports" / "source.srt"
    result = write_srt(sample(), target)
    assert result == target
    assert "Halo semuanya!" in target.read_text()
