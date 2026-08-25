from pathlib import Path

import pytest

from subforge.app.export import export_subtitles
from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment, StageState


def seeded(tmp_path: Path) -> Path:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id", target_languages=["en"]))
    project = load_project(d)
    project.segments = [
        Segment(id=1, start=1.2, end=3.4, source="Halo!", translations={"en": "Hello!"}),
        Segment(id=2, start=3.5, end=6.8, source="Dada.", translations={"en": "Bye."}),
    ]
    save_project(d, project)
    return d


def test_exports_source_and_translation_srt(tmp_path):
    d = seeded(tmp_path)
    written = export_subtitles(d, formats=["srt"], languages=["en"])
    names = {p.name for p in written}
    assert names == {"source.srt", "en.srt"}
    assert "Halo!" in (d / "exports" / "source.srt").read_text()
    assert "Hello!" in (d / "exports" / "en.srt").read_text()
    assert load_project(d).get_stage("export") is StageState.COMPLETED


def test_export_ass(tmp_path):
    d = seeded(tmp_path)
    export_subtitles(d, formats=["ass"], languages=["en"])
    content = (d / "exports" / "en.ass").read_text()
    assert "[Script Info]" in content
    assert "Hello!" in content


def test_skips_incomplete_language(tmp_path):
    d = seeded(tmp_path)
    project = load_project(d)
    project.segments[1].translations.pop("en")  # partial translation
    save_project(d, project)
    written = export_subtitles(d, formats=["srt"], languages=["en"])
    assert [p.name for p in written] == ["source.srt"]


def test_unknown_format_raises(tmp_path):
    d = seeded(tmp_path)
    with pytest.raises(ValueError, match="unsupported export format"):
        export_subtitles(d, formats=["vtt"], languages=[])
