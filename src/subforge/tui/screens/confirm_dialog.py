"""Reusable confirmation dialog modal screen."""

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmDialogScreen(ModalScreen[bool]):
    """Modal dialog asking for Yes/No confirmation with arrow navigation."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
        Binding("left", "focus_left", "Left", show=False),
        Binding("right", "focus_right", "Right", show=False),
        Binding("h", "focus_left", "Left", show=False),
        Binding("l", "focus_right", "Right", show=False),
        Binding("enter", "submit_focused", "Select", show=False),
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
                yield Button("Yes [y]", id="btn-confirm", variant="error")
                yield Button("Cancel [n / Esc]", id="btn-cancel", variant="default")
            yield Label(
                "[dim]← / →: switch · Enter: select · y: yes · n / Esc: cancel[/dim]",
                id="confirm-hints",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        elif event.button.id == "btn-cancel":
            self.dismiss(False)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("left", "h"):
            event.stop()
            self.action_focus_left()
        elif event.key in ("right", "l"):
            event.stop()
            self.action_focus_right()

    def action_focus_left(self) -> None:
        try:
            self.query_one("#btn-confirm", Button).focus()
        except Exception:  # noqa: BLE001, S110
            pass

    def action_focus_right(self) -> None:
        try:
            self.query_one("#btn-cancel", Button).focus()
        except Exception:  # noqa: BLE001, S110
            pass

    def action_submit_focused(self) -> None:
        focused = self.focused or self.app.focused
        if focused and getattr(focused, "id", None) == "btn-cancel":
            self.dismiss(False)
        else:
            self.dismiss(True)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

