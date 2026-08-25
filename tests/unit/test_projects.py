import shutil
from pathlib import Path

import pytest

from subforge.app.projects import (
    create_project_from_audio,
    find_audio_file,
    is_audio_file,
    unique_project_dir,
)


@pytest.fixture()
def audio(tmp_path: Path) -> Path:
    src = tmp_path / "somewhere" / "my_podcast_ep12.wav"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"RIFF-fake")
    return src


def test_create_from_audio_copies_into_layout(tmp_path, audio):
    d = create_project_from_audio(audio, tmp_path / "projects")
    assert d.name == "my_podcast_ep12"
    assert (d / "project.json").exists()
    copied = d / "audio" / "my_podcast_ep12.wav"
    assert copied.read_bytes() == b"RIFF-fake"


def test_collisions_get_numbered_suffixes(tmp_path, audio):
    first = create_project_from_audio(audio, tmp_path / "p")
    second = create_project_from_audio(audio, tmp_path / "p")
    assert first.name == "my_podcast_ep12"
    assert second.name == "my_podcast_ep12-2"


def test_rejects_missing_or_non_audio(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        create_project_from_audio(tmp_path / "nope.wav", tmp_path)
    txt = tmp_path / "notes.txt"
    txt.write_text("hi")
    with pytest.raises(ValueError, match="unsupported audio"):
        create_project_from_audio(txt, tmp_path)


def test_find_audio_file_roundtrip(tmp_path, audio):
    d = create_project_from_audio(audio, tmp_path / "p")
    assert find_audio_file(d) == d / "audio" / "my_podcast_ep12.wav"
    assert find_audio_file(tmp_path / "empty-project") is None


def test_is_audio_file():
    assert is_audio_file(Path("a.WAV"))
    assert is_audio_file(Path("a.flac"))
    assert not is_audio_file(Path("a.txt"))
    assert not is_audio_file(Path("noext"))


def _unused(p: Path) -> bool:  # keep shutil referenced if linters change scope
    return p.exists() and shutil is not None and bool(unique_project_dir(p, "x"))
