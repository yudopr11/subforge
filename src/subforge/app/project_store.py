"""Filesystem persistence for projects. project.json is the source of truth (ARCH §21)."""

import os
from pathlib import Path

from subforge.models.project import Project, ProjectMeta

_PROJECT_FILE = "project.json"
_SUBDIRS = ("audio", "transcripts", "translations", "exports")


def create_project(directory: Path, meta: ProjectMeta) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for sub in _SUBDIRS:
        (directory / sub).mkdir(exist_ok=True)
    save_project(directory, Project(project=meta, segments=[]))
    return directory


def project_file(directory: Path) -> Path:
    return directory / _PROJECT_FILE


def save_project(directory: Path, project: Project) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = project_file(directory)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, target)  # atomic on POSIX and Windows
    return target


def load_project(directory: Path) -> Project:
    return Project.model_validate_json(project_file(directory).read_text(encoding="utf-8"))
