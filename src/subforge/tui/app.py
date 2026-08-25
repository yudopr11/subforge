"""Textual application root. Presentation only — logic lives in app/* (ARCH §3.1)."""

from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from subforge.config.app_config import AppConfig, is_first_run, load_app_config
from subforge.tui.screens.repl import ReplScreen
from subforge.tui.screens.setup_wizard import FirstRunSetupScreen


class SubForgeApp(App[None]):
    TITLE = "SUBFORGE"

    CSS = """
    /* ---- shared keyboard-first primitives ---- */
    .panel {
        border: round $primary;
        padding: 1 2;
        margin: 0 1 1 0;
        height: auto;
        width: 1fr;
    }
    .section-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    .panel Button {
        width: 100%;
        height: auto;
        content-align: left middle;
        background: transparent;
        border: none;
        padding: 0 1;
        text-style: none;
    }
    .panel Button:hover {
        background: $surface-lighten-2;
    }
    .panel Button:focus {
        background: $primary 25%;
        text-style: bold;
    }
    .keymap {
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }
    .primary-action {
        width: 100%;
        border: round $success;
        text-style: bold;
        margin-bottom: 1;
    }
    .primary-action:focus {
        background: $success 25%;
    }
    #settings-title {
        width: 100%;
    }
    #settings-actions {
        height: auto;
        align-horizontal: right;
    }
    #settings-actions Button {
        width: auto;
        margin-left: 1;
    }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("q", "quit", "Quit")
    ]

    def __init__(
        self,
        project_dir: Path | None = None,
        app_config: AppConfig | None = None,
        force_setup: bool | None = None,
    ) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.app_config: AppConfig = app_config if app_config is not None else load_app_config()
        # First launch runs the setup wizard before anything else.
        self.needs_setup = force_setup if force_setup is not None else is_first_run()

    def on_mount(self) -> None:
        self.push_screen(ReplScreen())
        if self.needs_setup:
            self.push_screen(FirstRunSetupScreen(on_done=self._setup_finished))

    def screen_query_menu(self) -> ReplScreen:
        """Back-compat: the REPL home, wherever it sits in the stack."""
        return self.repl

    @property
    def repl(self) -> ReplScreen:
        for screen in reversed(list(self.screen_stack)):
            if isinstance(screen, ReplScreen):
                return screen
        raise LookupError("repl not mounted")

    def _setup_finished(self) -> None:
        """Wizard saved config: reload providers and refresh the menu status."""
        repl = self.screen_query_menu()
        self.app_config = load_app_config()
        self.needs_setup = False
        repl.reload_config()
        repl.log_line("[green]Setup complete[/green] — you are ready. Type ? for commands.")


def run(project_dir: str | None = None) -> None:
    SubForgeApp(project_dir=Path(project_dir) if project_dir else None).run()
