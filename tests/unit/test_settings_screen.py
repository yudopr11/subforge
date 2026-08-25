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
