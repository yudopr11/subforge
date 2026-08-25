"""Translation review and export trigger (PRD §10 review step, §23 export)."""

from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label
from textual.widgets.data_table import ColumnKey

from subforge.app.export import export_subtitles
from subforge.app.project_store import load_project, save_project
from subforge.app.translation_service import TranslationService


class ReviewTranslateScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "cancel", "Back")]

    def __init__(self, project_dir: Path, translation_service: TranslationService | None = None) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.service = translation_service
        self.on_done: Callable[[list[Path]], None] | None = None
        self.project = load_project(project_dir)
        self._column_keys: list[ColumnKey] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Translation Review")
            yield DataTable(id="review")
            yield Input(placeholder="Fix translation; Enter applies to selected row", id="fix")
            yield Label("", id="export-status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        self._column_keys = table.add_columns("ID", "Source", "Translation")
        for seg in sorted(self.project.segments, key=lambda s: s.start):
            table.add_row(str(seg.id), seg.source, seg.translations.get("en", "—"), key=str(seg.id))

    def apply_edit(self, segment_id: int, language: str, text: str) -> None:
        for seg in self.project.segments:
            if seg.id == segment_id:
                seg.translations[language] = text
                break
        save_project(self.project_dir, self.project)
        if language == "en":
            table = self.query_one("#review", DataTable)
            table.update_cell(str(segment_id), self._column_keys[2], text)

    def do_export(self, formats: list[str], languages: list[str]) -> list[Path]:
        paths = export_subtitles(self.project_dir, formats=formats, languages=languages)
        self.query_one("#export-status", Label).update("Exported: " + ", ".join(p.name for p in paths))
        if self.on_done:
            self.on_done(paths)
        return paths

    def action_cancel(self) -> None:
        self.dismiss(None)
