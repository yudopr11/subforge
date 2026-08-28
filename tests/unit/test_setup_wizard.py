"""First-run setup wizard tests: transcribe model + language → main menu."""

from pathlib import Path

import pytest

from subforge.config.app_config import load_app_config
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.model_manager import ModelManagerScreen
from subforge.tui.screens.setup_wizard import FirstRunSetupScreen


def _wizard(app: SubForgeApp) -> FirstRunSetupScreen:
    """The wizard sits under whatever step-modal is currently on top."""
    for screen in reversed(list(app.screen_stack)):
        if isinstance(screen, FirstRunSetupScreen):
            return screen
    raise AssertionError("wizard not on stack")


def _pick(screen: object, prompt: str) -> None:
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable, Input

    from subforge.tui.screens.language_picker import LanguagePickerScreen

    if isinstance(screen, ModelManagerScreen):
        table = screen.query_one(DataTable)
        target_id = prompt.split(" · ")[0].strip()
        for idx, row in enumerate(screen._rows):
            if row.id == target_id:
                table.cursor_coordinate = Coordinate(idx, 0)
                break
        screen.select_or_install()
    elif isinstance(screen, LanguagePickerScreen):
        field = screen.query_one(Input)
        field.value = prompt
        screen.on_input_submitted(type("Evt", (), {"input": field})())
    else:
        raise TypeError(f"no driver for {type(screen).__name__}")


@pytest.fixture()
def first_run_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from subforge.app.model_manager import GGML_WHISPER_MODELS

    monkeypatch.setenv("SUBFORGE_HOME", str(tmp_path))
    config_path = tmp_path / "fresh.json"
    monkeypatch.setenv("SUBFORGE_CONFIG", str(config_path))
    config_path.unlink(missing_ok=True)

    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    for model_meta in GGML_WHISPER_MODELS.values():
        (models_dir / model_meta["filename"]).write_bytes(b"dummy-model-data")

    return config_path


async def test_guided_flow_transcription_then_saves(first_run_env: Path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)
        assert wizard is not None

        _pick(app.screen, "small")
        await pilot.pause()

        _pick(app.screen, "en")
        await pilot.pause()

        cfg = load_app_config(first_run_env)
        assert cfg.transcription.model == "small"
        assert cfg.transcription.language == "en"
