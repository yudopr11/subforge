"""Textual application root. Presentation only — logic lives in app/* (ARCH §3.1)."""

from pathlib import Path
from typing import ClassVar

from textual.app import App, RenderResult
from textual.binding import Binding

from subforge.config.app_config import AppConfig, is_first_run, load_app_config
from subforge.tui.screens.repl import ReplScreen
from subforge.tui.screens.setup_wizard import FirstRunSetupScreen


class SubForgeApp(App[None]):
    TITLE = "SUBFORGE"

    CSS = """
    /* ════ Monochrome & Transparent Table-like Visual Theme ════
       Crisp monochrome terminal aesthetic: transparent background,
       white / silver high-contrast text, dark grayscale borders & panels,
       and clean tabular alignments.
    */

    /* ---- global monochrome color tokens ---- */
    $mono-text:        #ffffff;
    $mono-dim:         #777777;
    $mono-dark:        #444444;
    $mono-border:      #3e3e3e;
    $mono-border-hi:   #888888;
    $mono-selected-bg: #2a2a2a;
    $mono-highlight:   #ffffff;

    /* ---- base screen ---- */
    Screen {
        background: ansi_default;
        color: $mono-text;
    }

    /* ---- studio dashboard header (top) ---- */
    #studio-header {
        background: ansi_default;
        border-top: solid $mono-border;
        border-bottom: solid $mono-border;
        height: auto;
        padding: 0 1;
    }
    #project-banner {
        color: $mono-text;
        height: 1;
        content-align: left middle;
    }
    #pipeline-stepper {
        color: $mono-dim;
        height: 1;
        content-align: left middle;
    }
    #next-action-banner {
        color: $mono-text;
        height: 1;
        content-align: left middle;
    }
    #hotkey-bar {
        color: $mono-dim;
        background: transparent;
        border-bottom: solid $mono-border;
        height: 1;
        padding: 0 1;
        content-align: left middle;
    }

    /* ---- header / status bar (top) ---- */
    #status-bar {
        color: $mono-dim;
        background: transparent;
        height: 1;
        padding: 0 1;
        content-align: left middle;
    }

    /* ---- footer bar (bottom) ---- */
    #footer-bar {
        color: $mono-dim;
        background: transparent;
        border-top: solid $mono-border;
        height: 1;
        padding: 0 1;
        content-align: left middle;
    }

    /* ---- command legend above editor ---- */
    #command-legend {
        color: $mono-dim;
        background: transparent;
        border-top: solid $mono-border;
        height: 1;
        padding: 0 1;
        content-align: left middle;
    }

    /* ---- transcript / messages area ---- */
    #transcript {
        background: ansi_default;
        color: $mono-text;
        scrollbar-size-vertical: 1;
        scrollbar-color: $mono-dark;
        scrollbar-color-active: $mono-text;
        scrollbar-background: ansi_default;
        scrollbar-background-active: ansi_default;
    }

    /* ---- editor / prompt input ---- */
    #prompt {
        border: solid $mono-border-hi;
        background: transparent;
        color: $mono-text;
        padding: 0 1;
        height: auto;
    }
    #prompt:focus {
        border: double $mono-text;
    }
    #prompt > .input--cursor {
        color: #000000;
        background: #ffffff;
    }
    #prompt.--placeholder {
        color: $mono-dim;
    }
    #prompt.running {
        border: solid $mono-text;
    }
    #prompt.failed {
        border: solid $mono-dim;
    }
    #prompt.completed {
        border: solid $mono-text;
    }

    /* ---- shared modal / panel primitives ---- */
    .panel {
        border: solid $mono-border-hi;
        background: #111111 90%;
        padding: 1 2;
        margin: 0 1 1 0;
        height: auto;
        width: 1fr;
    }
    .section-title {
        color: $mono-text;
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
        color: $mono-text;
    }
    .panel Button:hover {
        background: $mono-selected-bg;
    }
    .panel Button:focus {
        background: $mono-selected-bg;
        text-style: bold;
        color: $mono-text;
    }
    .keymap {
        width: 100%;
        color: $mono-dim;
        margin-bottom: 1;
    }
    .primary-action {
        width: 100%;
        border: solid $mono-text;
        text-style: bold;
        margin-bottom: 1;
        color: $mono-text;
        background: transparent;
    }
    .primary-action:focus {
        background: $mono-selected-bg;
    }

    /* ---- searchable project / audio pickers ---- */
    #project-search,
    #audio-search {
        border: solid $mono-border-hi;
        background: transparent;
        color: $mono-text;
    }
    #project-search:focus,
    #audio-search:focus {
        border: double $mono-text;
    }
    #projects,
    #audio-files {
        max-height: 12;
        background: transparent;
        border: none;
    }
    #projects > .option-list--option,
    #audio-files > .option-list--option {
        color: $mono-text;
    }
    #projects > .option-list--option-highlighted,
    #audio-files > .option-list--option-highlighted {
        background: $mono-selected-bg;
        color: $mono-text;
        text-style: bold;
    }

    /* ---- searchable model picker ---- */
    #model-search {
        border: solid $mono-border-hi;
        background: transparent;
        color: $mono-text;
    }
    #model-search:focus {
        border: double $mono-text;
    }
    #models {
        max-height: 12;
        background: transparent;
        border: none;
    }
    #models > .option-list--option {
        color: $mono-text;
    }
    #models > .option-list--option-highlighted {
        background: $mono-selected-bg;
        color: $mono-text;
        text-style: bold;
    }

    /* ---- searchable language picker ---- */
    #lang-list {
        max-height: 12;
        background: transparent;
        border: none;
    }
    #lang-list > .option-list--option {
        color: $mono-text;
    }
    #lang-list > .option-list--option-highlighted {
        background: $mono-selected-bg;
        color: $mono-text;
        text-style: bold;
    }

    /* ---- slash-command autocomplete (Pi-style / picker) ---- */
    #autocomplete-container {
        display: none;
        height: auto;
        max-height: 9;
        background: #111111 95%;
        border: solid $mono-border-hi;
        padding: 0;
    }
    #autocomplete-list {
        background: transparent;
        border: none;
        height: auto;
        padding: 0;
    }
    #autocomplete-list > .option-list--option {
        color: $mono-text;
    }
    #autocomplete-list > .option-list--option-highlighted {
        background: $mono-selected-bg;
        color: $mono-text;
        text-style: bold;
    }

    /* ---- modal screens ---- */
    ModalScreen {
        background: #000000 85%;
        align: center middle;
    }
    ModalScreen > Vertical {
        background: #111111;
        border: solid $mono-border-hi;
        padding: 1 2;
    }
    ModalScreen Label {
        color: $mono-text;
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
        color: $mono-dim;
    }
    ModalScreen OptionList {
        background: transparent;
        border: none;
        padding: 0;
    }
    ModalScreen OptionList:focus {
        border: none;
    }
    ModalScreen OptionList > .option-list--option {
        color: $mono-text;
    }
    ModalScreen OptionList > .option-list--option-highlighted {
        background: $mono-selected-bg;
        color: $mono-text;
        text-style: bold;
    }
    ModalScreen DataTable {
        background: transparent;
        border: solid $mono-border;
    }
    ModalScreen DataTable:focus {
        border: solid $mono-border-hi;
    }
    ModalScreen DataTable > .datatable--header {
        background: $mono-selected-bg;
        color: $mono-text;
        text-style: bold;
    }
    ModalScreen DataTable > .datatable--cursor {
        background: $mono-selected-bg;
        color: $mono-text;
        text-style: bold;
    }
    ModalScreen Input {
        border: solid $mono-border-hi;
        background: transparent;
        color: $mono-text;
    }
    ModalScreen Input:focus {
        border: double $mono-text;
    }
    ModalScreen Button {
        background: transparent;
        border: solid $mono-border;
        color: $mono-text;
    }
    ModalScreen Button:hover {
        background: $mono-selected-bg;
    }
    ModalScreen Button:focus {
        background: $mono-selected-bg;
        border: solid $mono-text;
        color: $mono-text;
        text-style: bold;
    }

    /* ---- settings screen specifics ---- */
    #settings-title {
        width: 100%;
        color: $mono-text;
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
        border: solid $mono-border;
        color: $mono-text;
    }
    #settings-actions Button:focus {
        background: $mono-selected-bg;
        border: solid $mono-text;
        color: $mono-text;
    }

    /* ---- caption review specifics ---- */
    CaptionReviewScreen > Vertical {
        width: 92%;
        height: 88%;
        max-height: 90%;
        padding: 1 2;
    }
    CaptionReviewScreen DataTable {
        height: 1fr;
        min-height: 5;
    }
    CaptionReviewScreen Input {
        height: auto;
        min-height: 3;
        margin-top: 0;
        margin-bottom: 0;
    }
    #playback {
        height: auto;
        margin-top: 0;
        margin-bottom: 0;
    }
    #playback Button {
        background: transparent;
        border: solid $mono-border;
        color: $mono-text;
    }
    #playback Button:focus {
        background: $mono-selected-bg;
        border: solid $mono-text;
        color: $mono-text;
    }
    #play-status {
        color: $mono-dim;
        content-align: left middle;
    }

    /* ---- model manager screen specifics ---- */
    ModelManagerScreen > Vertical {
        width: 85%;
        max-height: 85%;
    }
    ModelManagerScreen DataTable {
        height: 8;
        max-height: 10;
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

    def render(self) -> RenderResult:
        from textual.renderables.blank import Blank

        return Blank("ansi_default")

    def on_mount(self) -> None:
        from subforge.app.storage import migrate_legacy_projects

        migrated = migrate_legacy_projects()
        self.push_screen(ReplScreen())
        if migrated:
            self.repl.log_line(
                f"[dim]Migrated {len(migrated)} legacy project(s) to app storage.[/dim]"
            )
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

    def download_model_background(
        self,
        model_id: str,
        manager: object = None,
    ) -> None:
        from subforge.app.model_manager import LocalModelManager

        mgr = manager if isinstance(manager, LocalModelManager) else LocalModelManager()
        if mgr.is_installed(model_id):
            return

        def _work() -> None:
            try:
                try:
                    self.call_from_thread(
                        self.repl.log_line,
                        f"⏳ Downloading Whisper model '[b]{model_id}[/b]' in background...",
                    )
                except Exception:  # noqa: BLE001, S110
                    pass

                last_milestone = 0

                def _bg_progress(downloaded: int, total: int) -> None:
                    nonlocal last_milestone
                    if total > 0:
                        pct = int(downloaded / total * 100)
                        dl_mb = downloaded / (1024 * 1024)
                        tot_mb = total / (1024 * 1024)
                        status_msg = f"Downloading {model_id}: {dl_mb:.1f}/{tot_mb:.1f} MB ({pct}%)"
                        try:
                            self.call_from_thread(self.repl._set_status, status_msg)
                        except Exception:  # noqa: BLE001, S110
                            pass

                        # Log milestones at 25%, 50%, 75%
                        if pct >= last_milestone + 25 and pct < 100:
                            last_milestone = (pct // 25) * 25
                            try:
                                self.call_from_thread(
                                    self.repl.log_line,
                                    f"  • Downloading '[b]{model_id}[/b]': {dl_mb:.1f}/{tot_mb:.1f} MB ({pct}%)",
                                )
                            except Exception:  # noqa: BLE001, S110
                                pass
                    else:
                        dl_mb = downloaded / (1024 * 1024)
                        status_msg = f"Downloading {model_id}: {dl_mb:.1f} MB..."
                        try:
                            self.call_from_thread(self.repl._set_status, status_msg)
                        except Exception:  # noqa: BLE001, S110
                            pass

                mgr.install(model_id, progress_callback=_bg_progress)
                try:
                    self.call_from_thread(
                        self.repl.log_line,
                        f"✓ Model '[b]{model_id}[/b]' downloaded and ready.",
                    )
                    self.call_from_thread(self.repl._set_status, "")
                    self.call_from_thread(self.repl.refresh_status)
                except Exception:  # noqa: BLE001, S110
                    pass
            except Exception as exc:  # noqa: BLE001
                try:
                    self.call_from_thread(
                        self.repl.log_line,
                        f"[red]✗[/red] Failed to download model '{model_id}': {exc}",
                    )
                    self.call_from_thread(self.repl._set_status, "")
                except Exception:  # noqa: BLE001, S110
                    pass

        self.run_worker(_work, thread=True, group="model_downloads")

    def _setup_finished(self) -> None:
        """Wizard saved config: reload providers and refresh the menu status."""
        repl = self.screen_query_menu()
        self.app_config = load_app_config()
        self.needs_setup = False
        repl.reload_config()
        repl.log_line("[green]Setup complete[/green] — you are ready. Type ? for commands.")


def run(project_dir: str | None = None) -> None:
    SubForgeApp(project_dir=Path(project_dir) if project_dir else None).run()
