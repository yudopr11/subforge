"""Review picker overlay — searchable list of what can be reviewed (PRD §7).

Bare ``/review`` shows captions plus one entry per language that has at least
one translated segment; typing filters, ``↑``/``↓`` move, ``Enter`` opens.
Dismisses with ``CAPTIONS``, a language code, or ``None`` (cancelled).
"""

from pathlib import Path
from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList

from subforge.app.project_store import load_project


class ReviewPickerScreen(ModalScreen[str | None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    AUTO_FOCUS = "Input"

    CAPTIONS = "__captions__"

    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project = load_project(project_dir)
        # entries: (label, value) — captions + languages with translated segments
        self._entries: list[tuple[str, str]] = [
            ("✎ Captions — source text (edit + audio preview)", self.CAPTIONS)
        ]
        for lang in self.project.project.target_languages:
            n = sum(1 for seg in self.project.segments if lang in seg.translations)
            if n:
                self._entries.append((f"⇄ Translation · {lang}  —  {n} segments", lang))
        self.result: str | None = None
        self._applied_query = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                f"[b]Review[/b]  —  {self.project.project.name} · {len(self._entries) - 1} translated"
            )
            yield Input(placeholder="type to search captions or a language…", id="review-search")
            yield OptionList(id="review-options")
            yield Label("[dim]type filter · ↑↓ move · Enter open · Esc cancel[/dim]", id="picker-hints")

    # ---- filtering ---------------------------------------------------------

    def on_mount(self) -> None:
        self._refresh("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "review-search":
            self._refresh(event.value.strip().lower())

    def _matches(self, label: str, value: str, query: str) -> bool:
        return query in label.lower() or query in value.lower()

    def _refresh(self, query: str) -> None:
        option_list = self.query_one("#review-options", OptionList)
        option_list.clear_options()
        matches = [e for e in self._entries if not query or self._matches(*e, query)]
        for label, _value in matches:
            option_list.add_option(label)
        option_list.highlighted = 0 if matches else None
        self._applied_query = query
        try:
            self.query_one("#picker-hints", Label).update(
                f"{len(matches)}/{len(self._entries)} · type filter · ↑↓ move · Enter open · Esc cancel"
            )
        except NoMatches:
            pass  # pre-mount unit seam

    def _selected_value(self) -> str | None:
        option_list = self.query_one("#review-options", OptionList)
        if option_list.highlighted is None or option_list.option_count == 0:
            return None
        label = str(option_list.get_option_at_index(option_list.highlighted).prompt).strip()
        for entry_label, value in self._entries:
            if entry_label == label:
                return value
        return None

    # ---- key routing -------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if event.key in ("up", "down"):
            event.stop()
            option_list = self.query_one("#review-options", OptionList)
            count = option_list.option_count
            if count == 0:
                return
            current = option_list.highlighted
            if current is None:
                option_list.highlighted = 0 if event.key == "down" else count - 1
            else:
                option_list.highlighted = min(count - 1, max(0, current + (1 if event.key == "down" else -1)))
        elif event.key == "tab":
            event.stop()
            self._select()

    def _select(self) -> None:
        value = self._selected_value()
        if value is not None:
            self.result = value
            self.dismiss(value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "review-search":
            return
        raw = event.input.value.strip()
        if self._applied_query != raw.lower():
            self._refresh(raw.lower())
        self._select()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # Test seam + fallback for direct list selection.
        label = str(getattr(event.option, "prompt", ""))
        for entry_label, value in self._entries:
            if entry_label == label:
                self.result = value
                self.dismiss(value)
                return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)