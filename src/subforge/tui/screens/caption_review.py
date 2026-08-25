"""Caption review: view/edit segment text (PRD §9, MVP subset of §23 editing)."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label

from subforge.app.project_store import load_project, save_project
from subforge.subtitles.timeutils import format_srt


class CaptionReviewScreen(Screen):
    BINDINGS = [Binding("ctrl+s", "save", "Save")]

    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.project = load_project(project_dir)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Caption Review — {self.project.project.name}")
            yield DataTable(id="segments")
            yield Input(placeholder="Edit text; Enter to apply", id="edit")
            yield Label("Ctrl+S Save   ↑↓ Navigate", id="hints")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        self._columns = table.add_columns("ID", "Time", "Text")
        for seg in sorted(self.project.segments, key=lambda s: s.start):
            table.add_row(str(seg.id), format_srt(seg.start)[:11], seg.source, key=str(seg.id))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "edit":
            return
        table = self.query_one(DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_cell).row_key
        if row_key is not None and row_key.value is not None:
            self.apply_edit(int(row_key.value), event.input.value)

    def apply_edit(self, segment_id: int, text: str) -> None:
        for seg in self.project.segments:
            if seg.id == segment_id:
                seg.source = text
                break
        save_project(self.project_dir, self.project)
        table = self.query_one(DataTable)
        table.update_cell(str(segment_id), self._columns[2], text)

    def action_save(self) -> None:
        save_project(self.project_dir, self.project)
        self.query_one("#hints", Label).update("Saved ✓")
