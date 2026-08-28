from subforge.config.app_config import AppConfig


def test_settings_screen_persists_on_save(tmp_path, monkeypatch):
    from subforge.config.app_config import load_app_config
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    calls: list[bool] = []
    screen = SettingsScreen(AppConfig(), on_saved=lambda: calls.append(True))
    screen.save_config()

    assert load_app_config().transcription.provider == "local"
    assert calls == []  # on_saved deferred to session close
    screen.on_unmount()  # settings session ends
    assert calls == [True]


def _screen(tmp_path, monkeypatch):
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    saved: list[bool] = []
    return SettingsScreen(AppConfig(), on_saved=lambda: saved.append(True)), saved


def test_transcription_mutations_roundtrip_to_disk(tmp_path, monkeypatch):
    from subforge.config.app_config import load_app_config

    screen, saved = _screen(tmp_path, monkeypatch)
    screen.apply_tc_model("small")
    screen.apply_tc_language("ja")
    screen.save_config()

    loaded = load_app_config()
    assert loaded.transcription.provider == "local"
    assert loaded.transcription.model == "small"
    assert loaded.transcription.language == "ja"
    assert saved == []  # deferred to close
    screen.on_unmount()
    assert saved == [True]


async def test_settings_opens_transcription_steps():
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.project import ChoiceScreen
    from subforge.tui.screens.settings import SettingsScreen

    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await app.push_screen(SettingsScreen(AppConfig()))
        await pilot.pause()
        assert isinstance(app.screen, ChoiceScreen)
        options = [str(o.prompt) for o in app.screen.query_one("#choices").options]
        assert any("model" in o.lower() for o in options)
        assert any("language" in o.lower() for o in options)


async def test_settings_escape_mid_flow_cancels(tmp_path, monkeypatch):
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = SettingsScreen(AppConfig(transcription={"provider": "local", "model": "small"}))
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
