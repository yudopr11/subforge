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
