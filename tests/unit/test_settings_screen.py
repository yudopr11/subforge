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
    assert calls == []  # on_saved deferred to session close
    screen.on_unmount()  # settings session ends
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
    assert saved == []  # deferred to close
    screen.on_unmount()
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


async def test_settings_opens_two_choice_menu():
    """Opening /settings presents a 2-choice menu: Transcribe or Translation."""
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.project import ChoiceScreen
    from subforge.tui.screens.settings import SettingsScreen

    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await app.push_screen(SettingsScreen(AppConfig()))
        await pilot.pause()
        assert isinstance(app.screen, ChoiceScreen)
        options = [str(o.prompt) for o in app.screen.query_one("#choices").options]
        assert any("Transcribe" in o for o in options)
        assert any("Translation" in o for o in options)


# ---- guided settings flow (Pi-style choice walk) ------------------------------


class _StaticLoader(list):
    """Callable list — satisfies Loader contract offline."""

    def __call__(self) -> list[str]:
        return list(self)


def fake_loaders(models: dict[str, list[str]]) -> object:
    def factory(kind: str) -> _StaticLoader:
        return _StaticLoader(models.get(kind.split(":")[0], ["fake-model-1"]))

    return factory


def _pick(screen: object, prompt: str) -> None:
    from subforge.tui.screens.language_picker import LanguagePickerScreen
    from subforge.tui.screens.model_picker import ModelPickerScreen
    from subforge.tui.screens.project import ChoiceScreen
    from subforge.tui.screens.settings import (
        ApiKeyInputScreen,
        ReasoningPickerScreen,
        UrlInputScreen,
    )

    if isinstance(screen, ChoiceScreen):
        screen.choose(prompt)
    elif isinstance(screen, (ReasoningPickerScreen, ModelPickerScreen)):
        screen.on_option_list_option_selected(
            type("Evt", (), {"option": type("O", (), {"prompt": prompt})()})()
        )
    elif isinstance(screen, (ApiKeyInputScreen, UrlInputScreen, LanguagePickerScreen)):
        field = screen.query_one("Input")
        field.value = prompt
        screen.on_input_submitted(type("Evt", (), {"input": field})())
    else:  # pragma: no cover — guards future modal additions
        raise TypeError(f"no driver for {type(screen).__name__}")


async def test_settings_menu_drives_each_stage_then_saves(tmp_path, monkeypatch):
    """Menu -> Transcribe (model + source lang) -> menu -> Translation (model + target)."""
    from subforge.config.app_config import load_app_config
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.project import ChoiceScreen
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    loaders = fake_loaders({"whisper": ["small · Lightweight"], "local": ["qwen3-14b"]})
    saved: list[bool] = []
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = SettingsScreen(
            AppConfig(), on_saved=lambda: saved.append(True), loader_factory=loaders  # type: ignore[arg-type]
        )
        await app.push_screen(screen)
        await pilot.pause()

        # menu appears first
        assert isinstance(app.screen, ChoiceScreen)

        # -> Transcribe: local whisper + source language
        _pick(app.screen, "Transcribe  —  model + source language")
        await pilot.pause()
        lbls = [str(l.render()) for l in app.screen.query("Label")]
        assert any("Transcription — where does it run" in s for s in lbls)
        _pick(app.screen, "Local (WhisperX)")
        await pilot.pause()
        _pick(app.screen, "small · Lightweight")
        await pilot.pause()
        _pick(app.screen, "id")  # source language
        await pilot.pause()

        # returns to the menu; configure -> Translation: local server + target lang
        assert isinstance(app.screen, ChoiceScreen)
        _pick(app.screen, "Translation  —  model + target language")
        await pilot.pause()
        _pick(app.screen, "Local server (LM Studio / Ollama)")
        await pilot.pause()
        _pick(app.screen, "http://localhost:1234/v1")
        await pilot.pause()
        _pick(app.screen, "")
        await pilot.pause()
        _pick(app.screen, "qwen3-14b")
        await pilot.pause()
        _pick(app.screen, "en")  # target language
        await pilot.pause()

        loaded = load_app_config()
        assert loaded.transcription.provider == "local"
        assert loaded.transcription.model == "small"
        assert loaded.translation.source == "local"
        assert loaded.translation.local_base_url == "http://localhost:1234/v1"
        assert loaded.translation.model == "qwen3-14b"
        assert loaded.transcription.language == "id"
        assert loaded.translation.default_target == "en"
        # persisted at every stage save, but the host is notified ONCE at close
        assert saved == []
        await pilot.press("escape")  # menu -> close settings (session ends)
        await pilot.pause()
        assert saved == [True]


async def test_settings_guided_flow_cloud_offers_reasoning(tmp_path, monkeypatch):
    """Cloud translation path asks reasoning ONLY for the model's vocabulary."""
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.settings import ReasoningPickerScreen, SettingsScreen

    class FakeCaps:
        def reasoning_spec(self, provider_preset: str, model_id: str) -> ReasoningSpec:
            if model_id == "glm-5.2":
                return ReasoningSpec("effort", ("high", "max"))
            return ReasoningSpec("unsupported", ())

    loaders = fake_loaders({"cloud": ["glm-5.2"]})
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = SettingsScreen(
            AppConfig(), capability_client=FakeCaps(), loader_factory=loaders  # type: ignore[arg-type]
        )
        await app.push_screen(screen)
        await pilot.pause()

        # menu -> Transcribe (OpenAI) -> model + source lang, then back to menu
        _pick(app.screen, "Transcribe  —  model + source language")
        await pilot.pause()
        _pick(app.screen, "OpenAI provider")
        await pilot.pause()
        _pick(app.screen, "sk-test")  # API key
        await pilot.pause()
        _pick(app.screen, "whisper-1")
        await pilot.pause()
        _pick(app.screen, "")
        await pilot.pause()  # source language: auto-detect

        # menu -> Translation (cloud) -> model -> reasoning
        _pick(app.screen, "Translation  —  model + target language")
        await pilot.pause()
        _pick(app.screen, "Cloud provider")
        await pilot.pause()
        _pick(app.screen, "OpenCode Zen (opencode-zen)")
        await pilot.pause()
        _pick(app.screen, "oc-key")
        await pilot.pause()
        _pick(app.screen, "glm-5.2")
        await pilot.pause()

        assert isinstance(app.screen, ReasoningPickerScreen)
        options = [str(o.prompt) for o in app.screen.query_one("OptionList").options]
        assert options == ["high", "max"]
        _pick(app.screen, "max")
        await pilot.pause()
        assert screen.cfg.translation.reasoning_effort == "max"


# ---- keyboard-only interaction (ARCH §3.2) ---------------------------------


async def test_settings_escape_mid_flow_cancels(tmp_path, monkeypatch):
    """Esc on the first step backs out through settings to the REPL, unsaved."""
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.repl import ReplScreen
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = SettingsScreen(AppConfig(transcription={"provider": "local", "model": "small"}))
        await app.push_screen(screen)
        await pilot.pause()

        # first step modal is up; Esc closes it -> SettingsScreen acts cancelled
        await pilot.press("escape")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, ReplScreen)
        # nothing was persisted for the (never-completed) flow: disk stays defaults
        from subforge.config.app_config import load_app_config as _load

        assert _load().transcription.model == ""


async def test_escape_returns_to_repl_from_settings():
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.repl import ReplScreen
    from subforge.tui.screens.settings import SettingsScreen

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.screen
        assert isinstance(repl, ReplScreen)
        await app.push_screen(SettingsScreen(AppConfig()))
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ReplScreen)
