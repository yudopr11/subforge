"""Setup & Settings: local/provider choice, key entry, model + reasoning picks.

All network access goes through provider objects' list_models() and the
capability client; this module only orchestrates screens and writes AppConfig
(ARCH §3.1). Keys are masked, never logged.

``SettingsScreen`` is a two-option menu (Transcribe / Translation); picking one
drills into that stage's model + language, then returns to the menu.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, TypeVar, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import Input, Label, OptionList

from subforge.app.model_manager import KNOWN_WHISPER_MODELS
from subforge.app.provider_factory import validate_reasoning_choice
from subforge.config.app_config import AppConfig, save_app_config
from subforge.config.providers import TRANSLATION_PRESETS
from subforge.providers.capabilities import CapabilityClient, ReasoningSpec
from subforge.tui.screens.language_picker import LanguagePickerScreen
from subforge.tui.screens.model_picker import ModelPickerScreen
from subforge.tui.screens.project import ChoiceScreen

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp


def refresh_reasoning(current: str, spec: ReasoningSpec) -> str:
    """Drop a stored reasoning value that the current model no longer offers."""
    return validate_reasoning_choice(spec, current)


R = TypeVar("R")


class ApiKeyInputScreen(ModalScreen[str | None]):
    """Single masked key entry (Enter confirms, Esc cancels)."""

    AUTO_FOCUS = "Input"

    def __init__(self, title: str) -> None:
        super().__init__()
        self.picker_title = title
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[b]{self.picker_title}[/b]")
            yield Input(password=True, placeholder="paste API key, Enter to confirm")
            yield Label("Esc cancel — stored locally in ~/.config/subforge/config.json")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.result = event.input.value.strip() or None
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ReasoningPickerScreen(ModalScreen[str | None]):
    """Offers EXACTLY the effort values discovered for the selected model."""

    AUTO_FOCUS = "#reasoning"

    def __init__(self, spec: ReasoningSpec) -> None:
        super().__init__()
        self.spec = spec
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
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

    AUTO_FOCUS = "#url"

    def __init__(self, current: str) -> None:
        super().__init__()
        self.current = current
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
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


class SettingsScreen(ModalScreen[None]):
    """Two-option settings menu (PRD §7).

    On mount it shows a menu with two choices:

      Transcribe  -> provider (Local/OpenAI) -> model -> source language
      Translation -> provider (Local/Cloud) -> model -> reasoning (if offered)
                     -> default target language

    Each stage configures and **persists immediately** when finished, then returns
    to the menu so the other stage can be configured too. Esc on the menu closes
    settings (already-saved stages are kept); Esc on a step returns to the menu.

    Values flow through the public ``apply_*``/``set_*`` methods (the tested
    seam); the model-list loaders are injectable via ``loader_factory`` so the
    flow runs offline in tests.
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Back"),
    ]

    def __init__(
        self,
        app_config: AppConfig,
        on_saved: Callable[[], None] | None = None,
        capability_client: object | None = None,
        loader_factory: Callable[[str], Callable[[], list[str]]] | None = None,
    ) -> None:
        super().__init__()
        self.cfg = app_config
        self.on_saved = on_saved
        self._cap_client = capability_client if capability_client is not None else CapabilityClient()
        self._loader_factory = loader_factory
        self._last_spec: ReasoningSpec | None = None
        self._dirty = False  # any stage saved? notify on_saved once at close

    def _loader(self, kind: str) -> Callable[[], list[str]]:
        """Offline-injectable model-list loader (test seam, mirrors the wizard)."""
        if self._loader_factory is not None:
            return self._loader_factory(kind)
        if kind == "whisper":
            return lambda: [f"{mid} · {meta['profile']}" for mid, meta in KNOWN_WHISPER_MODELS.items()]
        if kind.startswith("openai:"):
            from subforge.providers.transcription.openai import OpenAITranscriptionProvider

            return OpenAITranscriptionProvider(api_key=kind.split(":", 1)[1]).list_models
        if kind.startswith("local:"):
            from subforge.providers.translation.openai_compatible import (
                OpenAICompatibleProvider,
            )

            _, url, key = kind.split(":", 2)
            return OpenAICompatibleProvider(base_url=url, api_key=key, model="discovery").list_models
        preset_id = kind.split(":", 1)[1]
        preset = TRANSLATION_PRESETS[preset_id]
        from subforge.providers.translation.openai_compatible import (
            OpenAICompatibleProvider,
        )

        return OpenAICompatibleProvider(
            base_url=preset.base_url, api_key=self.cfg.translation.api_key or "-", model="discovery"
        ).list_models

    # ---- rendering / plumbing ---------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-host"):
            yield Label(
                "[b]Settings[/b]  —  pick a stage to configure; Esc closes",
                id="settings-title",
            )
            yield Label("", id="settings-status")

    @property
    def _host(self) -> "SubForgeApp":
        return cast("SubForgeApp", self.app)

    def _push(self, screen: Screen[R], callback: Callable[[R | None], None]) -> None:
        self._host.push_screen(screen, callback)

    def _set_status(self, message: str) -> None:
        try:
            self.query_one("#settings-status", Label).update(message)
        except NoMatches:
            pass  # pre-mount unit seam

    def on_mount(self) -> None:
        self.show_menu()

    # ---- settings menu: choose which stage to configure ----------------------

    def show_menu(self) -> None:
        """Menu with two choices — Transcribe or Translation (PRD §7)."""
        self._set_status("Pick what to configure — Esc closes settings")
        self._push(
            ChoiceScreen(
                "Settings — what to configure?",
                [
                    "Transcribe  —  model + source language",
                    "Translation  —  model + target language",
                ],
            ),
            lambda c: self.menu_choice(str(c) if c else ""),
        )

    def menu_choice(self, choice: str) -> None:
        if not choice:
            self.action_cancel()  # Esc on the menu closes settings (changes saved)
            return
        if "Transcribe" in choice:
            self.begin_transcription_choice()
        else:
            self.begin_translation_choice()

    # ---- stage: transcription (provider + model + source language) -----------

    def begin_transcription_choice(self) -> None:
        self._set_status("Transcribe · where does it run?")
        self._push(
            ChoiceScreen("Transcription — where does it run?", ["Local (WhisperX)", "OpenAI provider"]),
            lambda c: self.tc_source(str(c) if c else ""),
        )

    def tc_source(self, choice: str) -> None:
        if not choice:
            self.show_menu()  # Esc back to the menu
            return
        self.set_transcription_source("openai" if "OpenAI" in choice else "local")
        self._pick_transcription_model()

    def _pick_transcription_model(self) -> None:
        if self.cfg.transcription.provider == "local":
            self._push(
                ModelPickerScreen("Choose local Whisper model", self._loader("whisper")),
                lambda m: self.tc_model(str(m) if m else ""),
            )
        elif not self.cfg.transcription.api_key:
            self._push(
                ApiKeyInputScreen("OpenAI API key"),
                lambda k: self.tc_key(str(k) if k else ""),
            )
        else:
            self._pick_tc_model_openai()

    def tc_key(self, key: str) -> None:
        if not key:
            self._set_status("[ERROR] OpenAI API key required.")
            self.begin_transcription_choice()
            return
        self.apply_tc_key(key)
        self._pick_tc_model_openai()

    def _pick_tc_model_openai(self) -> None:
        self._push(
            ModelPickerScreen(
                "Choose transcription model", self._loader(f"openai:{self.cfg.transcription.api_key or '-'}")
            ),
            lambda m: self.tc_model(str(m) if m else ""),
        )

    def tc_model(self, model: str) -> None:
        if model:
            self.apply_tc_model(model.split(" · ")[0])
        self.ask_tc_language()

    def ask_tc_language(self) -> None:
        self._set_status("Transcribe · source language (type to search)")
        self._push(
            LanguagePickerScreen(
                "Audio source language (Enter empty for auto-detect)",
                current=self.cfg.transcription.language,
            ),
            lambda lang: self.tc_language_chosen(str(lang) if lang else ""),
        )

    def tc_language_chosen(self, lang: str) -> None:
        self.apply_tc_language(lang)
        self.save_config()  # persist, then back to the menu
        self.show_menu()

    # ---- stage: translation (provider + model + reasoning + target language) ---

    def begin_translation_choice(self) -> None:
        self._set_status("Translation · where does it run?")
        self._push(
            ChoiceScreen(
                "Translation — where does it run?",
                ["Local server (LM Studio / Ollama)", "Cloud provider"],
            ),
            lambda c: self.tl_source(str(c) if c else ""),
        )

    def tl_source(self, choice: str) -> None:
        if not choice:
            self.show_menu()  # Esc back to the menu
            return
        if choice.startswith("Local"):
            self.set_translation_source("local")
            self._push(
                UrlInputScreen(self.cfg.translation.local_base_url),
                lambda u: self.tl_url(str(u) if u else ""),
            )
        else:
            self.set_translation_source("provider")
            self._pick_tl_preset()

    def tl_url(self, url: str) -> None:
        if not url:
            self.show_menu()
            return
        self.apply_tl_url(url)
        self._push(
            ApiKeyInputScreen("Local server API key (optional — Enter to skip)"),
            lambda k: self.tl_local_key(str(k) if k else ""),
        )

    def tl_local_key(self, key: str) -> None:
        self.apply_tl_local_key(key)
        self._pick_translation_model()

    def _pick_tl_preset(self) -> None:
        labels = [f"{preset.name} ({pid})" for pid, preset in TRANSLATION_PRESETS.items()]
        self._push(
            ChoiceScreen("Cloud translation provider", labels),
            lambda c: self.tl_preset(str(c) if c else ""),
        )

    def tl_preset(self, label: str) -> None:
        if not label:
            self.show_menu()
            return
        for pid, preset in TRANSLATION_PRESETS.items():
            if label.startswith(preset.name):
                self.apply_tl_preset(pid)
                break
        self._prompt_tl_key()

    def _prompt_tl_key(self) -> None:
        if self.cfg.translation.api_key:
            self._pick_translation_model()
            return
        name = TRANSLATION_PRESETS[self.cfg.translation.provider].name
        self._push(
            ApiKeyInputScreen(f"{name} API key"),
            lambda k: self.tl_key(str(k) if k else ""),
        )

    def tl_key(self, key: str) -> None:
        if not key:
            self._set_status("[ERROR] API key required.")
            self.begin_translation_choice()
            return
        self.apply_tl_key(key)
        self._pick_translation_model()

    def _pick_translation_model(self) -> None:
        t = self.cfg.translation
        if t.source == "local":
            loader = self._loader(f"local:{t.local_base_url}:{t.local_api_key or ''}")
        else:
            loader = self._loader(f"cloud:{t.provider}")
        self._push(
            ModelPickerScreen("Choose translation model", loader),
            lambda m: self.tl_model(str(m) if m else ""),
        )

    def tl_model(self, model: str) -> None:
        if model:
            self.apply_tl_model(model.split(" · ")[0])
        self._ask_reasoning()

    def _ask_reasoning(self) -> None:
        """Offer EXACTLY this model's effort vocabulary (PRD §15)."""
        spec = self._last_spec or self._spec_for_current_model()
        if spec.kind != "effort":
            self.ask_tl_language()
            return
        self._set_status("Optional · reasoning effort offered by this model")
        self._push(
            ReasoningPickerScreen(spec),
            lambda v: self.tl_reasoning(str(v) if v else ""),
        )

    def tl_reasoning(self, effort: str) -> None:
        if effort:
            self.apply_reasoning(effort)
        self.ask_tl_language()

    def ask_tl_language(self) -> None:
        self._set_status("Translation · default target language (type to search)")
        self._push(
            LanguagePickerScreen(
                "Default target language",
                current=self.cfg.translation.default_target,
            ),
            lambda lang: self.tl_language_chosen(str(lang) if lang else ""),
        )

    def tl_language_chosen(self, lang: str) -> None:
        self.apply_default_target(lang)
        self.save_config()  # persist, then back to the menu
        self.show_menu()

    # ---- public mutation seam (tested; used by the flow above) ------------------

    def set_transcription_source(self, source: str) -> None:
        self.cfg.transcription.provider = "openai" if source == "openai" else "local"

    def set_translation_source(self, source: str) -> None:
        self.cfg.translation.source = "provider" if source == "provider" else "local"

    def apply_tc_key(self, key: str) -> None:
        self.cfg.transcription.api_key = key

    def apply_tc_language(self, language: str) -> None:
        self.cfg.transcription.language = language.strip().lower()

    def apply_default_target(self, language: str) -> None:
        language = language.strip().lower()
        if language:
            self.cfg.translation.default_target = language

    def apply_tc_model(self, model: str) -> None:
        self.cfg.transcription.model = model

    def apply_tl_url(self, url: str) -> None:
        self.cfg.translation.local_base_url = url.rstrip("/")

    def apply_tl_preset(self, provider_id: str) -> None:
        if provider_id in TRANSLATION_PRESETS:
            self.cfg.translation.provider = provider_id  # type: ignore[assignment]

    def apply_tl_key(self, key: str) -> None:
        self.cfg.translation.api_key = key

    def apply_tl_local_key(self, key: str) -> None:
        self.cfg.translation.local_api_key = key

    def apply_tl_model(self, model: str) -> None:
        self.cfg.translation.model = model
        self._last_spec = self._spec_for_current_model()
        # PRD §15: stale values reset when the model's vocabulary changes.
        self.cfg.translation.reasoning_effort = refresh_reasoning(
            self.cfg.translation.reasoning_effort, self._last_spec
        )

    def apply_reasoning(self, effort: str) -> None:
        self.cfg.translation.reasoning_effort = effort

    def apply_batch(self, raw: str | int) -> None:
        try:
            size = int(raw)
        except (TypeError, ValueError):
            size = 0
        self.cfg.translation.batch_size = size if size >= 1 else 5

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

    # ---- persistence -----------------------------------------------------------------

    def save_config(self) -> None:
        """Persist the current config immediately — per-stage save (PRD §7).

        ``on_saved`` is deferred: it fires once when the settings session closes,
        so the host refreshes/labels once, not per stage.
        """
        save_app_config(self.cfg)
        self._dirty = True

    def on_unmount(self) -> None:
        if self._dirty and self.on_saved:
            self.on_saved()

    def action_cancel(self) -> None:
        self.dismiss(None)
