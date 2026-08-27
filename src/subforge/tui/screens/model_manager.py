"""Local Whisper model management UI (PRD §8): cache status + on-demand install."""

from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label

from subforge.app.model_manager import LocalModelInfo, LocalModelManager


class ModelManagerScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
        ("i", "install_selected_action", "Install"),
    ]

    def __init__(
        self,
        manager: LocalModelManager | None = None,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.manager = manager or LocalModelManager()
        self.on_done = on_done

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]Local Whisper models[/b]")
            yield DataTable(id="models")
            yield Button("Install selected  [i]", id="btn-install")
            yield Label("[dim]i install · ↑↓ select · esc back[/dim]", id="mm-hints")
            yield Label("", id="mm-status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Model", "Profile", "VRAM", "Installed")
        self._rows: list[LocalModelInfo] = []
        self.refresh_rows()

    # ---- tested seams ----------------------------------------------------

    def list_models(self) -> list[LocalModelInfo]:
        return self.manager.list_models()

    def refresh_rows(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._rows = self.list_models()
        for info in sorted(self._rows, key=lambda i: i.id):
            table.add_row(
                info.id,
                info.profile,
                info.vram,
                "installed" if info.installed else "not installed",
                key=info.id,
            )

    def install(self, model_id: str) -> str:
        try:
            self.manager.install(model_id)
        except ValueError as exc:
            self._set_status(str(exc))
            raise
        except RuntimeError as exc:  # missing [local] extra
            self._set_status(f"[ERROR] {exc}")
            return f"[ERROR] {exc}"
        self.refresh_rows()
        message = f"{model_id} installed."
        self._set_status(message)
        if self.on_done:
            self.on_done()
        return message

    def install_selected(self) -> str:
        table = self.query_one(DataTable)
        row = table.cursor_row
        ordered = sorted(i.id for i in self._rows)
        if not (0 <= row < len(ordered)):
            return "[ERROR] Select a model row first."
        return self.install(ordered[row])

    def _set_status(self, message: str) -> None:
        label = self.query_one("#mm-status", Label)
        label.update(message)

    # ---- widget wiring ------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-install":
            self.run_worker(self.install_selected, thread=True, exclusive=True, group="install")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_install_selected_action(self) -> None:
        self.run_worker(self.install_selected, thread=True, exclusive=True, group="install")
