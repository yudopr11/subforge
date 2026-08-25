"""Textual application root. Presentation only — logic lives in app/* (ARCH §3.1)."""

from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from subforge.config.app_config import AppConfig, is_first_run, load_app_config
from subforge.tui.screens.main_menu import MainMenuScreen
from subforge.tui.screens.setup_wizard import FirstRunSetupScreen


class SubForgeApp(App[None]):
    TITLE = "SUBFORGE"
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
        self.push_screen(MainMenuScreen())
        if self.needs_setup:
            self.push_screen(FirstRunSetupScreen(on_done=self._setup_finished))

    def screen_query_menu(self) -> MainMenuScreen:
        """The (single) main menu instance, wherever it sits in the stack."""
        for screen in reversed(list(self.screen_stack)):
            if isinstance(screen, MainMenuScreen):
                return screen
        raise LookupError("main menu not mounted")

    def _setup_finished(self) -> None:
        """Wizard saved config: reload providers and refresh the menu status."""
        self.app_config = load_app_config()
        self.needs_setup = False
        menu = self.screen_query_menu()
        menu._config_reloaded()
        menu._set_flow_status("Setup complete")


def run(project_dir: str | None = None) -> None:
    SubForgeApp(project_dir=Path(project_dir) if project_dir else None).run()
