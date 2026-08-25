"""Translation review and export trigger (PRD §10 review step, §13, §23 export).

Same explicit-save editing as caption review: Enter updates the table in
memory, `Ctrl+S` persists, `Ctrl+Z`/`Ctrl+Y` undo/redo (also across saves).
Reviewed language is the one picked by `/review <lang>` (default `en`).
"""

from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label
from textual.widgets.data_table import ColumnKey

from subforge.app.export import export_subtitles
from subforge.app.project_store import load_project, save_project
from subforge.app.translation_service import TranslationService
from subforge.models.project import Segment
from subforge.tui.widgets import EditHistory


class ReviewTranslateScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+z", "undo", "Undo"),
        Binding("ctrl+y", "redo", "Redo"),
        ("escape", "cancel", "Back"),
    ]

    def __init__(
        self,
        project_dir: Path,
        language: str = "en",
        translation_service: TranslationService | None = None,
    ) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.language = language
        self.service = translation_service
        self.on_done: Callable[[list[Path]], None] | None = None
        self.project = load_project(project_dir)
        self._column_keys: list[ColumnKey] = []
        self._history = EditHistory()
        self._dirty = False
        self._esc_armed = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[b]Translation Review[/b]  —  {self.language} · {self.project.project.name}")
            yield DataTable(id="review")
            yield Label("", id="status")
            yield Input(placeholder=f"Fix {self.language} translation; Enter to apply", id="fix")
            yield Label(
                "[dim]Ctrl+S Save · Ctrl+Z Undo · Ctrl+Y Redo · Esc Back[/dim]", id="hints"
            )
            yield Label("", id="export-status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        self._column_keys = table.add_columns("ID", "Source", f"Translation ({self.language})")
        for seg in sorted(self.project.segments, key=lambda s: s.start):
            table.add_row(str(seg.id), seg.source, seg.translations.get(self.language, "—"), key=str(seg.id))
        self._refresh_status()

    # ---- helpers ---------------------------------------------------------------

    def _segment_by_id(self, segment_id: int) -> Segment | None:
        return next((s for s in self.project.segments if s.id == segment_id), None)

    def _set_translation(self, segment_id: int, text: str) -> None:
        seg = self._segment_by_id(segment_id)
        if seg is None:
            return
        seg.translations[self.language] = text
        if self._column_keys:
            self.query_one(DataTable).update_cell(str(segment_id), self._column_keys[2], text)

    def _refresh_status(self) -> None:
        try:
            label = self.query_one("#status", Label)
        except NoMatches:
            return  # pre-mount unit seam
        if self._dirty:
            n = self._history.count
            label.update(f"[yellow]●[/yellow] {n} unsaved edit{'s' if n != 1 else ''} — Ctrl+S to save")
        else:
            label.update("[green]✓[/green] all saved")

    def _set_status(self, message: str) -> None:
        try:
            self.query_one("#status", Label).update(message)
        except NoMatches:
            pass

    # ---- editing (memory only until Ctrl+S) -------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "fix":
            return
        table = self.query_one(DataTable)
        row = table.cursor_row
        seg = next((self.project.segments[i] for i in (row,) if 0 <= row < len(self.project.segments)), None)
        if seg is not None:
            self.apply_edit(seg.id, self.language, event.input.value)
            event.input.clear()

    def apply_edit(self, segment_id: int, language: str, text: str) -> None:
        """Apply an edit to the in-memory project + table; NOT saved yet."""
        if language != self.language:
            return  # this screen reviews exactly one language
        seg = self._segment_by_id(segment_id)
        if seg is None or seg.translations.get(language) == text:
            return
        self._history.record(segment_id, seg.translations.get(language, ""), text)
        self._set_translation(segment_id, text)
        self._dirty = True
        self._refresh_status()

    # ---- undo / redo ------------------------------------------------------------

    def action_undo(self) -> None:
        record = self._history.undo()
        if record is None:
            self._set_status("nothing to undo")
            return
        self._set_translation(record.segment_id, record.old_text)
        self._dirty = True
        self._refresh_status()

    def action_redo(self) -> None:
        record = self._history.redo()
        if record is None:
            self._set_status("nothing to redo")
            return
        self._set_translation(record.segment_id, record.new_text)
        self._dirty = True
        self._refresh_status()

    # ---- save / exit ---------------------------------------------------------------

    def action_save(self) -> None:
        save_project(self.project_dir, self.project)
        self._dirty = False
        self._esc_armed = False
        self._set_status(
            f"[green]✓[/green] saved — {self._history.count} edits in this session · "
            "Ctrl+Z to undo"
        )

    def action_cancel(self) -> None:
        if self._dirty and not self._esc_armed:
            self._esc_armed = True
            self._set_status("[red]⚠[/red] unsaved changes — Ctrl+S to save, Esc again to discard")
            return
        self.dismiss(None)

    def do_export(self, formats: list[str], languages: list[str]) -> list[Path]:
        paths = export_subtitles(self.project_dir, formats=formats, languages=languages)
        self.query_one("#export-status", Label).update("Exported: " + ", ".join(p.name for p in paths))
        if self.on_done:
            self.on_done(paths)
        return paths