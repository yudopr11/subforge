"""Textual application root. Presentation only — logic lives in app/* (ARCH §3.1)."""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from subforge.tui.screens.main_menu import MainMenuScreen


class SubForgeApp(App):
    TITLE = "SUBFORGE"
    BINDINGS = [("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())


def run(project_dir: str | None = None) -> None:
    SubForgeApp().run()
