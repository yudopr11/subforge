"""ASS (Advanced SubStation Alpha) writer (ARCH §20)."""

from dataclasses import dataclass
from pathlib import Path

from subforge.models.project import Segment
from subforge.subtitles.timeutils import format_ass


@dataclass(frozen=True)
class AssStyles:
    font_name: str = "Arial"
    font_size: int = 48
    primary_color: str = "&H00FFFFFF"


_HEADER_TEMPLATE = """\
[Script Info]
Title: SubForge Export
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _text_for(seg: Segment, language: str | None) -> str:
    return seg.source if language is None else seg.translations[language]


def render_ass(
    segments: list[Segment],
    language: str | None = None,
    styles: AssStyles | None = None,
) -> str:
    st = styles or AssStyles()
    lines = [_HEADER_TEMPLATE.format(font=st.font_name, size=st.font_size, primary=st.primary_color)]
    for seg in sorted(segments, key=lambda s: s.start):
        text = _text_for(seg, language)
        lines.append(f"Dialogue: 0,{format_ass(seg.start)},{format_ass(seg.end)},Default,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def write_ass(
    segments: list[Segment],
    path: Path,
    language: str | None = None,
    styles: AssStyles | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ass(segments, language, styles), encoding="utf-8")
    return path
