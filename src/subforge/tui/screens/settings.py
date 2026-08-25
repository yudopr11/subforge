"""Setup & Settings: local/provider choice, key entry, model + reasoning picks.

All network access goes through provider objects' list_models(); this module
only orchestrates screens and writes AppConfig. Keys are masked, never logged.
"""

from collections.abc import Callable

from textual.app import ComposeResult
from textual.screen import ModalScreen, Screen
from textual.widgets import Input, Label

from subforge.app.provider_factory import validate_reasoning_choice
from subforge.config.app_config import AppConfig, save_app_config
from subforge.providers.capabilities import ReasoningSpec


def refresh_reasoning(current: str, spec: ReasoningSpec) -> str:
    """Drop a stored reasoning value that the current model no longer offers."""
    return validate_reasoning_choice(spec, current)


class ApiKeyInputScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str) -> None:
        super().__init__()
        self.picker_title = title
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(f"[b]{self.picker_title}[/b]")
        yield Input(password=True, placeholder="paste API key, Enter to confirm")
        yield Label("Esc cancel — stored locally in ~/.config/subforge/config.json")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.result = event.input.value.strip() or None
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ReasoningPickerScreen(ModalScreen[str | None]):
    """Offers EXACTLY the effort values discovered for the selected model."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, spec: ReasoningSpec) -> None:
        super().__init__()
        self.spec = spec
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        from textual.widgets import OptionList  # noqa: PLC0415 — keeps module import light

        yield Label("[b]Reasoning effort[/b] — values provided by the model")
        yield OptionList(*self.spec.values, id="reasoning")
        yield Label("Esc = send without reasoning parameter")

    def on_option_list_option_selected(self, event: object) -> None:
        option = getattr(event, "option", None)
        if option is not None:
            self.result = str(option.prompt)
            self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SettingsScreen(Screen):
    """Interactive configuration; state transitions per revision 2026-08-25:

      Transcribe:  [Local|Provider]
        Local    -> LocalModelManager.list_models() table (Install action) -> pick model
        Provider -> ApiKeyInputScreen -> ModelPickerScreen(openai.list_models)
      Translate:   [Local|Provider]
        Local    -> edit base URL -> ModelPickerScreen(OpenAICompatibleProvider(url, "").list_models)
        Provider -> pick openai|opencode-zen|opencode-go -> ApiKeyInputScreen
                 -> ModelPickerScreen -> ReasoningPickerScreen (only if spec.kind == "effort")
      Model changed -> cfg.translation.reasoning_effort = refresh_reasoning(old, new_spec)
      Save -> save_app_config(cfg) -> on_saved() rebuilds providers mid-session.

    The full interactive widget tree lands with the UI-focused follow-up plan;
    the tested contracts (modals above, refresh_reasoning, save_config) are complete here.
    """

    def __init__(self, app_config: AppConfig, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.cfg = app_config
        self.on_saved = on_saved

    def compose(self) -> ComposeResult:
        yield Label("[b]SubForge Settings[/b] — changes apply immediately, no restart needed")

    def save_config(self) -> None:
        save_app_config(self.cfg)
        if self.on_saved:
            self.on_saved()
