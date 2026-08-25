"""Audio file picker overlay — the ``@`` browse for /new locate mode (PRD §7)."""

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList


class AudioFilePickerScreen(ModalScreen[str | None]):
    """Lists candidate audio files; Enter returns the selected absolute path."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel")
    ]

    def __init__(self, files: list[Path], title: str = "Locate audio") -> None:
        super().__init__()
        self.files = files
        self.picker_title = title
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(f"[b]{self.picker_title}[/b] — {len(self.files)} audio file(s)")
        if self.files:
            yield OptionList(
                *[f"{p.name}   ·   {p.parent}" for p in self.files], id="audio-files"
            )
        else:
            yield Label("No audio files found here — cancel and type a full path.", id="empty")
        yield Label("↑↓ select · Enter pick · Esc cancel", id="picker-hints")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        prompt = str(getattr(event.option, "prompt", ""))
        for f in self.files:
            if prompt.startswith(f.name + " ") or prompt == f.name:
                chosen = str(f.resolve())
                self.result = chosen
                self.dismiss(chosen)
                return

    def action_cancel(self) -> None:
        self.dismiss(None)
