from pathlib import Path
from unittest.mock import patch

import pytest

from subforge.app.storage import (
    get_bin_dir,
    get_config_path,
    get_models_dir,
    get_projects_dir,
    get_subforge_dir,
    migrate_legacy_projects,
)


def test_storage_paths_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUBFORGE_CONFIG", raising=False)
    monkeypatch.delenv("SUBFORGE_PROJECTS_DIR", raising=False)
    monkeypatch.delenv("SUBFORGE_BIN_DIR", raising=False)
    monkeypatch.delenv("SUBFORGE_MODELS_DIR", raising=False)
    custom = tmp_path / "custom_subforge"
    monkeypatch.setenv("SUBFORGE_HOME", str(custom))

    assert get_subforge_dir() == custom
    assert get_config_path() == custom / "config.json"
    assert get_bin_dir() == custom / "bin"
    assert get_models_dir() == custom / "models"
    assert get_projects_dir() == custom / "projects"


def test_storage_paths_windows_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUBFORGE_HOME", raising=False)
    monkeypatch.delenv("SUBFORGE_CONFIG", raising=False)
    monkeypatch.delenv("SUBFORGE_PROJECTS_DIR", raising=False)
    monkeypatch.delenv("SUBFORGE_BIN_DIR", raising=False)
    monkeypatch.delenv("SUBFORGE_MODELS_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\test\\AppData\\Local")

    with patch("os.name", "nt"):
        assert get_subforge_dir() == Path("C:\\Users\\test\\AppData\\Local\\subforge")
        assert get_config_path() == Path("C:\\Users\\test\\AppData\\Local\\subforge\\config.json")
        assert get_projects_dir() == Path("C:\\Users\\test\\AppData\\Local\\subforge\\projects")
        assert get_bin_dir() == Path("C:\\Users\\test\\AppData\\Local\\subforge\\bin")
        assert get_models_dir() == Path("C:\\Users\\test\\AppData\\Local\\subforge\\models")


def test_storage_paths_posix_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUBFORGE_HOME", raising=False)
    monkeypatch.delenv("SUBFORGE_CONFIG", raising=False)
    monkeypatch.delenv("SUBFORGE_PROJECTS_DIR", raising=False)
    monkeypatch.delenv("SUBFORGE_BIN_DIR", raising=False)
    monkeypatch.delenv("SUBFORGE_MODELS_DIR", raising=False)
    fake_home = Path("/home/testuser")

    with patch("os.name", "posix"), patch("pathlib.Path.home", return_value=fake_home):
        assert get_subforge_dir() == fake_home / ".local" / "share" / "subforge"
        assert get_config_path() == fake_home / ".config" / "subforge" / "config.json"
        assert get_projects_dir() == fake_home / ".local" / "share" / "subforge" / "projects"
        assert get_bin_dir() == fake_home / ".local" / "share" / "subforge" / "bin"
        assert get_models_dir() == fake_home / ".local" / "share" / "subforge" / "models"


def test_migrate_legacy_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target_projects = tmp_path / "target_projects"
    legacy_dir = tmp_path / "repo_projects"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "ProjectA").mkdir()
    (legacy_dir / "ProjectA" / "project.json").write_text('{"name": "ProjectA"}', encoding="utf-8")

    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(target_projects))

    migrated = migrate_legacy_projects(source_dir=legacy_dir)
    assert len(migrated) == 1
    assert "ProjectA" in migrated
    assert (target_projects / "ProjectA" / "project.json").exists()


def test_migrate_legacy_projects_noop_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target_projects = tmp_path / "target_projects"
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(target_projects))
    migrated = migrate_legacy_projects(source_dir=tmp_path / "nonexistent")
    assert migrated == []
