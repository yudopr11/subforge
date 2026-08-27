"""Reusable confirmation dialog modal screen."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmDialogScreen(ModalScreen[bool]):
    """Modal dialog asking for Yes/No confirmation."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("y", "confirm", "Yes"),
        Binding("enter", "confirm", "Confirm"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    AUTO_FOCUS = "#btn-confirm"

    def __init__(
        self,
        title: str = "Confirm Action",
        message: str = "Are you sure you want to proceed?",
    ) -> None:
        super().__init__()
        self.dialog_title = title
        self.dialog_message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog-container"):
            yield Label(f"[b]{self.dialog_title}[/b]", id="confirm-title")
            yield Label(self.dialog_message, id="confirm-message")
            with Horizontal(id="confirm-button-bar"):
                yield Button("Yes [y / Enter]", id="btn-confirm", variant="error")
                yield Button("Cancel [n / Esc]", id="btn-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        elif event.button.id == "btn-cancel":
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
