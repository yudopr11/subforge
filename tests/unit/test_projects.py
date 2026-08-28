import shutil
from pathlib import Path

import pytest

from subforge.app.projects import (
    create_project_from_audio,
    delete_project,
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


def test_create_from_audio_auto_converts_to_wav(tmp_path, monkeypatch):
    from unittest.mock import patch

    src_mp3 = tmp_path / "song.mp3"
    src_mp3.write_bytes(b"fake-mp3-bytes")

    def fake_convert(audio_path: Path, out_path: Path) -> bool:
        out_path.write_bytes(b"RIFF-converted-16k-wav")
        return True

    with patch("subforge.app.projects.convert_to_16khz_wav", side_effect=fake_convert):
        d = create_project_from_audio(src_mp3, tmp_path / "projects")
        assert d.name == "song"
        wav_file = d / "audio" / "song.wav"
        assert wav_file.exists()
        assert wav_file.read_bytes() == b"RIFF-converted-16k-wav"



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


def test_discover_projects_lists_recent_first(tmp_path, audio):
    import os
    import time

    from subforge.app.projects import discover_projects

    root = tmp_path / "p"
    d1 = create_project_from_audio(audio, root)
    d2 = create_project_from_audio(audio, root)
    # ensure d2 directory has a newer mtime deterministically
    now = time.time()
    os.utime(d1, (now - 10, now - 10))
    os.utime(d2, (now + 10, now + 10))

    # a directory without project.json must be ignored
    stray = root / "not-a-project"
    stray.mkdir()

    found = discover_projects(root)
    assert d1 in found and d2 in found
    assert stray not in found
    # most recently modified project first
    assert found[0] == d2


def test_discover_projects_missing_root_is_empty(tmp_path):
    from subforge.app.projects import discover_projects

    assert discover_projects(tmp_path / "does-not-exist") == []


def test_delete_project_removes_directory(tmp_path: Path):
    proj_dir = tmp_path / "TestProject"
    proj_dir.mkdir()
    (proj_dir / "project.json").write_text("{}")
    (proj_dir / "audio.wav").write_text("wav")

    assert proj_dir.exists() is True
    deleted = delete_project(proj_dir)
    assert deleted is True
    assert proj_dir.exists() is False


def test_delete_invalid_project_returns_false(tmp_path: Path):
    assert delete_project(tmp_path / "Nonexistent") is False

