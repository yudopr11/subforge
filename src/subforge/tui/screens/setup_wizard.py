"""First-run setup wizard: transcribe provider → translate provider → main menu.

Flow (PRD §7 revision): every step is a pushed modal; the wizard orchestrates
and writes AppConfig at the end. Local Whisper choice offers an immediate
model install. Esc on the wizard skips setup — guided Settings kick in later.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

from subforge.app.model_manager import LocalModelManager
from subforge.config.app_config import AppConfig, save_app_config
from subforge.config.providers import TRANSLATION_PRESETS
from subforge.tui.screens.language_picker import LanguagePickerScreen
from subforge.tui.screens.model_manager import ModelManagerScreen
from subforge.tui.screens.model_picker import ModelPickerScreen
from subforge.tui.screens.project import ChoiceScreen
from subforge.tui.screens.settings import (
    ApiKeyInputScreen,
    ReasoningPickerScreen,
    UrlInputScreen,
)

if TYPE_CHECKING:
    from subforge.providers.capabilities import ReasoningSpec
    from subforge.tui.app import SubForgeApp

Loader = Callable[[], list[str]]


def _whisper_entries() -> list[str]:
    manager = LocalModelManager()
    models = manager.list_models()
    entries = []
    for m in models:
        rec = " [RECOMMENDED]" if m.recommended else ""
        entries.append(f"{m.id} · {m.profile} ({m.vram}, {m.size}){rec}")
    return entries


class FirstRunSetupScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Skip setup")
    ]

    def __init__(
        self,
        on_done: Callable[[], None] | None = None,
        loader_factory: Callable[[str], Loader] | None = None,
        model_manager_factory: Callable[[], LocalModelManager] | None = None,
        capability_client: object | None = None,
        initial_config: AppConfig | None = None,
    ) -> None:
        super().__init__()
        # Re-runs prefill with current values; first-run starts from defaults.
        self.cfg = initial_config.model_copy(deep=True) if initial_config else AppConfig()
        self.on_done = on_done
        self._loader_factory = loader_factory
        self._mm_factory = model_manager_factory or LocalModelManager
        self._cap_client = capability_client

    # ---- rendering -------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]Setup Wizard[/b]  —  configure transcription + translation")
            yield Label("", id="setup-status")

    def on_mount(self) -> None:
        self.begin_transcription_choice()

    @property
    def _host(self) -> "SubForgeApp":
        return cast("SubForgeApp", self.app)

    def _push(self, screen: Any, callback: Callable[[Any], None]) -> None:
        """Push any modal; push_screen is generic over its dismiss value."""
        host = cast("SubForgeApp", self.app)
        host.push_screen(screen, callback)

    def _set_status(self, message: str) -> None:
        label = self.query_one("#setup-status", Label)
        label.update(message)
        self._log_repl(message)

    def _log_repl(self, message: str) -> None:
        """Mirror the wizard's current step into the REPL transcript (Pi-style)."""
        try:
            self._host.screen_query_menu().log_line(f"▸ {message}")
        except LookupError:
            pass  # REPL not yet mounted (unit seam)

    def _loader(self, kind: str) -> Loader:
        if self._loader_factory is not None:  # test seam
            return self._loader_factory(kind)
        if kind == "whisper":
            return _whisper_entries
        if kind.startswith("openai"):
            raise ValueError(f"OpenAI transcription is no longer supported: {kind}")
        if kind.startswith("local"):
            from subforge.providers.translation.openai_compatible import (
                OpenAICompatibleProvider,
            )

            remainder = kind.removeprefix("local:").removeprefix("local")
            remainder = remainder.removeprefix(":")
            url, _, key = remainder.partition("|")
            return OpenAICompatibleProvider(base_url=url, api_key=key, model="discovery").list_models
        if kind.startswith("cloud"):
            preset = TRANSLATION_PRESETS[kind.split(":", 1)[1]]
            from subforge.providers.translation.openai_compatible import (
                OpenAICompatibleProvider,
            )

            return OpenAICompatibleProvider(
                base_url=preset.base_url, api_key=self.cfg.translation.api_key or "-", model="discovery"
            ).list_models
        raise ValueError(f"unknown loader kind: {kind}")

    # ---- step 1: transcription ---------------------------------------------

    def begin_transcription_choice(self) -> None:
        self._set_status("Step 1/2 · Choose Whisper model (always local)")
        manager = self._mm_factory()
        self._push(
            ModelManagerScreen(manager=manager, current_model=self.cfg.transcription.model),
            lambda model: self.apply_tc_model(str(model)) if model else None,
        )

    def apply_tc_model(self, entry: str) -> None:
        """Accept a raw id ('small') or a picker entry ('small · Lightweight …')."""
        self.cfg.transcription.model = entry.split(" · ")[0]
        self._set_status(f"Transcription: {self.cfg.transcription.provider} · {self.cfg.transcription.model}")
        self._ask_source_language()

    def _ask_source_language(self) -> None:
        self._set_status("Step 2/2 · Audio source language (Enter empty for auto-detect)")
        self._push(
            LanguagePickerScreen(
                "Audio source language (Enter empty for auto-detect)",
                current=self.cfg.transcription.language,
            ),
            lambda lang: self._source_language_chosen(lang or ""),
        )

    def _source_language_chosen(self, language: str) -> None:
        self.cfg.transcription.language = language.strip().lower()
        self.cfg.translation.default_target = "en"
        self.finish()

    # ---- step 2: translation --------------------------------------------------

    def begin_translation_choice(self) -> None:
        self._set_status("Step 2/2 · Translation — where should it run?")
        self._push(
            ChoiceScreen("Translation", ["Local server (LM Studio / Ollama)", "Cloud provider"]),
            lambda choice: self._tl_source(str(choice) if choice else ""),
        )

    def _tl_source(self, choice: str) -> None:
        if not choice:
            return  # cancelled — remain on the wizard
        if choice.startswith("Local"):
            self.cfg.translation.source = "local"
            if self._loader_factory is None:
                from subforge.providers.translation.openai_compatible import detect_local_server

                detected = detect_local_server()
                if detected:
                    detected_url, detected_models = detected
                    self.cfg.translation.local_base_url = detected_url
                    self.cfg.translation.local_api_key = ""
                    self._set_status(f"Translation · detected {detected_url} ({len(detected_models)} model{'s' if len(detected_models) != 1 else ''})")
                    self._push(
                        ModelPickerScreen("Choose local translation model", self._loader(f"local:{detected_url}")),
                        lambda model: self.apply_tl_model(str(model)) if model else None,
                    )
                    return
            self._push(UrlInputScreen(self.cfg.translation.local_base_url), lambda url: self._tl_url(str(url)) if url else None)
        else:
            self.cfg.translation.source = "provider"
            labels = [f"{p.name} ({pid})" for pid, p in TRANSLATION_PRESETS.items()]
            self._push(ChoiceScreen("Cloud provider", labels), lambda pick_: self._tl_preset(str(pick_)) if pick_ else None)

    def _tl_url(self, url: str) -> None:
        self.cfg.translation.local_base_url = url
        self.cfg.translation.local_api_key = ""
        self._push(
            ModelPickerScreen("Choose local translation model", self._loader(f"local:{url}")),
            lambda model: self.apply_tl_model(str(model)) if model else None,
        )

    def _tl_local_key(self, key: str) -> None:
        self.cfg.translation.local_api_key = key
        url = self.cfg.translation.local_base_url
        self._push(
            ModelPickerScreen("Choose local translation model", self._loader(f"local:{url}|{key}")),
            lambda model: self.apply_tl_model(str(model)) if model else None,
        )

    def _tl_preset(self, label: str) -> None:
        for pid, preset in TRANSLATION_PRESETS.items():
            if label.startswith(preset.name):
                self.cfg.translation.provider = pid  # type: ignore[assignment]
                break
        self._push(
            ApiKeyInputScreen(f"{TRANSLATION_PRESETS[self.cfg.translation.provider].name} API key"),
            lambda key: self._tl_cloud_key(key or ""),
        )

    def _tl_cloud_key(self, key: str) -> None:
        if not key:
            self._set_status("[ERROR] API key required for cloud translation.")
            self._tl_source("Cloud")
            return
        self.cfg.translation.api_key = key
        preset_id = f"cloud:{self.cfg.translation.provider}"
        self._push(
            ModelPickerScreen("Choose translation model", self._loader(preset_id)),
            lambda model: self.apply_tl_model(str(model)) if model else None,
        )

    def apply_tl_model(self, entry: str) -> None:
        self.cfg.translation.model = entry.split(" · ")[0]
        self._ask_reasoning()

    def _ask_reasoning(self) -> None:
        """Offer EXACTLY this model's effort vocabulary (PRD §15).

        Skipped silently for local servers and models without one.
        """
        t = self.cfg.translation
        spec = self._current_reasoning_spec()
        if t.source != "provider" or spec.kind != "effort":
            self._ask_default_target()
            return

        self._set_status("Optional · reasoning effort offered by this model")

        def chosen(value: str | None) -> None:
            if value:
                self.cfg.translation.reasoning_effort = value.strip().lower()
            self._ask_default_target()

        self._push(
            ReasoningPickerScreen(spec),
            lambda value: chosen(str(value)) if value else chosen(None),
        )

    def _current_reasoning_spec(self) -> "ReasoningSpec":
        from subforge.providers.capabilities import (
            PROVIDER_TO_CATALOG,
            CapabilityClient,
            ReasoningSpec,
        )

        t = self.cfg.translation
        try:

            class _Cap(Protocol):
                def reasoning_spec(self, provider_preset: str, model_id: str) -> "ReasoningSpec": ...

            client = cast(_Cap, self._cap_client if self._cap_client is not None else CapabilityClient())
            catalog_id = PROVIDER_TO_CATALOG[t.provider]
            return client.reasoning_spec(catalog_id, t.model)
        except Exception:  # noqa: BLE001 — offline/degraded catalog hides the control
            return ReasoningSpec("unsupported", ())

    def _ask_default_target(self) -> None:

        self._set_status("Almost done — which language do you translate into most?")

        def target_chosen(lang: str | None) -> None:
            chosen = (lang or self.cfg.translation.default_target or "en").strip().lower()
            if chosen:
                self.cfg.translation.default_target = chosen
            self.finish()

        self._push(
            LanguagePickerScreen(
                "Default target language",
                current=self.cfg.translation.default_target,
            ),
            target_chosen,
        )

    # ---- finish ----------------------------------------------------------------

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        tr = self.cfg.transcription
        if not tr.model:
            errors.append("Whisper model not chosen")
        return errors

    def finish(self) -> None:
        errors = self.validation_errors()
        if errors:
            self._set_status("[ERROR] Incomplete setup: " + "; ".join(errors))
            return
        save_app_config(self.cfg)
        done = self.on_done
        self._log_repl("setup complete — configuration saved")
        self.dismiss(None)
        if done:
            done()

    def action_cancel(self) -> None:
        self.dismiss(None)
