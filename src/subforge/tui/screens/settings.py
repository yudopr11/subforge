"""Setup & Settings: configure local Whisper model and language.

Keys and configurations are stored in AppConfig (ARCH §3.1).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, TypeVar, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import Label

from subforge.config.app_config import AppConfig, save_app_config
from subforge.tui.screens.language_picker import LanguagePickerScreen
from subforge.tui.screens.project import ChoiceScreen

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp

R = TypeVar("R")


class SettingsScreen(ModalScreen[None]):
    """Settings menu: configure Whisper model + source language."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Back"),
    ]

    def __init__(
        self,
        app_config: AppConfig,
        on_saved: Callable[[], None] | None = None,
        loader_factory: Callable[[str], Callable[[], list[str]]] | None = None,
    ) -> None:
        super().__init__()
        self.cfg = app_config
        self.on_saved = on_saved
        self._loader_factory = loader_factory
        self._dirty = False

    def _loader(self, kind: str) -> Callable[[], list[str]]:
        if self._loader_factory is not None:
            return self._loader_factory(kind)
        if kind == "whisper":
            from subforge.app.model_manager import LocalModelManager

            manager = LocalModelManager()
            models = manager.list_models()
            entries = []
            for m in models:
                rec = " [RECOMMENDED]" if m.recommended else ""
                entries.append(f"{m.id} · {m.profile} ({m.vram}, {m.size}){rec}")
            return lambda: entries
        raise ValueError(f"unknown loader kind: {kind}")

    # ---- rendering / plumbing ---------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-host"):
            yield Label(
                "[b]Settings[/b]  —  configure local Whisper transcription; Esc closes",
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
        self.show_tc_steps()

    # ---- transcription step menu ---------------------------------------------

    def show_tc_steps(self) -> None:
        steps = [
            "1 · Select model — Whisper sizes for your machine",
            "2 · Source language — or auto-detect",
        ]
        self._set_status("Transcribe · pick a step — Esc closes")
        self._push(
            ChoiceScreen("Transcription Settings", steps),
            lambda c: self.tc_step(str(c) if c else ""),
        )

    def tc_step(self, choice: str) -> None:
        if not choice:
            self.action_cancel()
            return
        lowered = choice.lower()
        if "model" in lowered:
            self._pick_transcription_model()
        else:
            self.ask_tc_language()

    def _pick_transcription_model(self) -> None:
        from subforge.app.model_manager import LocalModelManager
        from subforge.tui.screens.model_manager import ModelManagerScreen

        manager = LocalModelManager()
        self._push(
            ModelManagerScreen(manager=manager, current_model=self.cfg.transcription.model),
            lambda m: self.tc_model(str(m) if m else ""),
        )

    def tc_model(self, model: str) -> None:
        if model:
            self.apply_tc_model(model.split(" · ")[0])
        self.save_config()
        self.show_tc_steps()

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
        self.save_config()
        self.show_tc_steps()

    # ---- public mutation seam ---------------------------------------------

    def set_transcription_source(self, source: str) -> None:
        self.cfg.transcription.provider = "local"

    def apply_tc_language(self, language: str) -> None:
        self.cfg.transcription.language = language.strip().lower()

    def apply_tc_model(self, model: str) -> None:
        self.cfg.transcription.model = model

    # ---- persistence ------------------------------------------------------

    def save_config(self) -> None:
        save_app_config(self.cfg)
        self._dirty = True

    def on_unmount(self) -> None:
        if self._dirty and self.on_saved:
            self.on_saved()

    def action_cancel(self) -> None:
        self.dismiss(None)
