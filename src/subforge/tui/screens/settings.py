"""Setup & Settings: local/provider choice, key entry, model + reasoning picks.

All network access goes through provider objects' list_models() and the
capability client; this module only orchestrates screens and writes AppConfig
(ARCH §3.1). Keys are masked, never logged.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Label, OptionList, RadioButton

from subforge.app.provider_factory import validate_reasoning_choice
from subforge.config.app_config import AppConfig, save_app_config
from subforge.config.providers import TRANSLATION_PRESETS
from subforge.providers.capabilities import CapabilityClient, ReasoningSpec

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp


def refresh_reasoning(current: str, spec: ReasoningSpec) -> str:
    """Drop a stored reasoning value that the current model no longer offers."""
    return validate_reasoning_choice(spec, current)


class ApiKeyInputScreen(ModalScreen[str | None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    def __init__(self, title: str) -> None:
        super().__init__()
        self.picker_title = title
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(f"[b]{self.picker_title}[/b]")
        yield Input(password=True, placeholder="paste API key, Enter to confirm")
        yield Label("Esc cancel — stored locally in ~/.config/subforge/config.json")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.result = event.input.value.strip() or None
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextInputScreen(ModalScreen[str | None]):
    """Generic single-line prompt (Enter submits, Esc cancels)."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    def __init__(self, title: str, current: str = "", placeholder: str = "") -> None:
        super().__init__()
        self.picker_title = title
        self.current = current
        self.placeholder_text = placeholder
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(f"[b]{self.picker_title}[/b]")
        yield Input(value=self.current, placeholder=self.placeholder_text)
        yield Label("Enter confirm · Esc cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.result = event.input.value.strip() or None
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ReasoningPickerScreen(ModalScreen[str | None]):
    """Offers EXACTLY the effort values discovered for the selected model."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    def __init__(self, spec: ReasoningSpec) -> None:
        super().__init__()
        self.spec = spec
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("[b]Reasoning effort[/b] — values provided by the model")
        yield OptionList(*self.spec.values, id="reasoning")
        yield Label("Esc = send without reasoning parameter")

    def on_mount(self) -> None:
        if self.spec.kind != "effort":  # defensive: control should be hidden upstream
            self.query_one("#reasoning", OptionList).disabled = True

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.result = str(event.option.prompt)
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class UrlInputScreen(ModalScreen[str | None]):
    """Enter a local OpenAI-compatible base URL (LM Studio / Ollama)."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    def __init__(self, current: str) -> None:
        super().__init__()
        self.current = current
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("[b]Local server base URL[/b]")
        yield Input(value=self.current, placeholder="http://localhost:1234/v1", id="url")
        yield Label("Must include /v1 for OpenAI-compatible servers · Esc cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        url = event.input.value.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            self.query_one("#url", Input).value = "[ERROR] URL must start with http:// or https://"
            return
        self.result = url + "/v1" if not url.endswith("/v1") else url
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SettingsScreen(Screen[None]):
    """Interactive configuration; state transitions per revision 2026-08-25:

      Transcribe:  [Local|Provider]
        Local    -> pick a known Whisper profile (install via ModelManagerScreen)
        Provider -> ApiKeyInputScreen -> ModelPickerScreen(openai.list_models)
      Translate:   [Local|Provider]
        Local    -> edit base URL (UrlInputScreen) -> ModelPickerScreen
        Provider -> preset -> ApiKeyInputScreen -> ModelPickerScreen
                 -> ReasoningPickerScreen (only if spec.kind == "effort")
      Model changed -> reasoning_effort = refresh_reasoning(old, new_spec)
      Save -> save_app_config(cfg) -> on_saved() rebuilds providers mid-session.

    Mutations flow through the public ``apply_*``/``set_*`` methods — the tested
    seam; widget handlers only collect input and call them.
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    def __init__(
        self,
        app_config: AppConfig,
        on_saved: Callable[[], None] | None = None,
        capability_client: object | None = None,
    ) -> None:
        super().__init__()
        self.cfg = app_config
        self.on_saved = on_saved
        self._cap_client = capability_client if capability_client is not None else CapabilityClient()
        self._last_spec: ReasoningSpec | None = None

    # ---- rendering -------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]SubForge Settings[/b] — changes apply immediately, no restart needed")
            with Vertical(id="tc-section"):
                yield Label("Transcription")
                with Horizontal():
                    yield RadioButton(label="Local (WhisperX)", value=self.cfg.transcription.provider == "local", id="tc-local")
                    yield RadioButton(label="OpenAI", value=self.cfg.transcription.provider == "openai", id="tc-openai")
                yield Button(f"Model: {self._model_label()}", id="btn-tc-model")
                yield Button(f"Audio language: {self._lang_label()}", id="btn-tc-lang")
                yield Button("Manage local models…", id="btn-tc-manage")
                yield Button("API key…", id="btn-tc-key")
            with Vertical(id="tl-section"):
                yield Label("Translation")
                with Horizontal():
                    yield RadioButton(label="Local server", value=self.cfg.translation.source == "local", id="tl-local")
                    yield RadioButton(
                        label=f"Cloud ({self.cfg.translation.provider})",
                        value=self.cfg.translation.source == "provider",
                        id="tl-provider",
                    )
                yield Button(f"Base URL: {self._url_label()}", id="btn-tl-url")
                yield Button(f"Preset: {self.cfg.translation.provider}", id="btn-tl-preset")
                yield Button("API key…", id="btn-tl-key")
                yield Button(f"Model: {self.cfg.translation.model or '—'}", id="btn-tl-model")
                yield Button(f"Reasoning: {self._reasoning_label()}", id="btn-tl-reasoning")
                yield Button(f"Batch size: {self.cfg.translation.batch_size}", id="btn-tl-batch")
                yield Button(f"Target language: {self.cfg.translation.default_target or '—'}", id="btn-tl-target")
            with Horizontal():
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", id="btn-cancel")

    def _model_label(self) -> str:
        tc = self.cfg.transcription
        if tc.provider == "local":
            return f"{tc.model} (local)" if tc.model else "pick local Whisper model"
        return tc.model or "pick from openai /models"

    def _url_label(self) -> str:
        t = self.cfg.translation
        return t.local_base_url if t.source == "local" else "(cloud preset)"

    def _reasoning_label(self) -> str:
        t = self.cfg.translation
        if t.reasoning_effort:
            return t.reasoning_effort
        if self._last_spec is not None and self._last_spec.kind == "unsupported":
            return "not offered"
        return "—"

    def _refresh_labels(self) -> None:
        if not self.is_mounted:
            return  # mutation seam may run before compose in unit tests
        try:
            self.query_one("#btn-tc-model", Button).label = f"Model: {self._model_label()}"
            self.query_one("#btn-tl-url", Button).label = f"Base URL: {self._url_label()}"
            self.query_one("#btn-tl-preset", Button).label = f"Preset: {self.cfg.translation.provider}"
            self.query_one("#btn-tl-model", Button).label = f"Model: {self.cfg.translation.model or '—'}"
            self.query_one("#btn-tl-reasoning", Button).label = f"Reasoning: {self._reasoning_label()}"
            self.query_one("#btn-tl-batch", Button).label = f"Batch size: {self.cfg.translation.batch_size}"
        except NoMatches:
            pass  # widgets not yet composed (unit-test seam)

    # ---- public mutation seam --------------------------------------------

    def set_transcription_source(self, source: str) -> None:
        self.cfg.transcription.provider = "openai" if source == "openai" else "local"
        self._refresh_labels()

    def set_translation_source(self, source: str) -> None:
        self.cfg.translation.source = "provider" if source == "provider" else "local"
        self._refresh_labels()

    def apply_tc_key(self, key: str) -> None:
        self.cfg.transcription.api_key = key

    def _lang_label(self) -> str:
        return self.cfg.transcription.language or "auto-detect"

    def apply_tc_language(self, language: str) -> None:
        self.cfg.transcription.language = language.strip().lower()
        if self.is_mounted:
            try:
                self.query_one("#btn-tc-lang", Button).label = f"Audio language: {self._lang_label()}"
            except NoMatches:
                pass

    def apply_default_target(self, language: str) -> None:
        language = language.strip().lower()
        if not language:
            return
        self.cfg.translation.default_target = language
        if self.is_mounted:
            try:
                self.query_one("#btn-tl-target", Button).label = f"Target language: {language}"
            except NoMatches:
                pass

    def apply_tc_model(self, model: str) -> None:
        self.cfg.transcription.model = model
        self._refresh_labels()

    def apply_tl_url(self, url: str) -> None:
        self.cfg.translation.local_base_url = url.rstrip("/")

    def apply_tl_preset(self, provider_id: str) -> None:
        if provider_id in TRANSLATION_PRESETS:
            self.cfg.translation.provider = provider_id  # type: ignore[assignment]
            self._refresh_labels()

    def apply_tl_key(self, key: str) -> None:
        self.cfg.translation.api_key = key

    def apply_tl_model(self, model: str) -> None:
        self.cfg.translation.model = model
        self._last_spec = self._spec_for_current_model()
        # PRD §15: stale values reset when the model's vocabulary changes.
        self.cfg.translation.reasoning_effort = refresh_reasoning(
            self.cfg.translation.reasoning_effort, self._last_spec
        )
        self._refresh_labels()

    def apply_reasoning(self, effort: str) -> None:
        self.cfg.translation.reasoning_effort = effort
        self._refresh_labels()

    def apply_batch(self, raw: str | int) -> None:
        try:
            size = int(raw)
        except (TypeError, ValueError):
            size = 0
        self.cfg.translation.batch_size = size if size >= 1 else 5
        self._refresh_labels()

    def _spec_for_current_model(self) -> ReasoningSpec:
        t = self.cfg.translation
        if t.source != "provider":
            return ReasoningSpec("unsupported", ())
        try:
            from subforge.config.app_config import AppConfig

            probe = AppConfig()
            probe.translation = t
            catalog_id = {"openai": "openai", "opencode-zen": "opencode", "opencode-go": "opencode-go"}[t.provider]
            return self._cap_client.reasoning_spec(catalog_id, t.model)  # type: ignore[attr-defined, no-any-return]
        except Exception:  # noqa: BLE001 — degraded catalog hides the control
            return ReasoningSpec("unsupported", ())

    # ---- persistence -------------------------------------------------------

    def save_config(self) -> None:
        save_app_config(self.cfg)
        if self.on_saved:
            self.on_saved()

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ---- widget handlers ----------------------------------------------------

    @property
    def _host(self) -> "SubForgeApp":
        return cast("SubForgeApp", self.app)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-save":
            self.save_config()
            self.dismiss(None)
            return
        if button_id == "btn-cancel":
            self.action_cancel()
            return
        if button_id == "btn-tc-key":
            self._host.push_screen(
                ApiKeyInputScreen("OpenAI API key"), lambda key: self.apply_tc_key(key or "")
            )
        elif button_id == "btn-tl-key":
            preset_name = TRANSLATION_PRESETS[self.cfg.translation.provider].name
            self._host.push_screen(
                ApiKeyInputScreen(f"{preset_name} API key"), lambda key: self.apply_tl_key(key or "")
            )
        elif button_id == "btn-tl-url":
            self._host.push_screen(
                UrlInputScreen(self.cfg.translation.local_base_url),
                lambda url: self.apply_tl_url(url or self.cfg.translation.local_base_url),
            )
        elif button_id == "btn-tl-batch":
            self._prompt_batch_size()
        elif button_id == "btn-tl-preset":
            self._cycle_preset()
        elif button_id == "btn-tc-model":
            self._pick_transcription_model()
        elif button_id == "btn-tc-lang":
            self._host.push_screen(
                TextInputScreen(
                    "Audio source language",
                    current=self.cfg.transcription.language,
                    placeholder="empty = auto-detect (e.g. id, en, ja)",
                ),
                lambda lang: self.apply_tc_language(lang or ""),
            )
        elif button_id == "btn-tc-manage":
            self._open_model_manager()
        elif button_id == "btn-tl-model":
            self._pick_translation_model()
        elif button_id == "btn-tl-target":
            self._host.push_screen(
                TextInputScreen(
                    "Default target language",
                    current=self.cfg.translation.default_target,
                    placeholder="e.g. en",
                ),
                lambda lang: self.apply_default_target(lang or ""),
            )
        elif button_id == "btn-tl-reasoning":
            self._pick_reasoning()

    def _prompt_batch_size(self) -> None:
        self._host.push_screen(
            ApiKeyInputScreen("Batch size (segments per request)"),
            lambda raw: self.apply_batch(raw or ""),
        )

    def _cycle_preset(self) -> None:
        ids = list(TRANSLATION_PRESETS)
        current = ids.index(self.cfg.translation.provider) if self.cfg.translation.provider in ids else -1
        self.apply_tl_preset(ids[(current + 1) % len(ids)])

    def _open_model_manager(self) -> None:
        from subforge.app.model_manager import LocalModelManager
        from subforge.tui.screens.model_manager import ModelManagerScreen

        def rebuild_labels() -> None:
            self._last_spec = None
            self._refresh_labels()

        self._host.push_screen(ModelManagerScreen(manager=LocalModelManager(), on_done=rebuild_labels))

    def _pick_transcription_model(self) -> None:
        from subforge.tui.screens.model_picker import ModelPickerScreen

        if self.cfg.transcription.provider == "local":
            from subforge.app.model_manager import (
                KNOWN_WHISPER_MODELS,
                LocalModelManager,
            )

            manager = LocalModelManager()
            models = [f"{mid} · {meta['profile']}" for mid, meta in KNOWN_WHISPER_MODELS.items()]
            self._host.push_screen(
                ModelPickerScreen("Choose local Whisper model", lambda: models),
                lambda choice: self.apply_tc_model(str(choice).split(" · ")[0]) if choice else None,
            )
            _ = manager
        else:
            from subforge.providers.transcription.openai import (
                OpenAITranscriptionProvider,
            )

            provider = OpenAITranscriptionProvider(api_key=self.cfg.transcription.api_key or "-")
            self._host.push_screen(
                ModelPickerScreen("Choose transcription model", provider.list_models),
                lambda choice: self.apply_tc_model(str(choice)) if choice else None,
            )

    def _pick_translation_model(self) -> None:
        from subforge.providers.translation.openai_compatible import (
            OpenAICompatibleProvider,
        )
        from subforge.tui.screens.model_picker import ModelPickerScreen

        t = self.cfg.translation
        base_url = t.local_base_url if t.source == "local" else TRANSLATION_PRESETS[t.provider].base_url
        api_key = t.local_api_key if t.source == "local" else t.api_key
        provider = OpenAICompatibleProvider(base_url=base_url, api_key=api_key or "-", model=t.model or "x")
        self._host.push_screen(
            ModelPickerScreen("Choose translation model", provider.list_models),
            lambda choice: self.apply_tl_model(str(choice)) if choice else None,
        )

    def _pick_reasoning(self) -> None:
        spec = self._last_spec or self._spec_for_current_model()
        if spec.kind != "effort":
            return  # PRD §15: hide the control entirely when no vocabulary exists
        self._host.push_screen(
            ReasoningPickerScreen(spec),
            lambda choice: self.apply_reasoning(str(choice)) if choice else None,
        )
