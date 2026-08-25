"""Audio file picker overlay — searchable browse for /new locate mode (PRD §7).

Type in the search box to filter the discovered audio files by name or folder,
`↑`/`↓` to move the highlight, `Enter`/`Tab` to pick. When nothing matches,
typing a full path that exists is accepted directly; otherwise the pinned
"type a file path" row (or Esc) hands off to the REPL's locate-mode prompt.
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

from subforge.app.projects import is_audio_file


class AudioFilePickerScreen(ModalScreen[str | None]):
    """Lists candidate audio files; Enter dismisses with an absolute path."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    AUTO_FOCUS = "Input"

    #: Dismissed when the user wants to type a path manually instead.
    PATH_ENTRY = "__type-path__"
    _PATH_LABEL = "⌨ Type a file path instead…"

    def __init__(self, files: list[Path], title: str = "Locate audio") -> None:
        super().__init__()
        self.files = files
        self.picker_title = title
        self.result: str | None = None
        self._applied_query = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[b]{self.picker_title}[/b]  —  {len(self.files)} audio file(s)")
            yield Input(placeholder="type to search audio… (or a full path)", id="audio-search")
            yield OptionList(id="audio-files")
            yield Label("[dim]type filter · ↑↓ move · Enter pick · ⌨ row types a path · Esc cancel[/dim]", id="picker-hints")

    # ---- filtering ---------------------------------------------------------

    def on_mount(self) -> None:
        self._refresh("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "audio-search":
            self._refresh(event.value.strip().lower())

    def _matches(self, path: Path, query: str) -> bool:
        return query in path.name.lower() or query in str(path.parent).lower()

    def _refresh(self, query: str) -> None:
        option_list = self.query_one("#audio-files", OptionList)
        option_list.clear_options()
        matches = [p for p in self.files if not query or self._matches(p, query)]
        option_list.add_option(self._PATH_LABEL)  # pinned first: always reachable (↑ from row 1)
        for p in matches:
            option_list.add_option(f"{p.name}   ·   {p.parent}")
        option_list.highlighted = 1 if matches else 0  # first FILE match, else the path row
        self._applied_query = query
        try:
            self.query_one("#picker-hints", Label).update(
                f"{len(matches)}/{len(self.files)} · type filter · ↑↓ move · Enter pick · "
                f"⌨ row types a path · Esc cancel"
            )
        except NoMatches:
            pass  # pre-mount unit seam

    def _selected_entry(self) -> Path | None:
        option_list = self.query_one("#audio-files", OptionList)
        if option_list.highlighted is None or option_list.option_count == 0:
            return None
        label = str(option_list.get_option_at_index(option_list.highlighted).prompt).strip()
        if label == self._PATH_LABEL:
            return None  # the pinned path row
        for path in self.files:
            if label.startswith(path.name + " "):
                return path
        return None

    def _dismiss_path(self, path: Path) -> None:
        chosen = str(path.resolve())
        self.result = chosen
        self.dismiss(chosen)

    def _move(self, delta: int) -> None:
        option_list = self.query_one("#audio-files", OptionList)
        count = option_list.option_count
        if count == 0:
            return
        current = option_list.highlighted
        if current is None:
            option_list.highlighted = 0 if delta > 0 else count - 1
        else:
            option_list.highlighted = min(count - 1, max(0, current + delta))

    def _select(self) -> None:
        """Enter/Tab: pick the highlighted file, or hand off to path typing."""
        path = self._selected_entry()
        if path is not None:
            self._dismiss_path(path)
            return
        raw = self.query_one("#audio-search", Input).value.strip()
        candidate = Path(raw).expanduser()
        if raw and candidate.is_file() and is_audio_file(candidate):
            self._dismiss_path(candidate)  # a typed path that exists: accept it directly
            return
        self.result = self.PATH_ENTRY
        self.dismiss(self.PATH_ENTRY)

    # ---- key routing -------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if event.key in ("up", "down"):
            event.stop()
            self._move(1 if event.key == "down" else -1)
        elif event.key == "tab":
            event.stop()
            self._select()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "audio-search":
            return
        raw = event.input.value.strip()
        if self._applied_query != raw.lower():
            self._refresh(raw.lower())  # list not yet caught up with the query
        self._select()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # Test seam + fallback for direct list selection.
        label = str(getattr(event.option, "prompt", ""))
        for path in self.files:
            if label.startswith(path.name + " "):
                self._dismiss_path(path)
                return
        self._select()

    def action_cancel(self) -> None:
        self.dismiss(None)