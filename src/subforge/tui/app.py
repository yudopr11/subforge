"""Textual application root. Presentation only — logic lives in app/* (ARCH §3.1)."""

from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from subforge.config.app_config import AppConfig, load_app_config
from subforge.tui.screens.main_menu import MainMenuScreen


class SubForgeApp(App[None]):
    TITLE = "SUBFORGE"
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("q", "quit", "Quit")
    ]

    def __init__(
        self,
        project_dir: Path | None = None,
        app_config: AppConfig | None = None,
    ) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.app_config = app_config or load_app_config()

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())


def run(project_dir: str | None = None) -> None:
    SubForgeApp(project_dir=Path(project_dir) if project_dir else None).run()
