"""First-run setup wizard: choose Whisper model & language → main menu.

Flow: modal wizard orchestrates and writes AppConfig at the end.
Local Whisper choice offers an immediate model install. Esc skips setup.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

from subforge.app.model_manager import LocalModelManager
from subforge.config.app_config import AppConfig, save_app_config
from subforge.tui.screens.language_picker import LanguagePickerScreen
from subforge.tui.screens.model_manager import ModelManagerScreen

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp


class FirstRunSetupScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Skip setup")
    ]

    def __init__(
        self,
        on_done: Callable[[], None] | None = None,
        model_manager_factory: Callable[[], LocalModelManager] | None = None,
        initial_config: AppConfig | None = None,
    ) -> None:
        super().__init__()
        # Re-runs prefill with current values; first-run starts from defaults.
        self.cfg = initial_config.model_copy(deep=True) if initial_config else AppConfig()
        self.on_done = on_done
        self._mm_factory = model_manager_factory or LocalModelManager

    # ---- rendering -------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]Setup Wizard[/b]  —  configure local Whisper transcription")
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
        self.finish()

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
