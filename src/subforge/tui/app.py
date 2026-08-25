"""Textual application root. Presentation only — logic lives in app/* (ARCH §3.1)."""

from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from subforge.config.app_config import AppConfig, is_first_run, load_app_config
from subforge.tui.screens.repl import ReplScreen
from subforge.tui.screens.setup_wizard import FirstRunSetupScreen


class SubForgeApp(App[None]):
    TITLE = "SUBFORGE"

    CSS = """
    /* ════ Pi Coding Tools visual language ════
       Dark terminal aesthetic: near-black backgrounds, cyan accent (#00aaff),
       muted grays for secondary text, green/red for status, minimal borders.
    */

    /* ---- global color tokens ---- */
    $pi-accent:        #00aaff;
    $pi-accent-dim:    #0088cc;
    $pi-muted:         #8a8a8a;
    $pi-dim:           #555566;
    $pi-success:       #00ff00;
    $pi-error:         #ff4444;
    $pi-warning:       #ffaa00;
    $pi-bg:            #18181e;
    $pi-bg-elevated:   #1e1e24;
    $pi-bg-panel:      #1e1e2e;
    $pi-selected-bg:   #2d2d30;
    $pi-border:        #333344;
    $pi-border-accent: #00aaff;

    /* ---- base screen ---- */
    Screen {
        background: $pi-bg;
    }

    /* ---- header / status bar (top) ---- */
    #status-bar {
        color: $pi-muted;
        background: $pi-bg-elevated;
        height: 1;
        padding: 0 1;
        content-align: left middle;
    }

    /* ---- footer bar (bottom, Pi-style) ---- */
    #footer-bar {
        color: $pi-dim;
        background: $pi-bg-elevated;
        height: 1;
        padding: 0 1;
        content-align: left middle;
    }

    /* ---- command legend above editor ---- */
    #command-legend {
        color: $pi-dim;
        background: $pi-bg;
        height: 1;
        padding: 0 1;
        content-align: left middle;
    }

    /* ---- transcript / messages area ---- */
    #transcript {
        background: $pi-bg;
        color: $text;
        scrollbar-size-vertical: 1;
        scrollbar-color: $pi-dim;
        scrollbar-color-active: $pi-accent;
        scrollbar-background: $pi-bg;
        scrollbar-background-active: $pi-bg;
    }

    /* ---- editor / prompt input ---- */
    #prompt {
        border: round $pi-border-accent;
        background: $pi-bg-elevated;
        color: $text;
        padding: 0 1;
        height: auto;
    }
    #prompt:focus {
        border: round $pi-accent;
    }
    #prompt > .input--cursor {
        color: $pi-accent;
        background: $pi-accent 30%;
    }
    #prompt.--placeholder {
        color: $pi-dim;
    }
    #prompt.running {
        border: round $pi-warning;
    }
    #prompt.failed {
        border: round $pi-error;
    }
    #prompt.completed {
        border: round $pi-success;
    }

    /* ---- shared modal / panel primitives ---- */
    .panel {
        border: round $pi-border-accent;
        background: $pi-bg-panel;
        padding: 1 2;
        margin: 0 1 1 0;
        height: auto;
        width: 1fr;
    }
    .section-title {
        color: $pi-accent;
        text-style: bold;
        margin-bottom: 1;
    }
    .panel Button {
        width: 100%;
        height: auto;
        content-align: left middle;
        background: transparent;
        border: none;
        padding: 0 1;
        text-style: none;
        color: $text;
    }
    .panel Button:hover {
        background: $pi-selected-bg;
    }
    .panel Button:focus {
        background: $pi-accent 20%;
        text-style: bold;
        color: $pi-accent;
    }
    .keymap {
        width: 100%;
        color: $pi-dim;
        margin-bottom: 1;
    }
    .primary-action {
        width: 100%;
        border: round $pi-success;
        text-style: bold;
        margin-bottom: 1;
        color: $pi-success;
        background: $pi-success 10%;
    }
    .primary-action:focus {
        background: $pi-success 25%;
    }

    /* ---- searchable project picker ---- */
    #project-search {
        border: round $pi-border;
        background: $pi-bg-elevated;
        color: $text;
    }
    #project-search:focus {
        border: round $pi-accent;
    }
    #projects {
        max-height: 12;
        background: $pi-bg-elevated;
        border: none;
    }
    #projects > .option-list--option {
        color: $text;
    }
    #projects > .option-list--option-highlighted {
        background: $pi-selected-bg;
        color: $pi-accent;
        text-style: bold;
    }

    /* ---- searchable model picker ---- */
    #model-search {
        border: round $pi-border;
        background: $pi-bg-elevated;
        color: $text;
    }
    #model-search:focus {
        border: round $pi-accent;
    }
    #models {
        max-height: 12;
        background: $pi-bg-elevated;
        border: none;
    }
    #models > .option-list--option {
        color: $text;
    }
    #models > .option-list--option-highlighted {
        background: $pi-selected-bg;
        color: $pi-accent;
        text-style: bold;
    }

    /* ---- searchable language picker ---- */
    #lang-list {
        max-height: 12;
        background: $pi-bg-elevated;
        border: none;
    }
    #lang-list > .option-list--option {
        color: $text;
    }
    #lang-list > .option-list--option-highlighted {
        background: $pi-selected-bg;
        color: $pi-accent;
        text-style: bold;
    }

    /* ---- slash-command autocomplete (Pi-style / picker) ---- */
    #autocomplete-container {
        display: none;
        height: auto;
        max-height: 9;
        background: $pi-bg-panel;
        border: round $pi-border-accent;
        padding: 0;
    }
    #autocomplete-list {
        background: transparent;
        border: none;
        height: auto;
        padding: 0;
    }
    #autocomplete-list > .option-list--option {
        color: $text;
    }
    #autocomplete-list > .option-list--option-highlighted {
        background: $pi-selected-bg;
        color: $pi-accent;
        text-style: bold;
    }

    /* ---- modal screens ---- */
    ModalScreen {
        background: $pi-bg 80%;
        align: center middle;
    }
    ModalScreen > Vertical {
        background: $pi-bg-panel;
        border: round $pi-border-accent;
        padding: 1 2;
    }
    ModalScreen Label {
        color: $text;
    }
    ModalScreen Label#picker-status,
    ModalScreen Label#choice-hints,
    ModalScreen Label#mm-hints,
    ModalScreen Label#picker-hints,
    ModalScreen Label#hints,
    ModalScreen Label#sm-hints,
    ModalScreen Label#new-project-hints,
    ModalScreen Label#open-project-hints,
    ModalScreen Label#target-lang-hints,
    ModalScreen Label#edit-hints,
    ModalScreen Label#empty {
        color: $pi-dim;
    }
    ModalScreen OptionList {
        background: $pi-bg-elevated;
        border: none;
        padding: 0;
    }
    ModalScreen OptionList:focus {
        border: none;
    }
    ModalScreen OptionList > .option-list--option {
        color: $text;
    }
    ModalScreen OptionList > .option-list--option-highlighted {
        background: $pi-selected-bg;
        color: $pi-accent;
        text-style: bold;
    }
    ModalScreen DataTable {
        background: $pi-bg-elevated;
        border: none;
    }
    ModalScreen DataTable:focus {
        border: none;
    }
    ModalScreen DataTable > .datatable--header {
        background: $pi-bg;
        color: $pi-accent;
        text-style: bold;
    }
    ModalScreen DataTable > .datatable--cursor {
        background: $pi-selected-bg;
        color: $pi-accent;
    }
    ModalScreen Input {
        border: round $pi-border;
        background: $pi-bg-elevated;
        color: $text;
    }
    ModalScreen Input:focus {
        border: round $pi-accent;
    }
    ModalScreen Button {
        background: transparent;
        border: round $pi-border;
        color: $text;
    }
    ModalScreen Button:hover {
        background: $pi-selected-bg;
    }
    ModalScreen Button:focus {
        background: $pi-accent 20%;
        border: round $pi-accent;
        color: $pi-accent;
        text-style: bold;
    }

    /* ---- settings screen specifics ---- */
    #settings-title {
        width: 100%;
        color: $pi-accent;
        text-style: bold;
    }
    #settings-actions {
        height: auto;
        align-horizontal: right;
    }
    #settings-actions Button {
        width: auto;
        margin-left: 1;
        background: transparent;
        border: round $pi-border;
        color: $text;
    }
    #settings-actions Button:focus {
        background: $pi-accent 20%;
        border: round $pi-accent;
        color: $pi-accent;
    }

    /* ---- caption review specifics ---- */
    #playback {
        height: auto;
        margin-top: 1;
    }
    #playback Button {
        background: transparent;
        border: round $pi-border;
        color: $text;
    }
    #playback Button:focus {
        background: $pi-accent 20%;
        border: round $pi-accent;
        color: $pi-accent;
    }
    #play-status {
        color: $pi-muted;
        content-align: left middle;
    }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("q", "quit", "Quit")
    ]

    def __init__(
        self,
        project_dir: Path | None = None,
        app_config: AppConfig | None = None,
        force_setup: bool | None = None,
    ) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.app_config: AppConfig = app_config if app_config is not None else load_app_config()
        # First launch runs the setup wizard before anything else.
        self.needs_setup = force_setup if force_setup is not None else is_first_run()

    def on_mount(self) -> None:
        self.push_screen(ReplScreen())
        if self.needs_setup:
            self.push_screen(FirstRunSetupScreen(on_done=self._setup_finished))

    def screen_query_menu(self) -> ReplScreen:
        """Back-compat: the REPL home, wherever it sits in the stack."""
        return self.repl

    @property
    def repl(self) -> ReplScreen:
        for screen in reversed(list(self.screen_stack)):
            if isinstance(screen, ReplScreen):
                return screen
        raise LookupError("repl not mounted")

    def _setup_finished(self) -> None:
        """Wizard saved config: reload providers and refresh the menu status."""
        repl = self.screen_query_menu()
        self.app_config = load_app_config()
        self.needs_setup = False
        repl.reload_config()
        repl.log_line("[green]Setup complete[/green] — you are ready. Type ? for commands.")


def run(project_dir: str | None = None) -> None:
    SubForgeApp(project_dir=Path(project_dir) if project_dir else None).run()
