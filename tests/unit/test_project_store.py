import json

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment, StageState


def test_create_makes_layout(tmp_path):
    directory = create_project(tmp_path / "yt-001", ProjectMeta(name="yt-001", source_language="id"))
    assert (directory / "project.json").exists()
    for sub in ("audio", "transcripts", "translations", "exports"):
        assert (directory / sub).is_dir()


def test_save_load_roundtrip(tmp_path):
    directory = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    loaded = load_project(directory)
    loaded.set_stage("transcription", StageState.COMPLETED)
    loaded.segments.append(Segment(id=1, start=1.0, end=2.0, source="hai"))
    save_project(directory, loaded)

    raw = json.loads((directory / "project.json").read_text())
    assert raw["segments"][0]["start"] == 1.0  # floats, not formatted strings
    reloaded = load_project(directory)
    assert reloaded.get_stage("transcription") is StageState.COMPLETED
    assert reloaded.segments[0].source == "hai"
