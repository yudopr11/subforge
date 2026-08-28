"""App-level configuration typed by the user in the TUI.

Primary configuration path: NO .env step for creators. Config is managed in the
Setup Wizard, Model Manager, and Language pickers. File holds configuration — atomic
writes and 0600 permissions are mandatory. Never commit, never log contents.
"""

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from subforge.app.storage import get_config_path


class TranscriptionConfig(BaseModel):
    provider: Literal["local"] = "local"
    model: str = ""  # empty until selected in Setup Wizard or /models
    language: str = ""  # audio source language ("": auto-detect)
    binary_path: str = ""  # optional custom path to whisper-cli
    models_dir: str = ""  # optional custom models directory


class AppConfig(BaseModel):
    transcription: TranscriptionConfig = TranscriptionConfig()


def default_config_path() -> Path:
    return get_config_path()


def save_app_config(config: AppConfig, path: Path | None = None) -> Path:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, target)
    if os.name == "posix":
        os.chmod(target, 0o600)
    return target


def load_app_config(path: Path | None = None) -> AppConfig:
    target = path or default_config_path()
    if not target.exists():
        return AppConfig()
    try:
        return AppConfig.model_validate_json(target.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"[WARN] Ignoring corrupt config file {target}: {exc}", file=sys.stderr)
        return AppConfig()


def is_first_run(path: Path | None = None) -> bool:
    """True when no config has been saved yet — drives the setup wizard."""
    target = path or default_config_path()
    return not target.exists()
