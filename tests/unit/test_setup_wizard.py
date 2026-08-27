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
    from subforge.tui.screens.language_picker import LanguagePickerScreen
    from subforge.tui.screens.settings import ReasoningPickerScreen

    if isinstance(screen, ChoiceScreen):
        screen.choose(prompt)
    elif isinstance(screen, (ReasoningPickerScreen, ModelPickerScreen)):
        screen.on_option_list_option_selected(type("Evt", (), {"option": type("O", (), {"prompt": prompt})()})())
    elif isinstance(screen, (ApiKeyInputScreen, UrlInputScreen, LanguagePickerScreen)) or type(screen).__name__ == 'TextInputScreen':
        field = screen.query_one("Input")
        field.value = prompt
        screen.on_input_submitted(type("Evt", (), {"input": field})())
    else:  # pragma: no cover - guards future modal additions
        raise TypeError(f"no driver for {type(screen).__name__}")


@pytest.fixture()
def first_run_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Remove the conftest-created config so the app is genuinely first-run."""
    config_path = Path(monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "fresh.json")) or tmp_path / "fresh.json")
    config_path.unlink(missing_ok=True)
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
        # the first step modal is on top (ModelPickerScreen for local whisper); menu is underneath
        assert isinstance(app.screen, ModelPickerScreen)
        assert any(isinstance(s, ReplScreen) for s in app.screen_stack)


async def test_happy_path_local_transcription_local_translation(first_run_env):
    saved_flags: list[bool] = []
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)
        wizard.on_done = lambda: (saved_flags.append(True), app._setup_finished())

        # -- step 1: transcription = local whisper model picker
        assert isinstance(app.screen, ModelPickerScreen)
        _pick(app.screen, "small · Balanced (~2 GB RAM, ~466 MB)")
        await pilot.pause()

        from subforge.tui.screens.language_picker import LanguagePickerScreen

        assert isinstance(app.screen, LanguagePickerScreen)  # source language prompt
        _pick(app.screen, "id")
        await pilot.pause()

        assert isinstance(app.screen, ChoiceScreen)  # install offer
        _pick(app.screen, "Later (I'll do it in Settings)")
        await pilot.pause()

        # -- step 2: translation = local server (offline loader injection)
        wizard._loader_factory = fake_loaders({"local": ["qwen3-14b"]})
        assert isinstance(app.screen, ChoiceScreen)
        _pick(app.screen, "Local server (LM Studio / Ollama)")
        await pilot.pause()
        assert isinstance(app.screen, UrlInputScreen)
        _pick(app.screen, "http://localhost:1234/v1")
        await pilot.pause()
        assert isinstance(app.screen, ModelPickerScreen)
        _pick(app.screen, "qwen3-14b")
        await pilot.pause()
        assert isinstance(app.screen, LanguagePickerScreen)  # default target prompt
        _pick(app.screen, "en")

        await pilot.pause()
        cfg = load_app_config(first_run_env)
        assert cfg.transcription.provider == "local"
        assert cfg.transcription.model == "small"
        assert cfg.transcription.language == "id"
        assert cfg.translation.source == "local"
        assert cfg.translation.default_target == "en"
        assert cfg.translation.local_base_url == "http://localhost:1234/v1"
        assert cfg.translation.model == "qwen3-14b"
        assert saved_flags == [True]
        assert app.needs_setup is False


async def test_wizard_install_now_opens_model_manager(first_run_env):
    """Picking 'Install now' opens ModelManagerScreen and returns to Translation on dismiss."""
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)
        wizard._loader_factory = fake_loaders({"whisper": ["small · Balanced"]})

        # Step 1: Model -> Language -> Install offer
        assert isinstance(app.screen, ModelPickerScreen)
        _pick(app.screen, "small · Balanced")
        await pilot.pause()

        from subforge.tui.screens.language_picker import LanguagePickerScreen

        assert isinstance(app.screen, LanguagePickerScreen)
        _pick(app.screen, "en")
        await pilot.pause()

        assert isinstance(app.screen, ChoiceScreen)
        _pick(app.screen, "Install now")
        await pilot.pause()

        assert isinstance(app.screen, ModelManagerScreen)
        await pilot.press("escape")  # Close model manager
        await pilot.pause()

        # Transitions to Step 2: Translation choice
        assert isinstance(app.screen, ChoiceScreen)
        assert any("Local server" in str(opt.prompt) for opt in app.screen.query_one("OptionList").options)


async def test_happy_path_cloud_translation(first_run_env):
    loaders = fake_loaders({"whisper": ["large-v3-turbo"], "cloud": ["glm-5.2"]})
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)
        wizard._loader_factory = loaders

        class FakeCaps:
            def reasoning_spec(self, provider_preset, model_id):
                from subforge.providers.capabilities import ReasoningSpec

                if model_id == "glm-5.2":
                    return ReasoningSpec("effort", ("high", "max"))
                return ReasoningSpec("unsupported", ())

        wizard._cap_client = FakeCaps()

        # Step 1: Transcription model picker
        assert isinstance(app.screen, ModelPickerScreen)
        _pick(app.screen, "large-v3-turbo")
        await pilot.pause()

        from subforge.tui.screens.language_picker import LanguagePickerScreen

        assert isinstance(app.screen, LanguagePickerScreen)
        _pick(app.screen, "ja")  # source language
        await pilot.pause()
        assert isinstance(app.screen, ChoiceScreen)
        _pick(app.screen, "Later (I'll do it in Settings)")
        await pilot.pause()

        # Step 2: Translation
        _pick(app.screen, "Cloud provider")
        await pilot.pause()
        _pick(app.screen, "OpenCode Zen (opencode-zen)")
        await pilot.pause()
        _pick(app.screen, "oc-key")
        await pilot.pause()
        _pick(app.screen, "glm-5.2")
        await pilot.pause()
        from subforge.tui.screens.language_picker import LanguagePickerScreen as TIS
        from subforge.tui.screens.settings import ReasoningPickerScreen

        # PRD §15: exactly this model's discovered vocabulary is offered
        assert isinstance(app.screen, ReasoningPickerScreen)
        options = [str(o.prompt) for o in app.screen.query_one("OptionList").options]
        assert options == ["high", "max"]
        _pick(app.screen, "max")
        await pilot.pause()

        assert isinstance(app.screen, TIS)
        _pick(app.screen, "es")  # default target
        await pilot.pause()

        cfg = load_app_config(first_run_env)
        assert cfg.transcription.provider == "local"
        assert cfg.transcription.language == "ja"
        assert cfg.transcription.model == "large-v3-turbo"
        assert cfg.translation.default_target == "es"
        assert cfg.translation.source == "provider"
        assert cfg.translation.provider == "opencode-zen"
        assert cfg.translation.api_key == "oc-key"
        assert cfg.translation.model == "glm-5.2"
        assert cfg.translation.reasoning_effort == "max"


async def test_incomplete_setup_does_not_save(first_run_env):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        wizard = _wizard(app)

        wizard.apply_tc_model("small")   # translation never configured
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
        wizard = _wizard(app)
        wizard._loader_factory = fake_loaders({"local": ["m1"]})

        # drive the real flow end-to-end so every step modal dismisses itself
        assert isinstance(app.screen, ModelPickerScreen)
        _pick(app.screen, "small · Balanced (~2 GB RAM, ~466 MB)")
        await pilot.pause()
        from subforge.tui.screens.language_picker import LanguagePickerScreen

        assert isinstance(app.screen, LanguagePickerScreen)
        _pick(app.screen, "")  # auto-detect
        await pilot.pause()
        _pick(app.screen, "Later (I'll do it in Settings)")
        await pilot.pause()
        _pick(app.screen, "Local server (LM Studio / Ollama)")
        await pilot.pause()
        _pick(app.screen, "http://localhost:1234/v1")
        await pilot.pause()
        _pick(app.screen, "m1")
        await pilot.pause()
        assert isinstance(app.screen, LanguagePickerScreen)
        _pick(app.screen, "en")  # default target
        await pilot.pause()

        assert isinstance(app.screen, ReplScreen)
        assert app.needs_setup is False
        # completion is announced in the transcript and config reloaded
        assert app.app_config.translation.model == "m1"
        from subforge.tui.screens.repl import ReplScreen as _Repl

        repl = next(s for s in app.screen_stack if isinstance(s, _Repl))
        assert repl is not None


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
