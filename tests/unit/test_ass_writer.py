from subforge.models.project import Segment
from subforge.subtitles.ass import AssStyles, render_ass


def sample() -> list[Segment]:
    return [
        Segment(id=1, start=1.2, end=3.4, source="Halo semuanya!"),
        Segment(id=2, start=3.5, end=6.8, source="Selamat datang kembali."),
    ]


def test_header_contains_script_info_and_default_style() -> None:
    out = render_ass(sample())
    assert "[Script Info]" in out
    assert "PlayResX: 1920" in out
    assert "Style: Default,Arial,48,&H00FFFFFF" in out


def test_dialogue_lines_use_ass_timing() -> None:
    out = render_ass(sample())
    assert "Dialogue: 0,0:00:01.20,0:00:03.40,Default,,0,0,0,,Halo semuanya!" in out
    assert "Selamat datang kembali." in out


def test_styles_override_defaults() -> None:
    out = render_ass(sample(), styles=AssStyles(font_name="Noto Sans", font_size=40))
    assert "Style: Default,Noto Sans,40,&H00FFFFFF" in out
