"""Caption review: view/edit segment text + audio preview (PRD §9)."""

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label
from textual.widgets.data_table import ColumnKey

from subforge.app.audio_player import SegmentPlayer
from subforge.app.project_store import load_project, save_project
from subforge.models.project import Segment
from subforge.subtitles.timeutils import format_srt


class CaptionReviewScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+s", "save", "Save"),
        Binding("p", "play", "Play"),
        Binding("x", "stop_audio", "Stop"),
        ("escape", "cancel", "Back"),
    ]

    def __init__(self, project_dir: Path, player: SegmentPlayer | None = None) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.project = load_project(project_dir)
        self.player = player  # wired in on_mount when audio exists
        self._row_ids: list[int] = []  # row order == insertion order (sorted by start)
        self._column_keys: list[ColumnKey] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Caption Review — {self.project.project.name}")
            yield DataTable(id="segments")
            with Horizontal(id="playback"):
                yield Button("▶ Play (p)", id="btn-play")
                yield Button("■ Stop (x)", id="btn-stop")
                yield Label("", id="play-status")
            yield Input(placeholder="Edit text; Enter to apply", id="edit")
            yield Label("Ctrl+S Save · p Play · x Stop · Esc Back", id="hints")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        self._column_keys = table.add_columns("ID", "Time", "Text")
        for seg in sorted(self.project.segments, key=lambda s: s.start):
            table.add_row(str(seg.id), format_srt(seg.start)[:11], seg.source, key=str(seg.id))
            self._row_ids.append(seg.id)
        audio = self.project_dir / "audio"
        candidates = [p for p in sorted(audio.iterdir()) if p.is_file()] if audio.is_dir() else []
        if candidates:
            self.player = player_for(candidates[0])

    def _selected_segment(self) -> Segment | None:
        table = self.query_one(DataTable)
        row = table.cursor_row
        if not (0 <= row < len(self._row_ids)):
            return None
        seg_id = self._row_ids[row]
        return next((s for s in self.project.segments if s.id == seg_id), None)

    # ---- playback seam ------------------------------------------------------

    def play_selected(self) -> str:
        """Public seam: play the highlighted row's time range."""
        if self.player is None or not self.player.available:
            message = (
                "[ERROR] No audio file in project." if self.player is None else str(
                    self.player.play_segment(0.0, 0.0)
                )
            )
            if self.player is None:
                return self._set_play_status(message)
        seg = self._selected_segment()
        if seg is None:
            return self._set_play_status("[ERROR] Select a caption row first.")
        assert self.player is not None
        return self._set_play_status(self.player.play_segment(seg.start, seg.end))

    def stop_playback(self) -> str:
        if self.player is None:
            return "■ stopped"
        return self._set_play_status(self.player.stop())

    def _set_play_status(self, message: str) -> str:
        try:
            self.query_one("#play-status", Label).update(message)
        except NoMatches:
            pass  # pre-mount unit seam
        return message

    # ---- editing ---------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "edit":
            return
        table = self.query_one(DataTable)
        row = table.cursor_row
        if 0 <= row < len(self._row_ids):
            self.apply_edit(self._row_ids[row], event.input.value)

    def apply_edit(self, segment_id: int, text: str) -> None:
        for seg in self.project.segments:
            if seg.id == segment_id:
                seg.source = text
                break
        save_project(self.project_dir, self.project)
        if self._column_keys:
            self.query_one(DataTable).update_cell(str(segment_id), self._column_keys[2], text)

    def action_save(self) -> None:
        save_project(self.project_dir, self.project)
        self.query_one("#hints", Label).update("Saved ✓")

    def action_play(self) -> None:
        self.play_selected()

    def action_stop_audio(self) -> None:
        self.stop_playback()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-play":
            self.play_selected()
        elif event.button.id == "btn-stop":
            self.stop_playback()

    def action_cancel(self) -> None:
        self.dismiss(None)


def player_for(audio_path: Path) -> SegmentPlayer:
    from subforge.app.audio_player import SegmentPlayer as _SP

    return _SP(audio_path)
