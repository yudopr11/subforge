"""Textual application root. Presentation only — logic lives in app/* (ARCH §3.1)."""

from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from subforge.tui.screens.main_menu import MainMenuScreen


class SubForgeApp(App[None]):
    TITLE = "SUBFORGE"
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())


def run(project_dir: str | None = None) -> None:
    SubForgeApp().run()
