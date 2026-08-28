"""Subtitle REPL — transcript-driven home screen (PRD §7, pi/coding-CLI style).

Presentation only (ARCH §3.1/§3.2): slash commands route to `app/*` services.
The transcript is the interface; every action writes an event line.
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, OptionList, RichLog, Static

from subforge.app.export import export_subtitles
from subforge.app.pipeline import ALL_STAGES, Pipeline, StageError
from subforge.app.project_store import load_project, save_project
from subforge.app.projects import create_project_from_audio, discover_projects, find_audio_file
from subforge.app.provider_factory import (
    build_pipeline,
    transcription_configured,
)
from subforge.models.project import StageState
from subforge.tui.widgets import SelectableRichLog

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp


def _glyph(state: StageState) -> str:
    return {
        StageState.PENDING: "○",
        StageState.RUNNING: "●",
        StageState.COMPLETED: "✓",
        StageState.FAILED: "✗",
        StageState.SKIPPED: "–",
    }[state]


class ReplScreen(Screen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("escape", "cancel_or_prompt", "Back"),
        Binding("ctrl+n", "hotkey_new", "New Project", show=False),
        Binding("ctrl+t", "hotkey_transcribe", "Transcribe", show=False),
        Binding("ctrl+r", "hotkey_review", "Review Captions", show=False),
        Binding("ctrl+e", "hotkey_export", "Export", show=False),
        Binding("ctrl+p", "hotkey_projects", "Projects", show=False),
        Binding("ctrl+m", "hotkey_models", "Models", show=False),
    ]

    AUTO_FOCUS = "#prompt"

    def __init__(self, pipeline_factory: Callable[[Path], Pipeline] | None = None) -> None:
        super().__init__()
        self.pipeline_factory = pipeline_factory  # test seam
        self._running_stages: set[str] = set()
        self._recent_listing: list[Path] = []
        self.locate_mode: str | None = None  # None | "new" — /new interactive locate
        self._history: list[str] = []  # submitted prompt values, oldest → newest
        self._history_index: int | None = None  # position while arrow-navigating
        self._history_draft: str = ""  # original prompt draft while navigating

    @property
    def _host(self) -> "SubForgeApp":
        from subforge.tui.app import SubForgeApp

        app: SubForgeApp = self.app  # type: ignore[assignment]
        return app

    # ---- layout ----------------------------------------------------------

    SLASH_COMMANDS: ClassVar[list[tuple[str, str]]] = [
        ("/new", "create project + import audio"),
        ("/open", "list/open recent projects"),
        ("/projects", "manage/open projects"),
        ("/delete", "delete a project"),
        ("/models", "manage and select local Whisper models"),
        ("/language", "set default audio source language"),
        ("/transcribe", "run transcription"),
        ("/review", "edit and review caption segments"),
        ("/export", "export SRT/ASS"),
        ("/wizard", "re-run guided setup"),
        ("/status", "pipeline stage states"),
        ("/quit", "exit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="studio-header"):
            yield Static(self._render_logo(), id="logo-banner")
            yield Label("", id="project-banner")
            yield Label("", id="pipeline-stepper")
            yield Label("", id="next-action-banner")
            yield Label("", id="status-bar")
        yield Label(
            "[b]N[/b] New  │  [b]T[/b] Transcribe  │  [b]R[/b] Review  │  [b]E[/b] Export  │  [b]P[/b] Projects  │  [b]M[/b] Models  │  [b]?[/b] Help",
            id="hotkey-bar",
        )
        with Vertical():
            yield SelectableRichLog(
                id="transcript", markup=True, wrap=True, highlight=False
            )
        with Vertical(id="autocomplete-container"):
            yield OptionList(id="autocomplete-list")
        yield Static(
            "/new /open /projects /delete /models /language /transcribe /review /export /wizard /status ? quit",
            id="command-legend",
        )
        yield Input(placeholder="Type a command or press hotkey (N, T, R, E, P, M)...", id="prompt")
        yield Label("", id="footer-bar")

    def _render_logo(self) -> str:
        from subforge import __version__

        return (
            "  [bold cyan]▄████▄[/bold cyan]  [bold white]████████[/bold white]\n"
            "  [bold cyan]██[/bold cyan]      [bold white]██[/bold white]\n"
            f"  [bold cyan]▀████▄[/bold cyan]  [bold white]█████[/bold white]     [bold]SUBFORGE STUDIO[/bold] [dim]v{__version__}[/dim]  —  [dim]local-first subtitles[/dim]\n"
            "      [bold cyan]██[/bold cyan]  [bold white]██[/bold white]\n"
            "  [bold cyan]▀████▀[/bold cyan]  [bold white]██[/bold white]"
        )

    def on_mount(self) -> None:
        self.log_line("[b]subforge[/b]  —  Quick Guide & Workflow:")
        self.log_line("  • [b]N[/b] (or [b]/new <audio>[/b])  — Create project and import audio file")
        self.log_line("  • [b]T[/b] (or [b]/transcribe[/b])   — Run local whisper.cpp speech-to-text")
        self.log_line("  • [b]R[/b] (or [b]/review[/b])       — Edit captions & listen to audio preview")
        self.log_line("  • [b]E[/b] (or [b]/export[/b])       — Export clean .srt and .ass subtitles")
        self.log_line("  • [b]M[/b] (or [b]/models[/b])       — Manage, download & switch Whisper models")
        self.log_line("  • [b]?[/b] (or [b]/help[/b])         — Show all available commands")
        self.log_line("")
        if self._host.project_dir is not None:
            self.log_line(f"▸ Opened active project '[b]{self._host.project_dir.name}[/b]'")
        else:
            self.log_line("[dim]▸ Ready. Start by pressing [b]N[/b] to create a project or [b]P[/b] to open one.[/dim]")
            self._hint_setup_if_needed()
        self.refresh_status()
        self._refresh_footer()

    # ---- transcript + status ----------------------------------------------

    def log_line(self, text: str = "") -> None:
        self.query_one("#transcript", RichLog).write(text)

    def _set_status(self, message: str) -> None:
        if self.query("#status-bar"):
            self.query_one("#status-bar", Label).update(message)

    def _refresh_footer(self) -> None:
        """Pi-style footer: project · model info · shortcuts."""
        host = self._host
        parts: list[str] = []
        if host.project_dir is not None:
            parts.append(f"project:{host.project_dir.name}")
        tc = host.app_config.transcription
        if tc.model:
            parts.append(f"asr:{tc.provider}:{tc.model}")
        if not parts:
            parts.append("no project")
        footer = " · ".join(parts)
        self.query_one("#footer-bar", Label).update(footer)

    def _render_project_banner(self) -> str:
        project_dir = self._host.project_dir
        tc = self._host.app_config.transcription
        model_str = f"asr:{tc.provider}:{tc.model}" if tc.model else "no model"
        if project_dir is None:
            return f"┌─ [b]PROJECT:[/b] [dim](no project open)[/dim]  │  [b]MODEL:[/b] {model_str}  │  [b]LANG:[/b] {tc.language or 'auto'}"
        try:
            project = load_project(project_dir)
            p_meta = project.project
            src = p_meta.source_language or tc.language or "auto"
            audio = find_audio_file(project_dir)
            audio_name = audio.name if audio else "no audio"
            seg_count = len(project.segments)
            return (
                f"┌─ [b]PROJECT:[/b] {p_meta.name} ({seg_count} captions)  │  "
                f"[b]MODEL:[/b] {model_str}  │  "
                f"[b]AUDIO:[/b] {audio_name}  │  "
                f"[b]LANG:[/b] {src}"
            )
        except Exception:  # noqa: BLE001
            return f"┌─ [b]PROJECT:[/b] {project_dir.name}  │  [b]MODEL:[/b] {model_str}"

    def _render_pipeline_stepper(self) -> str:
        project_dir = self._host.project_dir
        if project_dir is None:
            return "│  Pipeline: [1. New] ──▶ [2. Transcribe] ──▶ [3. Review] ──▶ [4. Export]"
        try:
            project = load_project(project_dir)
        except Exception:  # noqa: BLE001
            return "│  Pipeline: [1. New] ──▶ [2. Transcribe] ──▶ [3. Review] ──▶ [4. Export]"

        t_stage = project.get_stage("transcription")
        has_captions = len(project.segments) > 0
        export_stage = project.get_stage("export")

        pills = [
            f"\\[{_glyph(t_stage)} Transcribe\\]",
            f"\\[{'✓' if has_captions else '○'} Review\\]",
            f"\\[{_glyph(export_stage)} Export\\]",
        ]
        return "│  [b]PIPELINE:[/b] " + " ─▶ ".join(pills)

    def _render_next_step(self) -> str:
        project_dir = self._host.project_dir
        if project_dir is None:
            return "└─ [b]NEXT:[/b] Press [b]N[/b] to create a New project or [b]P[/b] to Open an existing project."
        try:
            project = load_project(project_dir)
        except Exception:  # noqa: BLE001
            return "└─ [b]NEXT:[/b] Press [b]N[/b] to create a New project or [b]P[/b] to Open an existing project."

        t_stage = project.get_stage("transcription")
        if t_stage in (StageState.PENDING, StageState.FAILED):
            return "└─ [b]NEXT:[/b] Press [b]T[/b] to Transcribe audio with whisper.cpp."
        if t_stage == StageState.RUNNING:
            return "└─ [b]NEXT:[/b] ⏳ Transcription in progress… please wait."

        export_stage = project.get_stage("export")
        if export_stage == StageState.COMPLETED:
            return "└─ [b]NEXT:[/b] Subtitles exported! Press [b]E[/b] to re-export or [b]R[/b] to edit captions."

        return "└─ [b]NEXT:[/b] Press [b]R[/b] to Review Captions or [b]E[/b] to Export Subtitles."

    def refresh_status(self) -> None:
        """Header status line: project banner, pipeline stepper, next action, footer."""
        host = self._host
        parts: list[str] = []
        project_dir = host.project_dir
        model_bits: list[str] = []
        tc = host.app_config.transcription
        if tc.model:
            model_bits.append(f"asr:{tc.provider}:{tc.model}")

        if project_dir is None:
            parts.append("no project")
        else:
            parts.append(f"{project_dir.name}")
            try:
                project = load_project(project_dir)
                shown: dict[str, StageState] = {s: project.get_stage(s) for s in ALL_STAGES}
                for label in sorted(shown):
                    if shown[label] is not StageState.PENDING or label == "transcription":
                        parts.append(f"{label} {_glyph(shown[label])}")
            except Exception:  # noqa: BLE001, S110
                pass
        if model_bits:
            parts.append(" · ".join(model_bits))
        busy = f" · ⏳ {'/'.join(sorted(self._running_stages))}" if self._running_stages else ""

        if self.query("#project-banner"):
            self.query_one("#project-banner", Label).update(self._render_project_banner())
        if self.query("#pipeline-stepper"):
            self.query_one("#pipeline-stepper", Label).update(self._render_pipeline_stepper())
        if self.query("#next-action-banner"):
            self.query_one("#next-action-banner", Label).update(self._render_next_step())

        self._set_status(" · ".join(parts) + busy)
        self._refresh_footer()
        self._update_prompt_border()

    def _update_prompt_border(self) -> None:
        """Pi-style editor border: color reflects pipeline state."""
        prompt = self.query_one("#prompt", Input)
        for cls in ("running", "failed", "completed"):
            prompt.remove_class(cls)
        if self._running_stages:
            prompt.add_class("running")
            return
        project_dir = self._host.project_dir
        if project_dir is None:
            return
        project = load_project(project_dir)
        states = [project.get_stage(s) for s in ALL_STAGES]
        if any(s is StageState.FAILED for s in states):
            prompt.add_class("failed")
        elif all(s in (StageState.COMPLETED, StageState.SKIPPED) for s in states):
            prompt.add_class("completed")

    def reload_config(self) -> None:
        """Reload AppConfig after config/wizard changes."""
        from subforge.config.app_config import load_app_config

        self._host.app_config = load_app_config()
        self.refresh_status()
        self.log_line("▸ configuration reloaded")

    # ---- locate mode (/new) ----------------------------------------------

    _NORMAL_PLACEHOLDER = "Type a command… (? for help)"
    _LOCATE_PLACEHOLDER = "audio file path — @ to browse, Enter confirm, Esc cancel"

    def enter_locate_mode(self) -> None:
        self.locate_mode = "new"
        prompt = self.query_one("#prompt", Input)
        prompt.placeholder = self._LOCATE_PLACEHOLDER
        self.log_line("Locate audio: type a path, or [b]@[/b] to browse files here.")
        self._set_status("[b]/new[/b] · locating audio · esc cancel")

    def exit_locate_mode(self) -> None:
        self.locate_mode = None
        self.query_one("#prompt", Input).placeholder = self._NORMAL_PLACEHOLDER
        self.refresh_status()

    def _submit_prompt_value(self, value: str) -> None:
        """Test seam + locate-mode submit: handle raw prompt content directly."""
        if self.locate_mode == "new":
            if not value.strip():
                return
            if value.startswith("@"):
                query = value[1:].strip().lower()
                from subforge.app.projects import discover_audio_files
                from subforge.tui.screens.audio_picker import AudioFilePickerScreen

                matches = [
                    f for f in discover_audio_files()
                    if not query or query in str(f).lower() or query in f.name.lower()
                ]
                self._host.push_screen(
                    AudioFilePickerScreen(matches[:100]), self._locate_picked
                )
                return
            # a concrete path: create, then leave locate mode
            self._cmd_new(value)
            if self._host.project_dir is not None:
                self.exit_locate_mode()
            return
        self.run_command(value if value.startswith("/") else "/" + value)

    def _locate_picked(self, picked: object) -> None:
        """Audio picker result: path to create, PATH_ENTRY for manual typing, None cancel."""
        if picked is None:
            self.log_line("[dim]cancelled[/dim]")
            return
        from subforge.tui.screens.audio_picker import AudioFilePickerScreen

        if picked == AudioFilePickerScreen.PATH_ENTRY:
            self.enter_locate_mode()
            return
        if isinstance(picked, str):
            self._cmd_new(picked)
            if self._host.project_dir is not None:
                self.exit_locate_mode()

    # ---- input -------------------------------------------------------------

    # ---- slash command autocomplete (Pi-style) -----------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        """Show/hide the slash-command picker as the prompt content changes or trigger direct hotkey."""
        if event.input.id != "prompt":
            return
        if self.locate_mode is not None or self._history_index is not None:
            self._hide_autocomplete()  # path entry / history recall: no picker
            return
        value = event.value
        if value.startswith("/"):
            self._show_autocomplete(value[1:])
        else:
            self._hide_autocomplete()
            if len(value) == 1:
                ch = value.lower()
                hotkey_actions = {
                    "n": self.action_hotkey_new,
                    "t": self.action_hotkey_transcribe,
                    "r": self.action_hotkey_review,
                    "e": self.action_hotkey_export,
                    "p": self.action_hotkey_projects,
                    "m": self.action_hotkey_models,
                    "?": self.action_hotkey_help,
                }
                if ch in hotkey_actions:
                    event.input.value = ""
                    hotkey_actions[ch]()

    def _show_autocomplete(self, query: str) -> None:
        """Filter commands by prefix and display the picker."""
        container = self.query_one("#autocomplete-container")
        option_list = self.query_one("#autocomplete-list", OptionList)
        option_list.clear_options()
        matches = [
            (cmd, desc) for cmd, desc in self.SLASH_COMMANDS
            if cmd[1:].startswith(query) or (query and query in cmd[1:])
        ]
        if not matches:
            container.styles.display = "none"
            return
        for cmd, desc in matches:
            option_list.add_option(f"{cmd}  —  {desc}")
        option_list.highlighted = 0
        container.styles.display = "block"

    def _hide_autocomplete(self) -> None:
        self.query_one("#autocomplete-container").styles.display = "none"

    def _autocomplete_visible(self) -> bool:
        return self.query_one("#autocomplete-container").styles.display != "none"

    def _autocomplete_up(self) -> None:
        option_list = self.query_one("#autocomplete-list", OptionList)
        count = option_list.option_count
        if count == 0:
            return
        current = option_list.highlighted
        option_list.highlighted = count - 1 if current is None or current == 0 else current - 1

    def _autocomplete_down(self) -> None:
        option_list = self.query_one("#autocomplete-list", OptionList)
        count = option_list.option_count
        if count == 0:
            return
        current = option_list.highlighted
        option_list.highlighted = 0 if current is None or current >= count - 1 else current + 1

    def _autocomplete_fill(self) -> None:
        """Fill the prompt with the highlighted command (Tab or Enter)."""
        option_list = self.query_one("#autocomplete-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None:
            return
        prompt = self.query_one("#prompt", Input)
        command = str(option_list.get_option_at_index(highlighted).prompt).split("  —  ")[0]
        prompt.value = command + " "
        prompt.cursor_position = len(command) + 1
        self._hide_autocomplete()
        prompt.focus()

    def on_key(self, event: events.Key) -> None:
        """Route arrows/Tab/Escape: autocomplete picker, else prompt history / direct hotkeys."""
        if self._autocomplete_visible():
            if event.key in ("up", "down"):
                event.stop()
                if event.key == "up":
                    self._autocomplete_up()
                else:
                    self._autocomplete_down()
            elif event.key == "tab":
                event.stop()
                self._autocomplete_fill()
            elif event.key == "escape":
                event.stop()
                self._hide_autocomplete()
            return

        if self.locate_mode is None:
            prompt = self.query_one("#prompt", Input)
            if event.character and prompt.value in ("", event.character):
                ch = event.character.lower()
                actions = {
                    "n": self.action_hotkey_new,
                    "t": self.action_hotkey_transcribe,
                    "r": self.action_hotkey_review,
                    "e": self.action_hotkey_export,
                    "p": self.action_hotkey_projects,
                    "m": self.action_hotkey_models,
                    "?": self.action_hotkey_help,
                }
                if ch in actions:
                    prompt.value = ""
                    event.stop()
                    event.prevent_default()
                    actions[ch]()
                    return

        if event.key in ("up", "down") and self._recall_history(up=event.key == "up"):
            event.stop()

    def action_hotkey_new(self) -> None:
        self._cmd_new("")

    def action_hotkey_transcribe(self) -> None:
        self._cmd_transcribe("")

    def action_hotkey_review(self) -> None:
        self._cmd_review("")

    def action_hotkey_export(self) -> None:
        self._cmd_export("")

    def action_hotkey_projects(self) -> None:
        self._cmd_open("")

    def action_hotkey_models(self) -> None:
        self._cmd_models("")

    def action_hotkey_help(self) -> None:
        self._cmd_help("")

    def _remember(self, raw: str) -> None:
        """Record a submitted prompt value; dedupe consecutive repeats, cap 100."""
        self._history_index = None
        self._history_draft = ""
        if raw and (not self._history or self._history[-1] != raw):
            self._history.append(raw)
            del self._history[:-100]

    def _recall_history(self, up: bool) -> bool:
        """Arrow-up/down: cycle the prompt through submitted history (Pi-style).

        Returns True when the event was consumed (history existed).
        """
        if not self._history:
            return False
        prompt = self.query_one("#prompt", Input)
        if self._history_index is None:
            self._history_draft = prompt.value  # save what was being typed
            index = len(self._history) - 1 if up else 0
        else:
            index = self._history_index + (-1 if up else 1)
            if index < 0 or index >= len(self._history):
                self._history_index = None  # past the edge: restore the draft
                prompt.value = self._history_draft
                prompt.cursor_position = len(prompt.value)
                return True
        self._history_index = index
        prompt.value = self._history[index]
        prompt.cursor_position = len(prompt.value)
        return True

    # ---- input -------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "prompt":
            return
        raw = event.value.strip()
        if self._autocomplete_visible():
            # Enter selects the highlighted command instead of submitting.
            self._autocomplete_fill()
            return
        self._remember(raw)
        self.log_line(f"[dim]>[/dim] {raw}")
        event.input.clear()
        if self.locate_mode == "new":
            if raw == "":
                self.exit_locate_mode()
                self.log_line("[dim]cancelled[/dim]")
            else:
                self._submit_prompt_value(raw)
            return
        if raw in {"?", "help"}:
            self.run_command("/help")
        elif raw in {"q", "quit"}:
            self.run_command("/quit")
        elif raw.startswith("/"):
            self.run_command(raw)
        elif raw:
            self.run_command("/" + raw)

    def run_command(self, raw: str) -> None:
        """Public seam: parse and execute one command line."""
        cmd = raw.lstrip("/").strip()
        name, _, arg = cmd.partition(" ")
        handler = getattr(self, f"_cmd_{name.lower()}", None)
        if handler is None:
            self.log_line(f"[red]✗ unknown command:[/red] /{name} — try ?")
            return
        handler(arg.strip())

    # ---- shared helpers ------------------------------------------------------

    def _require_project(self) -> Path | None:
        if self._host.project_dir is None:
            self.log_line("[red]✗[/red] No project open — start with /new <audio> or /open")
            return None
        return self._host.project_dir

    def _make_pipeline(self, project_dir: Path) -> Pipeline:
        if self.pipeline_factory is not None:
            return self.pipeline_factory(project_dir)
        return build_pipeline(project_dir, self._host.app_config)

    def _hint_setup_if_needed(self) -> None:
        cfg = self._host.app_config
        if not transcription_configured(cfg):
            self.log_line('[dim]tip: no transcribe provider yet — run /models or /wizard[/dim]')

    def _finish_stage(self, stage: str) -> None:
        self._running_stages.discard(stage)

    def _launch_stage(self, stage: str, work: Callable[[], str], busy_label: str) -> None:
        if stage in self._running_stages:
            self.log_line(f"[yellow]⏳[/yellow] {busy_label} already running…")
            return
        self._running_stages.add(stage)
        self.log_line(f"[yellow]▸[/yellow] {busy_label}…")
        self.refresh_status()

        def runner() -> None:
            try:
                message = work()
            except StageError as exc:
                message = str(exc)
            except Exception as exc:  # noqa: BLE001 — last-resort guard for the UI thread
                message = f"[ERROR] {exc}"
            finally:
                self._host.call_from_thread(self._finish_stage, stage)
            self._host.call_from_thread(self._log_result, message)

        self.run_worker(runner, thread=True, exclusive=False, group=f"stage-{stage}")

    def _log_result(self, message: str) -> None:
        ok = not message.startswith(("[ERROR]", "[SETUP]"))
        glyph = "✓" if ok else "✗"
        color = "#00ff00" if ok else "#ff4444"
        self.log_line(f"[{color}]{glyph}[/{color}] {message}")
        self.refresh_status()

    # ---- commands -----------------------------------------------------------

    def _cmd_new(self, arg: str) -> None:
        if not arg:
            # Searchable picker of discoverable audio (type to filter, ↑/↓, Enter).
            # The pinned "type a file path" row (or Esc) falls back to path typing.
            from subforge.app.projects import discover_audio_files
            from subforge.tui.screens.audio_picker import AudioFilePickerScreen

            self._host.push_screen(
                AudioFilePickerScreen(discover_audio_files()[:100]), self._locate_picked
            )
            return
        try:
            directory = create_project_from_audio(Path(arg).expanduser())
        except ValueError as exc:
            self.log_line(str(exc))
            return
        language = self._host.app_config.transcription.language
        if language:
            project = load_project(directory)
            project.project.source_language = language
            save_project(directory, project)
        self._host.project_dir = directory
        self.log_line(f"▸ created project '[b]{directory.name}[/b]' — audio imported")
        self._hint_setup_if_needed()
        self.refresh_status()

    def _cmd_open(self, arg: str) -> None:
        projects = discover_projects()
        if not projects:
            self.log_line("No projects yet — use /new <audio>")
            return
        if not arg:
            # Pi-style: searchable picker — type to filter, ↑/↓, Enter to open.
            self._recent_listing = projects
            from subforge.tui.screens.project import ProjectPickerScreen

            self._host.push_screen(ProjectPickerScreen(projects), self._open_picked)
            return
        target: Path | None = None
        if arg.isdigit():
            listing = self._recent_listing or projects
            idx = int(arg) - 1
            if 0 <= idx < len(listing):
                target = listing[idx]
        if target is None:
            # resolution priority: exact name > prefix > substring (deterministic)
            by_name = sorted(projects, key=lambda p: p.name)
            matches = (
                [p for p in by_name if p.name == arg]
                or [p for p in by_name if p.name.startswith(arg)]
                or [p for p in by_name if arg in p.name]
            )
            target = matches[0] if matches else None
        if target is None:
            self.log_line(f"[red]✗[/red] no project matching '{arg}'")
            return
        self._project_opened(target)

    def _open_picked(self, picked: object) -> None:
        """Project picker result: Path to open, NEW to create, None to cancel."""
        if picked is None:
            return
        from subforge.tui.screens.project import ProjectPickerScreen

        if picked == ProjectPickerScreen.NEW:
            self._cmd_new("")
            return
        if isinstance(picked, Path):
            self._project_opened(picked)

    def _project_opened(self, directory: Path) -> None:
        self._host.project_dir = directory
        name = load_project(directory).project.name
        self.log_line(f"▸ opened '[b]{name}[/b]'")
        self.refresh_status()

    def _cmd_transcribe(self, arg: str) -> None:
        if "transcription" in self._running_stages:
            self.log_line("[yellow]⏳[/yellow] transcription already running…")
            return
        project_dir = self._require_project()
        if project_dir is None:
            return
        audio = find_audio_file(project_dir)
        if audio is None:
            self.log_line(f"[red]✗[/red] no audio file in {project_dir / 'audio'}")
            return
        seam = self.pipeline_factory is not None  # tests/custom wiring count as configured
        if not seam and not transcription_configured(self._host.app_config):
            self.log_line(
                "[SETUP] No transcription provider yet — run /models or /wizard first."
            )
            return

        force = arg.strip().lower() in ("force", "--force", "-f", "rerun", "--rerun")
        project = load_project(project_dir)
        if not force and project.get_stage("transcription") == StageState.COMPLETED:
            from subforge.tui.screens.confirm_dialog import ConfirmDialogScreen

            def _on_confirm(confirmed: bool | None) -> None:
                if confirmed:
                    self._start_transcribe(project_dir, audio, force=True)
                else:
                    self.log_line("[dim]transcription cancelled[/dim]")

            n_segs = len(project.segments)
            self._host.push_screen(
                ConfirmDialogScreen(
                    title="Rerun Transcription",
                    message=f"Project '{project.project.name}' is already transcribed ({n_segs} captions). Rerun and overwrite captions?",
                ),
                _on_confirm,
            )
            return

        self._start_transcribe(project_dir, audio, force=force)

    def _start_transcribe(self, project_dir: Path, audio: Path, force: bool = False) -> None:
        pipeline = self._make_pipeline(project_dir)

        def work() -> str:
            pipeline.run_transcription(audio.name, force=force)
            n = len(pipeline.load().segments)
            return f"transcribed — {n} captions"

        self._launch_stage("transcription", work, f"transcribing '{audio.name}'")

    def _cmd_review(self, arg: str) -> None:
        project_dir = self._require_project()
        if project_dir is None:
            return
        from subforge.tui.screens.caption_review import CaptionReviewScreen, player_for

        audio = find_audio_file(project_dir)
        player = player_for(audio) if audio else None
        self._host.push_screen(CaptionReviewScreen(project_dir, player=player))

    def _cmd_export(self, arg: str) -> None:
        formats = [f.strip() for f in arg.split(",")] if arg else ["srt", "ass"]
        project_dir = self._require_project()
        if project_dir is None:
            return
        cwd = Path.cwd()
        try:
            paths = export_subtitles(
                project_dir, formats=formats, output_dir=cwd
            )
        except ValueError as exc:
            self.log_line(str(exc))
            return
        if not paths:
            self.log_line("▸ (nothing to export yet)")
        else:
            export_dir = (project_dir / "exports").resolve()
            self.log_line(f"✓ Exported {len(paths)} subtitle file(s) to [b]{cwd}[/b]:")
            for p in paths:
                self.log_line(f"  • [green]{p.resolve()}[/green]")
            self.log_line(f"[dim]  (internal copies saved to {export_dir})[/dim]")
        self.refresh_status()

    def _cmd_projects(self, arg: str) -> None:
        self._cmd_open(arg)

    def _cmd_models(self, arg: str) -> None:
        from subforge.config.app_config import save_app_config
        from subforge.tui.screens.model_manager import ModelManagerScreen

        def _on_model_selected(model_id: str | None) -> None:
            if model_id:
                self._host.app_config.transcription.model = model_id
                save_app_config(self._host.app_config)
                self.log_line(f"✓ Selected transcription model: [b]{model_id}[/b]")
                self.refresh_status()

        self._host.push_screen(
            ModelManagerScreen(current_model=self._host.app_config.transcription.model),
            _on_model_selected,
        )

    def _cmd_delete(self, arg: str) -> None:
        projects = discover_projects()
        if not projects:
            self.log_line("No projects found.")
            return
        if not arg:
            from subforge.tui.screens.project import ChoiceScreen

            choices = [p.name for p in sorted(projects, key=lambda p: p.name)]

            def _on_picked(picked: object) -> None:
                if picked and isinstance(picked, str):
                    self._cmd_delete(picked)

            self._host.push_screen(
                ChoiceScreen("Select project to delete", choices),
                _on_picked,
            )
            return
        target: Path | None = None
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(projects):
                target = projects[idx]
        if target is None:
            by_name = sorted(projects, key=lambda p: p.name)
            matches = (
                [p for p in by_name if p.name == arg]
                or [p for p in by_name if p.name.startswith(arg)]
                or [p for p in by_name if arg in p.name]
            )
            target = matches[0] if matches else None
        if target is None:
            self.log_line(f"[red]✗[/red] no project matching '{arg}'")
            return

        from subforge.tui.screens.confirm_dialog import ConfirmDialogScreen

        target_dir = target

        def on_confirmed(confirmed: bool | None) -> None:
            if confirmed:
                from subforge.app.projects import delete_project

                name = target_dir.name
                if delete_project(target_dir):
                    self.log_line(f"✓ Deleted project '[b]{name}[/b]'")
                    if self._host.project_dir == target_dir:
                        self._host.project_dir = None
                        self.refresh_status()
                else:
                    self.log_line(f"[red]✗[/red] failed to delete project '{name}'")

        self._host.push_screen(
            ConfirmDialogScreen(
                title="Delete Project",
                message=f"Permanently delete project '{target_dir.name}' and all associated files?",
            ),
            on_confirmed,
        )

    def _cmd_language(self, arg: str) -> None:
        from subforge.config.app_config import save_app_config
        from subforge.tui.screens.language_picker import LanguagePickerScreen

        if arg:
            self._host.app_config.transcription.language = arg.strip().lower()
            save_app_config(self._host.app_config)
            self.log_line(f"✓ Audio source language set to: [b]{arg}[/b]")
            self.refresh_status()
            return

        def _on_lang(lang: str | None) -> None:
            if lang is not None:
                chosen = lang.strip().lower()
                self._host.app_config.transcription.language = chosen
                save_app_config(self._host.app_config)
                desc = chosen or "auto-detect"
                self.log_line(f"✓ Audio source language set to: [b]{desc}[/b]")
                self.refresh_status()

        self._host.push_screen(
            LanguagePickerScreen(
                "Audio source language (Enter empty for auto-detect)",
                current=self._host.app_config.transcription.language,
            ),
            _on_lang,
        )

    def _cmd_lang(self, arg: str) -> None:
        self._cmd_language(arg)

    def _cmd_wizard(self, arg: str) -> None:
        from subforge.tui.screens.setup_wizard import FirstRunSetupScreen

        self._host.push_screen(
            FirstRunSetupScreen(
                initial_config=self._host.app_config.model_copy(deep=True),
                on_done=self.reload_config,
            )
        )

    def _cmd_status(self, arg: str) -> None:
        project_dir = self._require_project()
        if project_dir is None:
            return
        project = load_project(project_dir)
        self.log_line(f"project [b]{project.project.name}[/b]")
        for stage in ALL_STAGES:
            self.log_line(f"  {stage:<14} {_glyph(project.get_stage(stage))}")
        src = project.project.source_language or "(auto)"
        self.log_line(f"  language       source={src}")

    def _cmd_help(self, arg: str) -> None:
        rows = [
            ("/new <audio>", "create project + import audio"),
            ("/open [name|n]", "list/open recent projects"),
            ("/projects", "manage/open projects"),
            ("/delete [name]", "delete project"),
            ("/models", "manage & select Whisper GGML models"),
            ("/language [lang]", "set default audio source language"),
            ("/transcribe", "run transcription"),
            ("/review", "edit & review caption segments"),
            ("/export [formats]", "export SRT/ASS"),
            ("/wizard", "re-run guided setup"),
            ("/status", "pipeline stage states"),
            ("/quit", "exit"),
        ]
        self.log_line("[b]commands[/b]")
        for cmd, desc in rows:
            self.log_line(f"  [b]{cmd:<20}[/b] {desc}")
        self.log_line("[dim]leading '/' optional · ↑↓ recalls commands · esc backs out of overlays[/dim]")
        self.log_line("[dim]copy: drag mouse over transcript to select · right-click or Ctrl+C copies · Ctrl+C again quits[/dim]")

    def _cmd_quit(self, arg: str) -> None:
        self._host.exit()

    def action_cancel_or_prompt(self) -> None:
        if self._autocomplete_visible():
            self._hide_autocomplete()
            return
        if self.locate_mode == "new":
            self.exit_locate_mode()
            self.log_line("[dim]locate cancelled[/dim]")
            return
        self.query_one("#prompt", Input).focus()

    def action_quit(self) -> None:
        """Ctrl+C: copy an active mouse selection, otherwise quit (terminal UX)."""
        selection = self.get_selected_text() if self.selections else None
        if selection:
            self._host.copy_to_clipboard(selection)
            self.clear_selection()
            self.log_line("[green]✓[/green] selection copied to clipboard")
            self._set_status("copied selection · Ctrl+C again to quit")
            return
        self._host.exit()
