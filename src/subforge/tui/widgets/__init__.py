"""Shared TUI widgets (Pi-style keyboard-first primitives)."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.selection import Selection
from textual.strip import Strip
from textual.widgets import RichLog


class SelectableRichLog(RichLog):
    """A RichLog whose transcript text is drag-selectable, highlighted and copyable.

    Plain ``RichLog`` advertises ``ALLOW_SELECT`` but renders no ``offset``
    style metadata, so Textual's compositor never computes content offsets and
    ``get_selected_text()`` always comes back empty. This subclass attaches the
    ``offset`` meta via ``Strip.apply_offsets`` at render time, paints the live
    ``screen--selection`` highlight over the dragged span, and extracts the
    selected text from its own stored lines — making drag-select + Ctrl+C copy
    work over the transcript (PRD §7 interaction model).
    """

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        content_y = scroll_y + y
        line = self._render_line(content_y, scroll_x, self.scrollable_content_region.width)
        line = line.apply_style(self.rich_style)
        # Attach per-segment content offsets so pointer hits map to real cells.
        line = line.apply_offsets(0, content_y)
        return self._apply_selection_style(line, content_y)

    def _apply_selection_style(self, strip: Strip, content_y: int) -> Strip:
        """Paint the selection highlight over this content line (like ``Log``)."""
        selection = self.text_selection
        if selection is None:
            return strip
        span = selection.get_span(content_y)
        if span is None:
            return strip
        start, end = span
        text = Text()
        for seg in strip:
            text.append(seg.text, seg.style)
        if end == -1 or end > len(text):
            end = len(text)
        selection_style = self.screen.get_component_rich_style("screen--selection")
        if selection_style is not None and start < end:
            text.stylize(selection_style, start, end)
        return Strip(list(text.render(self.app.console)), strip.cell_length)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Right-click copies the current selection (terminal UX)."""
        if event.button != 3:
            return  # left/middle clicks behave normally (screen-level selection)
        text = self.screen.get_selected_text()
        if text:
            self.app.copy_to_clipboard(text)
            self.screen.clear_selection()  # also drops the pending drag-start state
            self.app.notify("Copied to clipboard")
        else:
            self.app.notify("Nothing selected — drag the mouse over the transcript first")
        event.stop()

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        text = "\n".join("".join(seg.text for seg in strip) for strip in self.lines)
        return selection.extract(text), "\n"


class EditRecord:
    """One captured edit: what changed (id, old text -> new text)."""

    __slots__ = ("new_text", "old_text", "segment_id")

    def __init__(self, segment_id: int, old_text: str, new_text: str) -> None:
        self.segment_id = segment_id
        self.old_text = old_text
        self.new_text = new_text


class EditHistory:
    """In-memory undo/redo stack for review screens (PRD §9).

    Edits are recorded on apply; undo/redo move a pointer over the records and
    return the record whose ``old_text`` (undo) or ``new_text`` (redo) restores
    the state. A fresh edit truncates the redo tail.
    """

    __slots__ = ("_pos", "_records")

    def __init__(self) -> None:
        self._records: list[EditRecord] = []
        self._pos = 0

    @property
    def count(self) -> int:
        return self._pos

    def can_undo(self) -> bool:
        return self._pos > 0

    def can_redo(self) -> bool:
        return self._pos < len(self._records)

    def record(self, segment_id: int, old_text: str, new_text: str) -> None:
        if old_text == new_text:
            return
        del self._records[self._pos :]
        self._records.append(EditRecord(segment_id, old_text, new_text))
        self._pos += 1

    def undo(self) -> EditRecord | None:
        if not self.can_undo():
            return None
        self._pos -= 1
        return self._records[self._pos]

    def redo(self) -> EditRecord | None:
        if not self.can_redo():
            return None
        record = self._records[self._pos]
        self._pos += 1
        return record
