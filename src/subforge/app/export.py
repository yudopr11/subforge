"""Export orchestration: canonical project -> SRT/ASS files (ARCH §18)."""

from pathlib import Path

from subforge.app.project_store import load_project, save_project
from subforge.models.project import StageState
from subforge.subtitles.ass import write_ass
from subforge.subtitles.srt import write_srt

_WRITERS = {"srt": write_srt, "ass": write_ass}


def export_subtitles(
    project_dir: Path,
    formats: list[str],
    output_dir: Path | None = None,
) -> list[Path]:
    for fmt in formats:
        if fmt not in _WRITERS:
            raise ValueError(f"[ERROR] unsupported export format: {fmt}")

    project = load_project(project_dir)
    exports = project_dir / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    proj_name = project.project.name or project_dir.name

    internal_written: list[Path] = []
    external_written: list[Path] = []

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    for fmt in formats:
        writer = _WRITERS[fmt]
        suffix = f".{fmt}"
        internal_written.append(writer(project.segments, exports / f"source{suffix}"))
        if output_dir is not None:
            external_written.append(writer(project.segments, output_dir / f"{proj_name}{suffix}"))

    project.set_stage("export", StageState.COMPLETED)
    save_project(project_dir, project)
    return external_written if output_dir is not None else internal_written
