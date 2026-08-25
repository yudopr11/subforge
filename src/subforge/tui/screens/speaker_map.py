"""Speaker naming: map anonymous diarization IDs to real names (PRD §12)."""

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label

from subforge.app.project_store import load_project, save_project


class SpeakerMapScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.project = load_project(project_dir)

    def compose(self) -> ComposeResult:
        yield Label(f"Speakers — {self.project.project.name}")
        yield DataTable(id="speakers")
        yield Input(placeholder="Name for selected speaker; Enter applies", id="speaker-name")
        yield Label("Esc back — names apply to exports in V2 styling; stored now.", id="sm-hints")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Speaker ID", "Display name")
        for speaker in sorted(self._distinct_speakers()):
            name = self.project.project.speaker_map.get(speaker, "—")
            table.add_row(speaker, name, key=speaker)

    def _distinct_speakers(self) -> set[str]:
        return {s.speaker for s in self.project.segments if s.speaker}

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "speaker-name":
            return
        table = self.query_one(DataTable)
        row = table.cursor_row
        keys = sorted(k.value for k in table.rows if isinstance(k.value, str))
        if 0 <= row < len(keys):
            self.apply_mapping(keys[row], event.value)

    def apply_mapping(self, speaker_id: str, name: str) -> None:
        """Public seam: persist a speaker->name mapping immediately."""
        name = name.strip()
        if not name:
            return
        self.project.project.speaker_map[speaker_id] = name
        save_project(self.project_dir, self.project)
        table = self.query_one("#speakers", DataTable)
        column_keys = list(table.columns)
        table.update_cell(speaker_id, column_keys[1], name)
        self.query_one("#sm-hints", Label).update(f"Mapped {speaker_id} → {name}")

    def action_cancel(self) -> None:
        self.dismiss(None)
