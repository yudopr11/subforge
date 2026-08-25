"""First-run setup wizard: transcribe provider → translate provider → main menu.

Flow (PRD §7 revision): every step is a pushed modal; the wizard orchestrates
and writes AppConfig at the end. Local Whisper choice offers an immediate
model install. Esc on the wizard skips setup — guided Settings kick in later.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Label

from subforge.app.model_manager import KNOWN_WHISPER_MODELS, LocalModelManager
from subforge.config.app_config import AppConfig, save_app_config
from subforge.config.providers import TRANSLATION_PRESETS
from subforge.tui.screens.model_manager import ModelManagerScreen
from subforge.tui.screens.model_picker import ModelPickerScreen
from subforge.tui.screens.project import ChoiceScreen
from subforge.tui.screens.settings import ApiKeyInputScreen, UrlInputScreen

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp

Loader = Callable[[], list[str]]


def _whisper_entries() -> list[str]:
    return [f"{mid} · {meta['profile']} ({meta['vram']})" for mid, meta in KNOWN_WHISPER_MODELS.items()]


class FirstRunSetupScreen(Screen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Skip setup")
    ]

    def __init__(
        self,
        on_done: Callable[[], None] | None = None,
        loader_factory: Callable[[str], Loader] | None = None,
        model_manager_factory: Callable[[], LocalModelManager] | None = None,
    ) -> None:
        super().__init__()
        self.cfg = AppConfig()
        self.on_done = on_done
        self._loader_factory = loader_factory
        self._mm_factory = model_manager_factory or LocalModelManager

    # ---- rendering -------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Label("[b]Welcome to SubForge[/b] — initial setup (Esc to skip for now)")
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

    def _loader(self, kind: str) -> Loader:
        if self._loader_factory is not None:  # test seam
            return self._loader_factory(kind)
        if kind == "whisper":
            return _whisper_entries
        if kind.startswith("openai"):
            from subforge.providers.transcription.openai import (
                OpenAITranscriptionProvider,
            )

            return OpenAITranscriptionProvider(api_key=kind.split(":", 1)[1]).list_models
        if kind.startswith("local"):
            from subforge.providers.translation.openai_compatible import (
                OpenAICompatibleProvider,
            )

            _, url, key = kind.split(":", 2)
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
        self._set_status("Step 1/2 · Transcription — where should it run?")
        self._push(
            ChoiceScreen("Transcription", ["Local (WhisperX)", "OpenAI provider"]),
            lambda choice: self._tc_source(str(choice) if choice else ""),
        )

    def _tc_source(self, choice: str) -> None:
        if not choice:
            return  # cancelled — remain on the wizard
        if choice.startswith("Local"):
            self._push(
                ModelPickerScreen("Choose Whisper model", self._loader("whisper")),
                lambda model: self.apply_tc_model(str(model)) if model else None,
            )
        else:
            self.cfg.transcription.provider = "openai"
            self._push(
                ApiKeyInputScreen("OpenAI API key"),
                lambda key: self._tc_key(key or ""),
            )

    def _tc_key(self, key: str) -> None:
        if not key:
            self._set_status("[ERROR] API key required for OpenAI transcription.")
            self.begin_transcription_choice()
            return
        self.cfg.transcription.api_key = key
        self._push(
            ModelPickerScreen("Choose transcription model", self._loader(f"openai:{key}")),
            lambda model: self.apply_tc_model(str(model)) if model else None,
        )

    def apply_tc_model(self, entry: str) -> None:
        """Accept a raw id ('small') or a picker entry ('small · Lightweight …')."""
        self.cfg.transcription.model = entry.split(" · ")[0]
        self._set_status(f"Transcription: {self.cfg.transcription.provider} · {self.cfg.transcription.model}")
        if self.cfg.transcription.provider == "local":
            self._offer_local_install()
        else:
            self.begin_translation_choice()

    def _offer_local_install(self) -> None:
        self._push(
            ChoiceScreen("Install model weights now?", ["Install now", "Later (I'll do it in Settings)"]),
            lambda choice: self._after_install_choice(str(choice) if choice else ""),
        )

    def _after_install_choice(self, choice: str) -> None:
        if choice.startswith("Install"):
            manager = self._mm_factory()
            self._push(ModelManagerScreen(manager=manager), lambda _: self.begin_translation_choice())
        else:
            self.begin_translation_choice()

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
            self._push(UrlInputScreen(self.cfg.translation.local_base_url), lambda url: self._tl_url(str(url)) if url else None)
        else:
            self.cfg.translation.source = "provider"
            labels = [f"{p.name} ({pid})" for pid, p in TRANSLATION_PRESETS.items()]
            self._push(ChoiceScreen("Cloud provider", labels), lambda pick_: self._tl_preset(str(pick_)) if pick_ else None)

    def _tl_url(self, url: str) -> None:
        self.cfg.translation.local_base_url = url
        self._push(
            ApiKeyInputScreen("Local server API key (optional — Enter to skip)"),
            lambda key: self._tl_local_key(key or ""),
        )

    def _tl_local_key(self, key: str) -> None:
        self.cfg.translation.local_api_key = key
        url = self.cfg.translation.local_base_url
        self._push(
            ModelPickerScreen("Choose local translation model", self._loader(f"local:{url}:{key}")),
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
        self.finish()

    # ---- finish ----------------------------------------------------------------

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        t, tr = self.cfg.translation, self.cfg.transcription
        if not tr.model:
            errors.append("transcription model not chosen")
        if not t.model:
            errors.append("translation model not chosen")
        if t.source == "local" and not t.local_base_url:
            errors.append("local translation URL missing")
        if t.source == "provider" and not t.api_key:
            errors.append("translation API key missing")
        return errors

    def finish(self) -> None:
        errors = self.validation_errors()
        if errors:
            self._set_status("[ERROR] Incomplete setup: " + "; ".join(errors))
            return
        save_app_config(self.cfg)
        done = self.on_done
        self.dismiss(None)
        if done:
            done()

    def action_cancel(self) -> None:
        self.dismiss(None)
