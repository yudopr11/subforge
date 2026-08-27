"""Centralized storage and directory path resolver for SubForge.

Governs user configuration, downloaded GGML models, managed standalone binaries,
and subtitle project directories across Windows and POSIX (Linux/macOS) platforms.
"""

import os
import shutil
from pathlib import Path


def get_subforge_dir() -> Path:
    """Base directory for SubForge application data."""
    env = os.environ.get("SUBFORGE_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(app_data) / "subforge"
    return Path.home() / ".local" / "share" / "subforge"


def get_config_path() -> Path:
    """Path to the application config.json file."""
    env = os.environ.get("SUBFORGE_CONFIG")
    if env:
        return Path(env)
    home_env = os.environ.get("SUBFORGE_HOME")
    if home_env:
        return Path(home_env) / "config.json"
    if os.name == "nt":
        return get_subforge_dir() / "config.json"
    return Path.home() / ".config" / "subforge" / "config.json"


def get_bin_dir() -> Path:
    """Directory for standalone binaries (whisper-cli, ffmpeg)."""
    env = os.environ.get("SUBFORGE_BIN_DIR")
    if env:
        return Path(env)
    return get_subforge_dir() / "bin"


def get_models_dir() -> Path:
    """Directory for downloaded local GGML Whisper models."""
    env = os.environ.get("SUBFORGE_MODELS_DIR")
    if env:
        return Path(env)
    return get_subforge_dir() / "models"


def get_projects_dir() -> Path:
    """Root directory under which user projects are stored."""
    env = os.environ.get("SUBFORGE_PROJECTS_DIR")
    if env:
        return Path(env)
    return get_subforge_dir() / "projects"


def migrate_legacy_projects(source_dir: Path | None = None) -> list[str]:
    """Scan legacy repository projects directory and migrate projects to OS storage."""
    legacy = source_dir if source_dir is not None else Path("projects")
    if not legacy.exists() or not legacy.is_dir():
        return []
    target = get_projects_dir()
    target.mkdir(parents=True, exist_ok=True)
    migrated: list[str] = []
    for item in legacy.iterdir():
        if item.is_dir() and (item / "project.json").exists():
            dest = target / item.name
            if not dest.exists():
                shutil.copytree(item, dest)
                migrated.append(item.name)
    return migrated
