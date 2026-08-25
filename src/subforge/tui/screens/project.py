"""Project-selection modals: new-from-audio, open-existing, target language.

Pure presentation + input validation; all filesystem orchestration lives in
``app/projects.py`` / ``app/pipeline.py`` (ARCH §3.1).
"""

import re
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
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
        yield Label("[b]New project[/b] — path to your exported final audio")
        yield Input(placeholder="/path/to/final_audio.wav", id="audio-path")
        yield Label(f"Formats: {', '.join(sorted(is_audio_file.__doc__ or ''))}wav flac mp3 m4a aac ogg opus · Esc cancel", id="new-project-hints")

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
        yield Label("[b]Open project[/b] — path to a project directory")
        yield Input(placeholder="/path/to/projects/my-video", id="project-path")
        yield Label("Directory must contain project.json · Esc cancel", id="open-project-hints")

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
        yield Label("[b]Translate into[/b] — language code")
        yield Input(value=self.default, id="target-lang")
        yield Label("Two/three-letter code (en, ja, es…) · Esc cancel", id="target-lang-hints")

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
    """Lists existing projects (recent first) plus a create-new entry.

    Dismisses with:
      - ``Path``  — an existing project directory to open
      - ``NEW``   — user wants to create a new project from audio
      - ``None``  — cancelled
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    NEW = "__create-new__"

    def __init__(self, projects: list[Path]) -> None:
        super().__init__()
        self.projects = projects
        self.result: Path | str | None = None

    def compose(self) -> ComposeResult:
        yield Label("[b]Open project[/b] — recent projects, or create new")
        yield OptionList(
            "[+] Create new project from audio…",
            *[f"{p.name}   ·   {p}" for p in self.projects],
            id="projects",
        )
        yield Label("Enter select · Esc cancel", id="picker-hints")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        prompt = str(getattr(event.option, "prompt", ""))
        if prompt.startswith("[+]"):
            self.result = self.NEW
            self.dismiss(self.NEW)
            return
        for path in self.projects:
            if prompt.startswith(path.name + " "):
                self.result = path
                self.dismiss(path)
                return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
