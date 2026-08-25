"""Reusable model-selection modal backed by live GET /models discovery."""

from collections.abc import Callable

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList


class ModelPickerScreen(ModalScreen[str]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, loader: Callable[[], list[str]]) -> None:
        super().__init__()
        self.picker_title = title
        self.loader = loader
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(f"[b]{self.picker_title}[/b]")
        yield OptionList(id="models")
        yield Label("Loading models…", id="picker-status")

    def on_mount(self) -> None:
        models = self.loader()  # sync; move into run_worker(thread=True) if slow in practice
        option_list = self.query_one("#models", OptionList)
        if not models:
            self.query_one("#picker-status", Label).update(
                "No models found — check your API key / server URL"
            )
            return
        for model_id in models:
            option_list.add_option(model_id)
        status = self.query_one("#picker-status", Label)
        status.update(f"{len(models)} models · Enter select · Esc cancel")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.result = str(event.option.prompt)
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)
