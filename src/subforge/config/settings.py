"""Layered configuration: defaults < .env file < environment variables (ARCH §24).

Env-var names follow ``<GROUP>_<FIELD>`` (e.g. ``TRANSLATION_BASE_URL``). We
apply them explicitly instead of using pydantic-settings' nested-delimiter
magic, which breaks on field names that themselves contain underscores.
"""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class TranscriptionSettings(BaseModel):
    provider: str = "local"
    model: str = "large-v3"
    device: str = "auto"
    compute_type: str = "auto"


class Settings(BaseModel):
    transcription: TranscriptionSettings = TranscriptionSettings()


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser (no interpolation), matching .env semantics."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            values[key] = value
    return values


def _coerce(model: type[BaseModel], key: str, raw: str) -> Any:
    annotation = model.model_fields[key].annotation
    if annotation is bool:
        return _parse_bool(raw)
    if annotation is int:
        return int(raw)
    return raw


def load_settings(env_file: Path | str | None = ".env") -> Settings:
    file_values = _parse_dotenv(Path(env_file)) if env_file is not None and Path(env_file).exists() else {}
    settings = Settings()
    for group_name, group_model in (
        ("transcription", TranscriptionSettings),
    ):
        updates: dict[str, Any] = {}
        for field_name in group_model.model_fields:
            env_key = f"{group_name}_{field_name}".upper()
            if env_key in os.environ:
                updates[field_name] = _coerce(group_model, field_name, os.environ[env_key])
            elif env_key in file_values:
                updates[field_name] = _coerce(group_model, field_name, file_values[env_key])
        if updates:
            setattr(settings, group_name, group_model(**updates))
    return settings
