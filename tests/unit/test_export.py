from pathlib import Path

import pytest

from subforge.app.export import export_subtitles
from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment, StageState


def seeded(tmp_path: Path) -> Path:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    project = load_project(d)
    project.segments = [
        Segment(id=1, start=1.2, end=3.4, source="Halo!"),
        Segment(id=2, start=3.5, end=6.8, source="Dada."),
    ]
    save_project(d, project)
    return d


def test_exports_source_srt(tmp_path):
    d = seeded(tmp_path)
    written = export_subtitles(d, formats=["srt"])
    names = {p.name for p in written}
    assert names == {"source.srt"}
    assert "Halo!" in (d / "exports" / "source.srt").read_text()
    assert load_project(d).get_stage("export") is StageState.COMPLETED


def test_export_ass(tmp_path):
    d = seeded(tmp_path)
    export_subtitles(d, formats=["ass"])
    content = (d / "exports" / "source.ass").read_text()
    assert "[Script Info]" in content
    assert "Halo!" in content


def test_export_to_custom_output_dir_with_project_name(tmp_path):
    d = seeded(tmp_path)
    out_dir = tmp_path / "custom_out"
    written = export_subtitles(d, formats=["srt", "ass"], output_dir=out_dir)
    names = {p.name for p in written}
    assert names == {"p.srt", "p.ass"}
    assert (out_dir / "p.srt").exists()
    assert (out_dir / "p.ass").exists()
    # Internal exports still exist
    assert (d / "exports" / "source.srt").exists()
    assert (d / "exports" / "source.ass").exists()


def test_unknown_format_raises(tmp_path):
    d = seeded(tmp_path)
    with pytest.raises(ValueError, match="unsupported export format"):
        export_subtitles(d, formats=["vtt"])
