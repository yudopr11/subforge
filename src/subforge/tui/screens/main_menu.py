"""Main menu matching the PRD §7 mockup."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView

ACTIONS = [
    "Select Audio / Open Project",
    "Transcribe",
    "Review Captions",
    "Translate",
    "Review Translation",
    "Export SRT / ASS",
]


class MainMenuScreen(Screen):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]SUBFORGE[/b] — local-first subtitles")
            yield ListView(*[ListItem(Label(a), name=a.lower()) for a in ACTIONS], classes="action-list", id="actions")
            yield Label("Status: Ready", id="status")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # MVP: wire Transcribe/Translate/Export to Pipeline in a UI follow-up plan;
        # see Task 12 interfaces (Pipeline.run_transcription / run_translation / export_subtitles).
        self.query_one("#status", Label).update(f"Selected: {event.item.name}")
