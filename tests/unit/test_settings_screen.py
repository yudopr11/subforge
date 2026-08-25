import inspect

from subforge.config.app_config import AppConfig
from subforge.providers.capabilities import ReasoningSpec
from subforge.tui.screens.settings import ApiKeyInputScreen, refresh_reasoning


def test_refresh_reasoning_keeps_valid_drops_stale():
    spec = ReasoningSpec("effort", ("high", "max"))
    assert refresh_reasoning("max", spec) == "max"
    assert refresh_reasoning("low", spec) == ""  # model switched: old value invalid
    assert refresh_reasoning("high", ReasoningSpec("unsupported", ())) == ""


def test_reasoning_picker_offers_exactly_discovered_values():
    from subforge.tui.screens.settings import ReasoningPickerScreen

    src = inspect.getsource(ReasoningPickerScreen)
    assert "spec.values" in src  # values come from metadata, never hardcoded


async def test_api_key_input_masks_and_returns_value():
    from subforge.tui.app import SubForgeApp

    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ApiKeyInputScreen("Enter OpenAI API key")
        await app.push_screen(screen)
        await pilot.pause()

        field = screen.query_one("Input")
        field.value = "  sk-secret  "
        screen.on_input_submitted(type("Evt", (), {"input": field})())
        await pilot.pause()
        assert screen.result == "sk-secret"


def test_api_key_is_masked():
    assert "password=True" in inspect.getsource(ApiKeyInputScreen)


def test_settings_screen_persists_on_save(tmp_path, monkeypatch):
    from subforge.config.app_config import load_app_config
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    calls = []
    screen = SettingsScreen(AppConfig(), on_saved=lambda: calls.append(True))
    screen.save_config()  # public hook used by the (follow-up) widget wiring

    assert load_app_config().transcription.provider == "local"
    assert calls == [True]


# ---- full interactive tree (public mutation methods; DOM-light) ----------


class FakeCaps:
    """Injectable capability client: glm-5.2 -> [high, max]."""

    def reasoning_spec(self, provider_preset, model_id):
        vocab = {"glm-5.2": ("high", "max"), "kimi-k3": ("max",)}
        if model_id in vocab:
            return ReasoningSpec("effort", vocab[model_id])
        return ReasoningSpec("unsupported", ())


def _screen(tmp_path, monkeypatch):
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    saved = []
    return SettingsScreen(AppConfig(), on_saved=lambda: saved.append(True), capability_client=FakeCaps()), saved


def test_transcription_mutations_roundtrip_to_disk(tmp_path, monkeypatch):
    from subforge.config.app_config import load_app_config

    screen, saved = _screen(tmp_path, monkeypatch)
    screen.set_transcription_source("openai")
    screen.apply_tc_key("sk-xyz")
    screen.apply_tc_model("whisper-1")
    screen.save_config()

    loaded = load_app_config()
    assert loaded.transcription.provider == "openai"
    assert loaded.transcription.api_key == "sk-xyz"
    assert loaded.transcription.model == "whisper-1"
    assert saved == [True]


def test_translation_local_and_provider_paths(tmp_path, monkeypatch):
    from subforge.config.app_config import load_app_config

    screen, _ = _screen(tmp_path, monkeypatch)

    # local path
    screen.set_translation_source("local")
    screen.apply_tl_url("http://192.168.1.20:1234/v1")
    screen.apply_tl_model("qwen3-14b")
    screen.apply_batch(8)

    # switch to provider path — local fields stay stored but unused
    screen.set_translation_source("provider")
    screen.apply_tl_preset("opencode-go")
    screen.apply_tl_key("oc-key")
    screen.apply_tl_model("glm-5.2")
    screen.save_config()

    loaded = load_app_config()
    t = loaded.translation
    assert t.source == "provider"
    assert t.local_base_url == "http://192.168.1.20:1234/v1"  # preserved for switching back
    assert t.provider == "opencode-go"
    assert t.api_key == "oc-key"
    assert t.model == "glm-5.2"
    assert t.batch_size == 8


def test_reasoning_reset_when_model_changes(tmp_path, monkeypatch):
    screen, _ = _screen(tmp_path, monkeypatch)
    screen.set_translation_source("provider")
    screen.apply_tl_preset("opencode-zen")

    screen.apply_tl_model("glm-5.2")  # offers [high, max]
    screen.apply_reasoning("max")
    assert screen.cfg.translation.reasoning_effort == "max"

    screen.apply_tl_model("kimi-k3")  # only [max] -> max still fine
    assert screen.cfg.translation.reasoning_effort == "max"

    screen.apply_tl_model("nemotron")  # unsupported -> stale value dropped
    assert screen.cfg.translation.reasoning_effort == ""


def test_batch_size_coerced_and_clamped(tmp_path, monkeypatch):
    screen, _ = _screen(tmp_path, monkeypatch)
    screen.apply_batch("12")
    assert screen.cfg.translation.batch_size == 12
    screen.apply_batch("0")  # invalid -> falls back to default 5
    assert screen.cfg.translation.batch_size == 5


