"""Project-level helpers used by the TUI: create from audio, discover audio.

File-management glue lives here (not in screens) so the TUI stays logic-free
(ARCH §3.1) and the behavior is unit-testable offline.
"""

import shutil
from pathlib import Path

from subforge.app.project_store import create_project
from subforge.models.project import ProjectMeta

AUDIO_SUFFIXES = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus"}


def projects_root() -> Path:
    """Directory under which new projects are created (override for tests)."""
    import os

    return Path(os.environ.get("SUBFORGE_PROJECTS_DIR", "projects"))


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_SUFFIXES


def unique_project_dir(root: Path, base_name: str) -> Path:
    """First non-existing `<root>/<base>`; appends -2, -3, … on collisions."""
    candidate = root / base_name
    n = 2
    while candidate.exists():
        candidate = root / f"{base_name}-{n}"
        n += 1
    return candidate


def create_project_from_audio(audio_path: Path, root: Path | None = None) -> Path:
    """Create a new project around an audio file and copy the audio into it."""
    if not audio_path.is_file():
        raise ValueError(f"[ERROR] audio file not found: {audio_path}")
    if not is_audio_file(audio_path):
        raise ValueError(f"[ERROR] unsupported audio format: {audio_path.suffix or '(none)'}")

    target_root = root if root is not None else projects_root()
    directory = unique_project_dir(target_root, audio_path.stem)
    meta = ProjectMeta(name=directory.name, source_language="", target_languages=["en"])
    create_project(directory, meta)
    shutil.copy2(audio_path, directory / "audio" / audio_path.name)
    return directory


def find_audio_file(project_dir: Path) -> Path | None:
    """The project's imported audio (MVP: one file per project)."""
    audio_dir = project_dir / "audio"
    if not audio_dir.is_dir():
        return None
    for candidate in sorted(audio_dir.iterdir()):
        if candidate.is_file() and is_audio_file(candidate):
            return candidate
    return None
