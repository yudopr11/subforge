"""SRT writer. Converts canonical segments to SubRip text (ARCH §19)."""

from pathlib import Path

from subforge.models.project import Segment
from subforge.subtitles.timeutils import format_srt


def render_srt(segments: list[Segment]) -> str:
    blocks = []
    for seg in sorted(segments, key=lambda s: s.start):
        stamp = f"{format_srt(seg.start)} --> {format_srt(seg.end)}"
        blocks.append(f"{seg.id}\n{stamp}\n{seg.source}\n")
    return "\n".join(blocks)


def write_srt(segments: list[Segment], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_srt(segments), encoding="utf-8")
    return path