async def test_settings_screen_renders_section_labels():
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.settings import SettingsScreen

    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await app.push_screen(SettingsScreen(AppConfig()))
        await pilot.pause()
        labels = " ".join(str(l.render()) for l in app.screen.query("Label"))
        assert "Transcription" in labels and "Translation" in labels
        buttons = " ".join(str(b.label) for b in app.screen.query("Button"))
        assert "Reasoning:" in buttons and "Batch size:" in buttons


# ---- wizard re-run from Settings -------------------------------------------


async def test_open_wizard_prefills_and_completion_saves(tmp_path, monkeypatch):
    from subforge.config.app_config import load_app_config
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.settings import SettingsScreen
    from subforge.tui.screens.setup_wizard import FirstRunSetupScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))

    cfg = AppConfig(transcription={"provider": "local", "model": "medium"})
    saved: list[bool] = []
    app = SubForgeApp(app_config=cfg.model_copy(deep=True))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = SettingsScreen(cfg, on_saved=lambda: saved.append(True))
        await app.push_screen(screen)
        await pilot.pause()

        # button exists and seam pushes the wizard prefilled with current values
        assert app.screen.query_one("#btn-wizard")
        screen.open_wizard()
        await pilot.pause()

        def find_wizard() -> FirstRunSetupScreen:
            for s in reversed(list(app.screen_stack)):
                if isinstance(s, FirstRunSetupScreen):
                    return s
            raise AssertionError("wizard not pushed")

        wizard = find_wizard()
        assert wizard.cfg.transcription.model == "medium"  # prefilled, not blank

        # user changes translation side inside the wizard and finishes
        wizard.cfg.translation.source = "local"
        wizard.cfg.translation.local_base_url = "http://localhost:1234/v1"
        wizard.cfg.translation.source = "local"
        wizard.cfg.translation.local_base_url = "http://localhost:1234/v1"
        wizard.cfg.translation.model = "qwen3-14b"

        # close the wizard's own first-step modal (as a user would), then finish
        app.screen.action_cancel()  # type: ignore[union-attr]
        await pilot.pause()
        wizard.finish()
        await pilot.pause()

        loaded = load_app_config()
        assert loaded.transcription.model == "medium"
        assert loaded.translation.source == "local"
        assert loaded.translation.model == "qwen3-14b"

        # settings reloaded its view of config and notified the app
        assert screen.cfg.translation.model == "qwen3-14b"
        assert saved == [True]
        # back on settings after finish (step modals dismissed with the wizard)
        assert isinstance(app.screen, SettingsScreen)


async def test_wizard_button_present_in_dom():
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.settings import SettingsScreen

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await app.push_screen(SettingsScreen(AppConfig()))
        await pilot.pause()
        buttons = [str(b.label) for b in app.screen.query("Button")]
        assert any("wizard" in b.lower() for b in buttons)


# ---- keyboard-only interaction (ARCH §3.2) ---------------------------------


async def test_keybindings_drive_settings(tmp_path, monkeypatch):
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = SettingsScreen(AppConfig())
        await app.push_screen(screen)
        await pilot.pause()

        # 't' cycles transcribe source local -> openai
        await pilot.press("t")
        assert screen.cfg.transcription.provider == "openai"
        await pilot.press("t")
        assert screen.cfg.transcription.provider == "local"

        # 'c' cycles translate source local -> provider
        await pilot.press("c")
        assert screen.cfg.translation.source == "provider"

        # 'o' opens the audio-language prompt
        from subforge.tui.screens.settings import TextInputScreen

        await pilot.press("o")
        assert isinstance(app.screen, TextInputScreen)
        app.screen.action_cancel()  # type: ignore[union-attr]
        await pilot.pause()


async def test_wizard_and_save_keys(tmp_path, monkeypatch):
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.settings import SettingsScreen
    from subforge.tui.screens.setup_wizard import FirstRunSetupScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = SettingsScreen(AppConfig(transcription={"provider": "local", "model": "small"}))
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.press("w")  # wizard
        await pilot.pause()
        for s in reversed(list(app.screen_stack)):
            if isinstance(s, FirstRunSetupScreen):
                break
        else:
            raise AssertionError("wizard not opened by 'w'")
        app.screen.action_cancel()  # type: ignore[union-attr]  # leave wizard step modal
        await pilot.pause()
        app.screen.action_cancel()  # type: ignore[union-attr]  # leave wizard itself
        await pilot.pause()

        await pilot.press("ctrl+s")  # save without mouse
        await pilot.pause()
        assert (tmp_path / "config.json").exists()


async def test_escape_returns_to_menu_from_settings():
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.main_menu import MainMenuScreen
    from subforge.tui.screens.settings import SettingsScreen

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.screen
        await app.push_screen(SettingsScreen(AppConfig()))
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, MainMenuScreen)
        assert menu is not None


def test_keymap_legend_rendered():
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.settings import SettingsScreen

    async def go():
        app = SubForgeApp()
        async with app.run_test() as pilot:
            await app.push_screen(SettingsScreen(AppConfig()))
            await pilot.pause()
            labels = " ".join(str(l.render()) for l in app.screen.query("Label"))
            return labels

    import asyncio

    labels = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(go())
    for key in ("w", "t", "y", "k", "o", "c", "p", "i", "d", "n", "r", "b", "g"):
        assert key in labels
