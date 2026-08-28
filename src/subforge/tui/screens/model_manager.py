"""Local Whisper model management UI (PRD §8): cache status + on-demand install + model selection."""

from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label

from subforge.app.model_manager import LocalModelInfo, LocalModelManager


class ModelManagerScreen(ModalScreen[str | None]):
    AUTO_FOCUS = "#models"
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select_or_install_action", "Select / Install"),
        ("i", "install_selected_action", "Install only"),
        ("d", "delete_selected_action", "Delete"),
        ("delete", "delete_selected_action", "Delete"),
    ]

    def __init__(
        self,
        manager: LocalModelManager | None = None,
        current_model: str | None = None,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.manager = manager or LocalModelManager()
        self.current_model = current_model
        self.on_done = on_done

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]Local Whisper Models (whisper.cpp)[/b]")
            yield DataTable(id="models", cursor_type="row")
            with Horizontal(id="mm-buttons"):
                yield Button("Select / Install  [Enter]", id="btn-select", variant="primary")
                yield Button("Install only  [i]", id="btn-install")
                yield Button("Delete  [d / Del]", id="btn-delete", variant="error")
            yield Label(
                "[dim]Enter: select (auto-installs if needed) · i: install · d / Del: delete · ↑↓: move · Esc: cancel[/dim]",
                id="mm-hints",
            )
            yield Label("", id="mm-status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Model", "Profile", "VRAM / Size", "Status")
        self._rows: list[LocalModelInfo] = []
        self.refresh_rows()
        if self.current_model and self._rows:
            for idx, info in enumerate(self._rows):
                if info.id == self.current_model:
                    table.cursor_coordinate = Coordinate(idx, 0)
                    break

    # ---- tested seams ----------------------------------------------------

    def list_models(self) -> list[LocalModelInfo]:
        return self.manager.list_models()

    def refresh_rows(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._rows = self.list_models()
        for info in self._rows:
            name_display = f"{info.id} [b][green][RECOMMENDED][/green][/b]" if info.recommended else info.id
            status_display = "installed" if info.installed else "not installed"
            table.add_row(
                name_display,
                info.profile,
                f"{info.vram}, {info.size}",
                status_display,
                key=info.id,
            )

    def install(self, model_id: str) -> str:
        self._set_status(f"Starting download for {model_id}...")

        def _on_progress(downloaded: int, total: int) -> None:
            if total > 0:
                pct = int(downloaded / total * 100)
                dl_mb = downloaded / (1024 * 1024)
                tot_mb = total / (1024 * 1024)
                msg = f"Downloading {model_id}: {dl_mb:.1f} MB / {tot_mb:.1f} MB ({pct}%)"
            else:
                dl_mb = downloaded / (1024 * 1024)
                msg = f"Downloading {model_id}: {dl_mb:.1f} MB..."
            try:
                self.app.call_from_thread(self._set_status, msg)
            except Exception:  # noqa: BLE001
                self._set_status(msg)

        try:
            self.manager.install(model_id, progress_callback=_on_progress)
        except ValueError as exc:
            self._set_status(str(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"[ERROR] {exc}")
            return f"[ERROR] {exc}"

        try:
            self.app.call_from_thread(self.refresh_rows)
        except Exception:  # noqa: BLE001
            self.refresh_rows()

        message = f"✓ {model_id} installed successfully."
        try:
            self.app.call_from_thread(self._set_status, message)
        except Exception:  # noqa: BLE001
            self._set_status(message)

        if self.on_done:
            try:
                self.app.call_from_thread(self.on_done)
            except Exception:  # noqa: BLE001
                self.on_done()
        return message

    def _install_worker(self, model_id: str, dismiss_on_success: bool = False) -> str:
        msg = self.install(model_id)
        if dismiss_on_success and not msg.startswith("[ERROR]"):
            try:
                self.app.call_from_thread(self.dismiss, model_id)
            except Exception:  # noqa: BLE001
                self.dismiss(model_id)
        return msg

    def select_or_install(self) -> None:
        table = self.query_one(DataTable)
        row = table.cursor_row
        if row is None or not (0 <= row < len(self._rows)):
            self._set_status("[ERROR] Select a model row first.")
            return
        selected_info = self._rows[row]
        if not selected_info.installed:
            if hasattr(self.app, "download_model_background"):
                self.app.download_model_background(selected_info.id, self.manager)
            else:
                self.run_worker(
                    lambda: self.manager.install(selected_info.id),
                    thread=True,
                    group="model_download",
                )

        if self.on_done:
            try:
                self.app.call_from_thread(self.on_done)
            except Exception:  # noqa: BLE001
                self.on_done()
        self.dismiss(selected_info.id)

    def install_selected(self) -> str:
        table = self.query_one(DataTable)
        row = table.cursor_row
        if row is None or not (0 <= row < len(self._rows)):
            self._set_status("[ERROR] Select a model row first.")
            return "[ERROR] Select a model row first."
        selected_model = self._rows[row].id
        self.run_worker(
            lambda: self._install_worker(selected_model, dismiss_on_success=False),
            thread=True,
            exclusive=True,
            group="install",
        )
        return f"Starting download for {selected_model}..."

    def delete(self, model_id: str) -> str:
        deleted = self.manager.delete_model(model_id)
        if not deleted:
            msg = f"[ERROR] Failed to delete model {model_id} (not found or in use)."
            self._set_status(msg)
            return msg

        try:
            self.app.call_from_thread(self.refresh_rows)
        except Exception:  # noqa: BLE001
            self.refresh_rows()

        message = f"✓ {model_id} deleted successfully."
        try:
            self.app.call_from_thread(self._set_status, message)
        except Exception:  # noqa: BLE001
            self._set_status(message)

        if self.on_done:
            try:
                self.app.call_from_thread(self.on_done)
            except Exception:  # noqa: BLE001
                self.on_done()
        return message

    def delete_selected(self) -> None:
        table = self.query_one(DataTable)
        row = table.cursor_row
        if row is None or not (0 <= row < len(self._rows)):
            self._set_status("[ERROR] Select a model row first.")
            return
        selected_info = self._rows[row]
        if not selected_info.installed:
            self._set_status(f"[WARN] Model '{selected_info.id}' is not installed.")
            return

        from subforge.tui.screens.confirm_dialog import ConfirmDialogScreen

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self.delete(selected_info.id)

        self.app.push_screen(
            ConfirmDialogScreen(
                title="Delete Local Model",
                message=f"Permanently delete GGML model '{selected_info.id}' ({selected_info.size}) from disk?",
            ),
            on_confirm,
        )

    def _set_status(self, message: str) -> None:
        try:
            label = self.query_one("#mm-status", Label)
            label.update(message)
        except Exception:  # noqa: BLE001, S110
            pass

    # ---- widget wiring ------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-select":
            self.select_or_install()
        elif event.button.id == "btn-install":
            self.install_selected()
        elif event.button.id == "btn-delete":
            self.delete_selected()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.select_or_install()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select_or_install_action(self) -> None:
        self.select_or_install()

    def action_install_selected_action(self) -> None:
        self.install_selected()

    def action_delete_selected_action(self) -> None:
        self.delete_selected()


