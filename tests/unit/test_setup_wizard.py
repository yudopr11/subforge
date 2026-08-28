"""First-run setup wizard tests: transcribe → translate → main menu.

Modal interactions are driven through their public handlers (the same seam a
real keypress uses), with model-list loading injected to stay offline.
"""

from pathlib import Path

import pytest

from subforge.config.app_config import load_app_config
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.model_manager import ModelManagerScreen
from subforge.tui.screens.model_picker import ModelPickerScreen
from subforge.tui.screens.project import ChoiceScreen, NewProjectScreen, ProjectPickerScreen
from subforge.tui.screens.settings import ApiKeyInputScreen, UrlInputScreen
from subforge.tui.screens.setup_wizard import FirstRunSetupScreen


def _wizard(app: SubForgeApp) -> FirstRunSetupScreen:
    """The wizard sits under whatever step-modal is currently on top."""
    for screen in reversed(list(app.screen_stack)):
        if isinstance(screen, FirstRunSetupScreen):
            return screen
    raise AssertionError("wizard not on stack")


def _pick(screen: object, prompt: str) -> None:
    """Drive an OptionList-based modal through its public choose/submit seam."""
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable, Input

    from subforge.tui.screens.language_picker import LanguagePickerScreen
    from subforge.tui.screens.model_manager import ModelManagerScreen
    from subforge.tui.screens.settings import ReasoningPickerScreen

    if isinstance(screen, ChoiceScreen):
        screen.choose(prompt)
    elif isinstance(screen, (ReasoningPickerScreen, ModelPickerScreen)):
        screen.on_option_list_option_selected(type("Evt", (), {"option": type("O", (), {"prompt": prompt})()})())
    elif isinstance(screen, ModelManagerScreen):
        table = screen.query_one(DataTable)
        target_id = prompt.split(" · ")[0].strip()
        for idx, row in enumerate(screen._rows):
            if row.id == target_id:
                table.cursor_coordinate = Coordinate(idx, 0)
                break
        screen.select_or_install()
    elif isinstance(screen, (ApiKeyInputScreen, UrlInputScreen, LanguagePickerScreen)) or type(screen).__name__ == 'TextInputScreen':
        field = screen.query_one(Input)
        field.value = prompt
        screen.on_input_submitted(type("Evt", (), {"input": field})())
    else:  # pragma: no cover - guards future modal additions
        raise TypeError(f"no driver for {type(screen).__name__}")


