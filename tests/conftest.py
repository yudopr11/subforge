"""Shared fixtures: isolate app config per-test so the first-run wizard
doesn't cover the main menu in unrelated UI tests."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_app_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point SUBFORGE_CONFIG at an existing (empty-defaults) config file."""
    config_path = tmp_path / "config.json"
    config_path.write_text("{}")  # validates to default AppConfig
    monkeypatch.setenv("SUBFORGE_CONFIG", str(config_path))
    return config_path
