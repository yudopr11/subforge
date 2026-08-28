"""Project-level helpers used by the TUI: create from audio, discover audio.

File-management glue lives here (not in screens) so the TUI stays logic-free
(ARCH §3.1) and the behavior is unit-testable offline.
"""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from subforge.app.binaries import ensure_ffmpeg_binary, find_in_path_or_bin
from subforge.app.project_store import create_project
from subforge.app.storage import get_projects_dir
from subforge.models.project import ProjectMeta

AUDIO_SUFFIXES = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus"}


def projects_root() -> Path:
    """Directory under which new projects are created (override for tests)."""
    return get_projects_dir()


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


def convert_to_16khz_wav(audio_path: Path, out_path: Path) -> bool:
    """Convert audio to 16kHz 16-bit mono PCM WAV using ffmpeg."""
    try:
        ffmpeg_bin = str(find_in_path_or_bin("ffmpeg") or ensure_ffmpeg_binary())
    except Exception:  # noqa: BLE001
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(audio_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(out_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, check=False)
        return res.returncode == 0 and out_path.exists()
    except Exception:  # noqa: BLE001
        return False


def create_project_from_audio(audio_path: Path, root: Path | None = None) -> Path:
    """Create a new project around an audio file, converting/resampling to 16kHz WAV."""
    if not audio_path.is_file():
        raise ValueError(f"[ERROR] audio file not found: {audio_path}")
    if not is_audio_file(audio_path):
        raise ValueError(f"[ERROR] unsupported audio format: {audio_path.suffix or '(none)'}")

    target_root = root if root is not None else projects_root()
    directory = unique_project_dir(target_root, audio_path.stem)
    meta = ProjectMeta(name=directory.name, source_language="")
    create_project(directory, meta)

    audio_dir = directory / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    target_wav = audio_dir / f"{audio_path.stem}.wav"

    converted = False
    try:
        converted = convert_to_16khz_wav(audio_path, target_wav)
    except Exception:  # noqa: BLE001
        converted = False

    if not converted or not target_wav.exists():
        shutil.copy2(audio_path, audio_dir / audio_path.name)

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


def delete_project(project_dir: Path) -> bool:
    """Permanently delete a project directory and its contents from disk."""
    if not project_dir.exists() or not project_dir.is_dir():
        return False
    try:
        shutil.rmtree(project_dir)
        return True
    except OSError:
        return False


def discover_projects(root: Path | None = None) -> list[Path]:
    """Existing projects under ``root`` (default: :func:`projects_root`).

    Only directories containing ``project.json`` count; most recently modified
    first so the picker feels 'recently used'.
    """
    base = root if root is not None else projects_root()
    if not base.is_dir():
        return []
    projects = [d for d in base.iterdir() if d.is_dir() and (d / "project.json").is_file()]
    return sorted(projects, key=lambda d: d.stat().st_mtime, reverse=True)


_JUNK_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"}


def discover_audio_files(
    root: Path | None = None,
    limit: int = 500,
    is_dir: Callable[[Path], bool] = lambda p: p.is_dir(),
) -> list[Path]:
    """Audio files under ``root`` (default: cwd), junk dirs pruned, newest first.

    Powers the ``@`` browse in the REPL's /new locate mode.
    """
    from collections import deque

    base = root if root is not None else Path.cwd()
    found: list[tuple[float, Path]] = []
    queue: deque[Path] = deque([base])
    while queue and len(found) < limit * 4:
        current = queue.popleft()
        try:
            children = sorted(current.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_symlink():
                continue
            if child.is_dir():
                if child.name not in _JUNK_DIRS:
                    queue.append(child)
            elif is_audio_file(child):
                try:
                    found.append((child.stat().st_mtime, child))
                except OSError:
                    continue
                if len(found) >= limit * 4:
                    break
    found.sort(key=lambda pair: pair[0], reverse=True)
    return [path for _, path in found[:limit]]