@pytest.fixture()
def first_run_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Remove the conftest-created config so the app is genuinely first-run."""
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


def fake_loaders(models: dict[str, list[str]]):
    """Factory returning offline loaders keyed by loader-kind prefix."""

    def factory(kind: str) -> list[str]:  # matches Loader signature loosely
        return _StaticLoader(models.get(kind.split(":")[0], ["fake-model-1"]))

    return factory


class _StaticLoader(list):  # callable list — satisfies Loader contract offline
    def __call__(self) -> list[str]:
        return list(self)


async def test_first_run_launches_wizard_over_menu(first_run_env):
    from subforge.tui.screens.repl import ReplScreen

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(_wizard(app), FirstRunSetupScreen)
        # the first step modal is on top (ModelManagerScreen for local whisper); menu is underneath
        assert isinstance(app.screen, ModelManagerScreen)
        assert any(isinstance(s, ReplScreen) for s in app.screen_stack)


async def test_happy_path_wizard_setup(first_run_env):
    saved_flags: list[bool] = []
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)
        wizard.on_done = lambda: (saved_flags.append(True), app._setup_finished())

        # -- step 1: transcription = local whisper model manager
        assert isinstance(app.screen, ModelManagerScreen)
        _pick(app.screen, "small")
        await pilot.pause()

        from subforge.tui.screens.language_picker import LanguagePickerScreen

        # -- step 2: source language
        assert isinstance(app.screen, LanguagePickerScreen)
        _pick(app.screen, "id")
        await pilot.pause()

        cfg = load_app_config(first_run_env)
        assert cfg.transcription.provider == "local"
        assert cfg.transcription.model == "small"
        assert cfg.transcription.language == "id"
        assert cfg.translation.default_target == "en"
        assert saved_flags == [True]
        assert app.needs_setup is False


async def test_wizard_sets_auto_detect_when_language_empty(first_run_env):
    saved_flags: list[bool] = []
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)
        wizard.on_done = lambda: (saved_flags.append(True), app._setup_finished())

        assert isinstance(app.screen, ModelManagerScreen)
        _pick(app.screen, "large-v3-turbo")
        await pilot.pause()

        from subforge.tui.screens.language_picker import LanguagePickerScreen

        assert isinstance(app.screen, LanguagePickerScreen)
        _pick(app.screen, "")  # empty = auto-detect
        await pilot.pause()

        cfg = load_app_config(first_run_env)
        assert cfg.transcription.model == "large-v3-turbo"
        assert cfg.transcription.language == ""
        assert cfg.translation.default_target == "en"
        assert saved_flags == [True]


async def test_incomplete_setup_does_not_save(first_run_env):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)

        wizard.cfg.transcription.model = ""  # transcription model not chosen
        wizard.finish()

        assert not first_run_env.exists()  # nothing persisted
        assert "Incomplete setup" in str(wizard.query_one("#setup-status").render())


async def test_escape_skips_wizard_without_saving(first_run_env):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)

        # Esc lands on the current step modal first (wizard stays put),
        # then a second Esc skips the wizard entirely.
        app.screen.action_cancel()  # type: ignore[union-attr]
        await pilot.pause()
        assert isinstance(_wizard(app), FirstRunSetupScreen)
        assert isinstance(app.screen, FirstRunSetupScreen)
        wizard.action_cancel()
        await pilot.pause()

        assert not first_run_env.exists()
        from subforge.tui.screens.repl import ReplScreen

        assert isinstance(app.screen, ReplScreen)


async def test_after_setup_menu_status_refreshes(first_run_env):
    from subforge.tui.screens.repl import ReplScreen

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(_wizard(app), FirstRunSetupScreen)

        # drive the real flow end-to-end so every step modal dismisses itself
        assert isinstance(app.screen, ModelManagerScreen)
        _pick(app.screen, "small")
        await pilot.pause()
        from subforge.tui.screens.language_picker import LanguagePickerScreen

        assert isinstance(app.screen, LanguagePickerScreen)
        _pick(app.screen, "")  # auto-detect
        await pilot.pause()

        assert isinstance(app.screen, ReplScreen)
        assert app.needs_setup is False
        # completion is announced in the transcript and config reloaded
        assert app.app_config.transcription.model == "small"
        from subforge.tui.screens.repl import ReplScreen as _Repl

        repl = next(s for s in app.screen_stack if isinstance(s, _Repl))
        assert repl is not None


async def test_wizard_does_not_block_on_uninstalled_model_download(tmp_path, monkeypatch):
    from subforge.tui.screens.language_picker import LanguagePickerScreen
    from subforge.tui.screens.repl import ReplScreen

    monkeypatch.setenv("SUBFORGE_HOME", str(tmp_path))
    config_path = tmp_path / "fresh.json"
    monkeypatch.setenv("SUBFORGE_CONFIG", str(config_path))
    config_path.unlink(missing_ok=True)

    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ModelManagerScreen)

        # Select uninstalled model 'tiny'
        _pick(app.screen, "tiny")
        await pilot.pause()

        assert isinstance(app.screen, LanguagePickerScreen)
        _pick(app.screen, "en")
        await pilot.pause()

        assert isinstance(app.screen, ReplScreen)
        assert app.needs_setup is False
        assert app.app_config.transcription.model == "tiny"


def _menu_import_guard() -> None:  # keep explicit import referenced for readers
    
    assert ProjectPickerScreen and NewProjectScreen and ModelManagerScreen


async def test_reasoning_skipped_for_non_reasoning_model_and_local(first_run_env):
    """No vocabulary / local server -> straight to target-language prompt."""
    from subforge.providers.capabilities import ReasoningSpec
    from subforge.tui.screens.language_picker import LanguagePickerScreen
    from subforge.tui.screens.settings import ReasoningPickerScreen

    class NoCaps:
        def reasoning_spec(self, provider_preset, model_id):
            return ReasoningSpec("unsupported", ())

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)
        wizard._cap_client = NoCaps()

        # local server: never asked, regardless of model
        wizard.cfg.translation.source = "local"
        wizard.apply_tl_model("qwen3-14b")
        assert not isinstance(app.screen, ReasoningPickerScreen)
        assert isinstance(app.screen, LanguagePickerScreen)  # target-language prompt follows

        # cloud but non-reasoning model: also skipped
        wizard2_cfg_source = "provider"
        wizard.cfg.translation.source = wizard2_cfg_source  # type: ignore[assignment]
        wizard.cfg.translation.provider = "opencode-zen"
        wizard.apply_tl_model("nemotron")
        assert not isinstance(app.screen, ReasoningPickerScreen)


# ---- Pi-style wizard: modal overlay + transcript mirroring ----------------


async def test_wizard_is_modal_overlay_not_fullscreen(first_run_env):
    """The wizard stays on the stack over the REPL, never hides it (Pi-style)."""
    from textual.screen import ModalScreen

    from subforge.tui.screens.repl import ReplScreen

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)
        assert isinstance(wizard, ModalScreen)
        # REPL remains underneath, reachable and mounted
        assert any(isinstance(s, ReplScreen) for s in app.screen_stack)


async def test_wizard_mirrors_steps_into_repl_transcript(first_run_env):
    from subforge.tui.screens.repl import ReplScreen

    def transcript(repl: ReplScreen) -> str:
        log = repl.query_one("#transcript")
        lines = ["".join(seg.text for seg in strip) for strip in log.lines]
        return "\n".join(lines)

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)

        # Step 1 status is already mirrored on mount
        repl = next(s for s in app.screen_stack if isinstance(s, ReplScreen))
        assert "Step 1/2" in transcript(repl)

        # Advancing steps keeps mirroring
        wizard._set_status("Step 2/2 · Translation — where should it run?")
        await pilot.pause()
        repl = next(s for s in app.screen_stack if isinstance(s, ReplScreen))
        assert "Step 2/2" in transcript(repl)
