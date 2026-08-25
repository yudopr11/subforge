"""Export orchestration: canonical project -> SRT/ASS files (ARCH §18)."""

from pathlib import Path

from subforge.app.project_store import load_project, save_project
from subforge.models.project import Project, StageState
from subforge.subtitles.ass import write_ass
from subforge.subtitles.srt import write_srt

_WRITERS = {"srt": write_srt, "ass": write_ass}


def _complete(project: Project, language: str) -> bool:
    return bool(project.segments) and all(language in s.translations for s in project.segments)


def export_subtitles(project_dir: Path, formats: list[str], languages: list[str]) -> list[Path]:
    for fmt in formats:
        if fmt not in _WRITERS:
            raise ValueError(f"[ERROR] unsupported export format: {fmt}")

    project = load_project(project_dir)
    exports = project_dir / "exports"
    written: list[Path] = []
    for fmt in formats:
        writer = _WRITERS[fmt]
        suffix = f".{fmt}"
        written.append(writer(project.segments, exports / f"source{suffix}"))
        for lang in languages:
            if _complete(project, lang):
                written.append(writer(project.segments, exports / f"{lang}{suffix}", language=lang))

    project.set_stage("export", StageState.COMPLETED)
    save_project(project_dir, project)
    return written
