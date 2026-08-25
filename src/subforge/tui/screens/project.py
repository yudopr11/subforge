"""Project-selection modals: new-from-audio, open-existing, target language.

Pure presentation + input validation; all filesystem orchestration lives in
``app/projects.py`` / ``app/pipeline.py`` (ARCH §3.1).
"""

import re
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

_LANG_RE = re.compile(r"^[a-z]{2,3}$")


class NewProjectScreen(ModalScreen[Path | None]):
    """Type/paste an exported audio file; dismisses with its Path."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "cancel", "Cancel")]

    def __init__(self) -> None:
        super().__init__()
        self.result: Path | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]New project[/b]  —  path to your exported final audio")
            yield Input(placeholder="/path/to/final_audio.wav", id="audio-path")
            yield Label("[dim]Formats: wav flac mp3 m4a aac ogg opus · Esc cancel[/dim]", id="new-project-hints")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.input.value.strip()
        path = Path(raw).expanduser() if raw else None
        if path is None or not path.is_file():
            self.query_one("#new-project-hints", Label).update(
                f"[ERROR] File not found: {raw}" if raw else "[ERROR] Enter a file path."
            )
            return
        if not is_audio_file(path):
            self.query_one("#new-project-hints", Label).update(
                f"[ERROR] Unsupported audio format: {path.suffix or '(none)'}"
            )
            return
        self.result = path
        self.dismiss(path)

    def action_cancel(self) -> None:
        self.dismiss(None)


class OpenProjectScreen(ModalScreen[Path | None]):
    """Type/paste an existing project directory; validates project.json."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "cancel", "Cancel")]

    def __init__(self) -> None:
        super().__init__()
        self.result: Path | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]Open project[/b]  —  path to a project directory")
            yield Input(placeholder="/path/to/projects/my-video", id="project-path")
            yield Label("[dim]Directory must contain project.json · Esc cancel[/dim]", id="open-project-hints")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.input.value.strip()
        path = Path(raw).expanduser() if raw else None
        if path is None or not (path / "project.json").is_file():
            self.query_one("#open-project-hints", Label).update(
                f"[ERROR] Not a SubForge project (no project.json): {raw}" if raw else "[ERROR] Enter a directory."
            )
            return
        self.result = path
        self.dismiss(path)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TargetLanguageScreen(ModalScreen[str | None]):
    """Ask which language to translate into (ISO-ish code, e.g. 'en')."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "cancel", "Cancel")]

    def __init__(self, default: str = "en") -> None:
        super().__init__()
        self.default = default
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]Translate into[/b]  —  language code")
            yield Input(value=self.default, id="target-lang")
            yield Label("[dim]Two/three-letter code (en, ja, es…) · Esc cancel[/dim]", id="target-lang-hints")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        lang = event.input.value.strip().lower()
        if not _LANG_RE.match(lang):
            self.query_one("#target-lang-hints", Label).update(
                f"[ERROR] Invalid language code: {event.input.value!r}"
            )
            return
        self.result = lang
        self.dismiss(lang)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ProjectPickerScreen(ModalScreen[object]):
    """Searchable project picker (recent first) plus a create-new entry.

    Type in the search box to filter by project name, `↑`/`↓` to move the
    highlight, `Enter`/`Tab` to open. Dismisses with:
      - ``Path``  — an existing project directory to open
      - ``NEW``   — user wants to create a new project from audio
      - ``None``  — cancelled
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    AUTO_FOCUS = "Input"

    NEW = "__create-new__"
    _NEW_LABEL = "[+] Create new project from audio…"

    def __init__(self, projects: list[Path]) -> None:
        super().__init__()
        self.projects = projects  # recent first
        self.result: Path | str | None = None
        self._entries: list[tuple[str, Path | None]] = [(self._NEW_LABEL, None)]
        self._entries += [(f"{p.name}   ·   {p}", p) for p in projects]
        self._applied_query = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]Open project[/b]  —  recent projects, or create new")
            yield Input(placeholder="type to search project…", id="project-search")
            yield OptionList(id="projects")
            yield Label("[dim]type filter · ↑↓ move · Enter open · Esc cancel[/dim]", id="picker-hints")

    # ---- filtering ---------------------------------------------------------

    def on_mount(self) -> None:
        self._refresh("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "project-search":
            self._refresh(event.value.strip().lower())

    def _matches(self, entry: tuple[str, Path | None], query: str) -> bool:
        label, path = entry
        if path is None:
            return False  # "+ create new" row only shows without a filter
        return query in path.name.lower() or query in label.lower()

    def _refresh(self, query: str) -> None:
        option_list = self.query_one("#projects", OptionList)
        option_list.clear_options()
        matches = [e for e in self._entries if not query or self._matches(e, query)]
        for label, _path in matches:
            option_list.add_option(label)
        option_list.highlighted = 0 if (matches and query) else None
        self._applied_query = query
        try:
            self.query_one("#picker-hints", Label).update(
                f"{len(matches)}/{len(self._entries)} · type filter · ↑↓ move · Enter open · Esc cancel"
            )
        except NoMatches:
            pass  # pre-mount unit seam

    def _selected_entry(self) -> tuple[str, Path | None] | None:
        option_list = self.query_one("#projects", OptionList)
        if option_list.highlighted is None or option_list.option_count == 0:
            return None
        label = str(option_list.get_option_at_index(option_list.highlighted).prompt).strip()
        for entry in self._entries:
            if entry[0] == label:
                return entry
        return None

    def _dismiss_entry(self, entry: tuple[str, Path | None]) -> None:
        _label, path = entry
        if path is None:
            self.result = self.NEW
            self.dismiss(self.NEW)
        else:
            self.result = path
            self.dismiss(path)

    def _move(self, delta: int) -> None:
        option_list = self.query_one("#projects", OptionList)
        count = option_list.option_count
        if count == 0:
            return
        current = option_list.highlighted
        if current is None:
            option_list.highlighted = 0 if delta > 0 else count - 1
        else:
            option_list.highlighted = min(count - 1, max(0, current + delta))

    def _select(self) -> None:
        entry = self._selected_entry()
        if entry is not None:
            self._dismiss_entry(entry)

    # ---- key routing -------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if event.key in ("up", "down"):
            event.stop()
            self._move(1 if event.key == "down" else -1)
        elif event.key == "tab":
            event.stop()
            self._select()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "project-search":
            return
        raw = event.input.value.strip()
        if self._applied_query != raw.lower():
            self._refresh(raw.lower())  # list not yet caught up with the query
        entry = self._selected_entry()
        if entry is not None:
            self._dismiss_entry(entry)
        else:
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # Test seam + fallback for direct list selection.
        label = str(getattr(event.option, "prompt", ""))
        for entry in self._entries:
            if entry[0] == label:
                self._dismiss_entry(entry)
                return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ChoiceScreen(ModalScreen[str | None]):
    """Generic single-choice prompt; dismisses with the chosen label (or None)."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    def __init__(self, title: str, options: list[str]) -> None:
        super().__init__()
        self.picker_title = title
        self.options = options
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[b]{self.picker_title}[/b]")
            yield OptionList(*self.options, id="choices")
            yield Label("[dim]Enter select · Esc cancel[/dim]", id="choice-hints")

    def choose(self, prompt: str) -> None:
        """Public seam: act on a selection (also used by the event handler)."""
        if prompt in self.options:
            self.result = prompt
            self.dismiss(prompt)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.choose(str(event.option.prompt))

    def action_cancel(self) -> None:
        self.dismiss(None)
