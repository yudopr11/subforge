"""Reusable searchable model-selection modal backed by live GET /models.

Shared by transcription (settings + wizard) and translation model picking:
type in the search box to filter the live model list, ↑/↓ to move the
highlight, Enter/Tab to select, Esc to cancel. Selection backs onto the list;
typing a model id with no match and pressing Enter accepts it as a custom model.
"""

from collections.abc import Callable
from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList


class ModelPickerScreen(ModalScreen[str]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    AUTO_FOCUS = "Input"

    def __init__(self, title: str, loader: Callable[[], list[str]]) -> None:
        super().__init__()
        self.picker_title = title
        self.loader = loader
        self.result: str | None = None
        self._all_models: list[str] = []
        self._applied_query = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[b]{self.picker_title}[/b]")
            yield Input(placeholder="type to filter models…", id="model-search")
            yield OptionList(id="models")
            yield Label("[dim]type filter · ↑↓ move · Enter select · Esc cancel[/dim]", id="picker-status")

    def on_mount(self) -> None:
        try:
            models = list(self.loader())
        except Exception as exc:  # noqa: BLE001 — bad key/offline must not crash the picker
            self.query_one("#picker-status", Label).update(
                f"[ERROR] Couldn't load models ({exc}) · Esc cancel"
            )
            return
        self._all_models = models or []
        self._refresh("")

    # ---- filtering ---------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "model-search":
            self._refresh(event.value.strip().lower())

    def _refresh(self, query: str) -> None:
        option_list = self.query_one("#models", OptionList)
        option_list.clear_options()
        if query:
            exact = [m for m in self._all_models if m.lower() == query]
            rest = [
                m
                for m in self._all_models
                if m.lower() != query and (m.lower().startswith(query) or query in m.lower())
            ]
            matches = exact + rest
        else:
            matches = list(self._all_models)
        for model_id in matches:
            option_list.add_option(model_id)
        # Empty search shows the whole catalog but selects nothing on Enter.
        option_list.highlighted = 0 if (matches and query) else None
        self._applied_query = query
        total = len(self._all_models)
        status = f"{len(matches)}/{total} models" if query and len(matches) != total else f"{total} models"
        self.query_one("#picker-status", Label).update(
            f"{status} · type filter · ↑↓ move · Enter select · Esc cancel"
        )

    def _selected_model(self) -> str | None:
        option_list = self.query_one("#models", OptionList)
        if option_list.highlighted is None or option_list.option_count == 0:
            return None
        return str(option_list.get_option_at_index(option_list.highlighted).prompt).strip()

    def _move(self, delta: int) -> None:
        option_list = self.query_one("#models", OptionList)
        count = option_list.option_count
        if count == 0:
            return
        current = option_list.highlighted
        if current is None:
            option_list.highlighted = 0 if delta > 0 else count - 1
        else:
            option_list.highlighted = min(count - 1, max(0, current + delta))

    # ---- key routing -------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            event.stop()
            self._move(-1)
        elif event.key == "down":
            event.stop()
            self._move(1)
        elif event.key == "tab":
            event.stop()
            self._select()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "model-search":
            return
        raw = event.input.value.strip()
        if self._applied_query != raw.lower():
            self._refresh(raw.lower())  # list not yet caught up with the query
        selected = self._selected_model()
        if selected is None and raw:
            selected = raw  # custom model id not present in the live list
        self.result = selected
        self.dismiss(selected)

    def _select(self) -> None:
        selected = self._selected_model()
        if selected is not None:
            self.result = selected
            self.dismiss(selected)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # Test seam + fallback for direct list selection.
        self.result = str(event.option.prompt)
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)
