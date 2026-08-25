"""Subtitle REPL — transcript-driven home screen (PRD §7, pi/coding-CLI style).

Presentation only (ARCH §3.1/§3.2): slash commands route to `app/*` services.
The transcript is the interface; every action writes an event line.
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, RichLog

from subforge.app.export import export_subtitles
from subforge.app.pipeline import ALL_STAGES, Pipeline, StageError
from subforge.app.project_store import load_project, save_project
from subforge.app.projects import create_project_from_audio, discover_projects, find_audio_file
from subforge.app.provider_factory import (
    build_pipeline,
    transcription_configured,
    translation_configured,
)
from subforge.models.project import StageState

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp


def _glyph(state: StageState) -> str:
    return {
        StageState.PENDING: "○",
        StageState.RUNNING: "●",
        StageState.COMPLETED: "[green]✓[/green]",
        StageState.FAILED: "[red]✗[/red]",
        StageState.SKIPPED: "[dim]–[/dim]",
    }[state]


class ReplScreen(Screen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("escape", "focus_prompt", "Prompt"),
    ]

    AUTO_FOCUS = "#prompt"

    def __init__(self, pipeline_factory: Callable[[Path], Pipeline] | None = None) -> None:
        super().__init__()
        self.pipeline_factory = pipeline_factory  # test seam
        self._running_stages: set[str] = set()
        self._recent_listing: list[Path] = []

    @property
    def _host(self) -> "SubForgeApp":
        from subforge.tui.app import SubForgeApp

        app: SubForgeApp = self.app  # type: ignore[assignment]
        return app

    # ---- layout ----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Label("", id="status-bar")
        with Vertical():
            yield RichLog(id="transcript", markup=True, wrap=True, highlight=False)
            yield Input(placeholder="Type a command… (? for help)", id="prompt")

    def on_mount(self) -> None:
        self.log_line("[b]subforge[/b] v0.1.0 — local-first subtitles")
        if self._host.project_dir is not None:
            self.log_line(f"▸ opened '[b]{self._host.project_dir.name}[/b]'")
        else:
            self.log_line("Type [b]/new <audio-file>[/b] to start, or [b]?[/b] for help.")
            self._hint_setup_if_needed()
        self.refresh_status()

    # ---- transcript + status ----------------------------------------------

    def log_line(self, text: str = "") -> None:
        self.query_one("#transcript", RichLog).write(text)

    def _set_status(self, message: str) -> None:
        self.query_one("#status-bar", Label).update(message)

    def refresh_status(self) -> None:
        """Footer status line: project · stage glyphs · active models."""
        host = self._host
        parts: list[str] = []
        project_dir = host.project_dir
        model_bits: list[str] = []
        tc = host.app_config.transcription
        tl = host.app_config.translation
        if tc.model:
            model_bits.append(f"asr:{tc.provider}:{tc.model}")
        if tl.model:
            src = tl.provider if tl.source == "provider" else "local"
            model_bits.append(f"mt:{src}:{tl.model}")

        if project_dir is None:
            parts.append("[dim]no project[/dim]")
        else:
            parts.append(f"[b]{project_dir.name}[/b]")
            project = load_project(project_dir)
            shown: dict[str, StageState] = {s: project.get_stage(s) for s in ALL_STAGES}
            for key in sorted(project.stages):
                if key.startswith("translation_"):
                    shown[key.replace("translation_", "tl:")] = project.get_stage(key)
            for label in sorted(shown):
                if shown[label] is not StageState.PENDING or label == "transcription":
                    parts.append(f"{label} {_glyph(shown[label])}")
        if model_bits:
            parts.append(" · ".join(model_bits))
        busy = f" · ⏳ {'/'.join(sorted(self._running_stages))}" if self._running_stages else ""
        self._set_status(" · ".join(parts) + busy)

    def reload_config(self) -> None:
        """Reload AppConfig after settings/wizard changes."""
        from subforge.config.app_config import load_app_config

        self._host.app_config = load_app_config()
        self.refresh_status()
        self.log_line("▸ configuration reloaded")

    # ---- input -------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "prompt":
            return
        raw = event.value.strip()
        self.log_line(f"[dim]>[/dim] {raw}")
        event.input.clear()
        if raw in {"?", "help"}:
            self.run_command("/help")
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
            self.log_line('[dim]tip: no transcribe provider yet — run /settings or /wizard[/dim]')
        if not translation_configured(cfg):
            self.log_line('[dim]tip: no translate provider yet — run /settings or /wizard[/dim]')

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
                self._host.call_from_thread(self._running_stages.discard, stage)
            self._host.call_from_thread(self._log_result, message)

        self.run_worker(runner, thread=True, exclusive=False, group=f"stage-{stage}")

    def _log_result(self, message: str) -> None:
        ok = not message.startswith(("[ERROR]", "[SETUP]"))
        glyph = "✓" if ok else "✗"
        color = "green" if ok else "red"
        self.log_line(f"[{color}]{glyph}[/{color}] {message}")
        self.refresh_status()

    # ---- commands -----------------------------------------------------------

    def _cmd_new(self, arg: str) -> None:
        if not arg:
            self.log_line("usage: /new <path-to-audio.(wav|flac|mp3|…)>")
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
            self._recent_listing = projects
            self.log_line("recent projects:")
            for i, proj in enumerate(projects, 1):
                self.log_line(f"  {i}. [b]{proj.name}[/b] · {proj}")
            self.log_line("open one with: /open <number-or-name>")
            return
        target: Path | None = None
        if arg.isdigit() and self._recent_listing:
            idx = int(arg) - 1
            if 0 <= idx < len(self._recent_listing):
                target = self._recent_listing[idx]
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
                "[SETUP] No transcription provider yet — run /settings or /wizard first."
            )
            return
        pipeline = self._make_pipeline(project_dir)

        def work() -> str:
            pipeline.run_transcription(audio.name)
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

    def _cmd_translate(self, arg: str) -> None:
        if "translation" in self._running_stages:
            self.log_line("[yellow]⏳[/yellow] translation already running…")
            return
        project_dir = self._require_project()
        if project_dir is None:
            return
        language = arg.strip().lower() or self._host.app_config.translation.default_target
        if not language:
            from subforge.tui.screens.project import TargetLanguageScreen

            self._host.push_screen(
                TargetLanguageScreen(),
                lambda lang: self._begin_translate(str(lang)) if lang else None,
            )
            return
        self._begin_translate(language)

    def _begin_translate(self, language: str) -> None:
        seam = self.pipeline_factory is not None
        if not seam and not translation_configured(self._host.app_config):
            self.log_line(
                "[SETUP] No translation provider yet — run /settings or /wizard first."
            )
            return
        project_dir = self._require_project()
        if project_dir is None:
            return
        pipeline = self._make_pipeline(project_dir)

        def work() -> str:
            pipeline.run_translation(language)
            n = sum(1 for s in pipeline.load().segments if language in s.translations)
            return f"translated to '{language}' — {n} segments"

        self._launch_stage("translation", work, f"translating to '{language}'")
        self._host.app_config.translation.default_target = language

    def _cmd_export(self, arg: str) -> None:
        formats = [f.strip() for f in arg.split(",")] if arg else ["srt", "ass"]
        project_dir = self._require_project()
        if project_dir is None:
            return
        languages = [l for l in load_project(project_dir).project.target_languages if l]
        try:
            paths = export_subtitles(project_dir, formats=formats, languages=languages)
        except ValueError as exc:
            self.log_line(str(exc))
            return
        names = ", ".join(p.name for p in paths) or "(nothing to export yet)"
        self.log_line(f"▸ exported: {names}")

    def _cmd_speakers(self, arg: str) -> None:
        project_dir = self._require_project()
        if project_dir is not None:
            from subforge.tui.screens.speaker_map import SpeakerMapScreen

            self._host.push_screen(SpeakerMapScreen(project_dir))

    def _cmd_settings(self, arg: str) -> None:
        from subforge.tui.screens.settings import SettingsScreen

        self._host.push_screen(SettingsScreen(self._host.app_config, on_saved=self.reload_config))

    def _cmd_wizard(self, arg: str) -> None:
        from subforge.tui.screens.setup_wizard import FirstRunSetupScreen

        self._host.push_screen(
            FirstRunSetupScreen(
                initial_config=self._host.app_config.model_copy(deep=True),
                on_done=self.reload_config,
            )
        )

    def _cmd_models(self, arg: str) -> None:
        from subforge.app.model_manager import LocalModelManager
        from subforge.tui.screens.model_manager import ModelManagerScreen

        self._host.push_screen(ModelManagerScreen(manager=LocalModelManager()))

    def _cmd_status(self, arg: str) -> None:
        project_dir = self._require_project()
        if project_dir is None:
            return
        project = load_project(project_dir)
        self.log_line(f"project [b]{project.project.name}[/b]")
        for stage in ALL_STAGES:
            self.log_line(f"  {stage:<14} {_glyph(project.get_stage(stage))}")
        for key in sorted(project.stages):
            if key.startswith("translation_"):
                self.log_line(f"  {key:<14} {_glyph(project.get_stage(key))}")
        src = project.project.source_language or "(auto)"
        targets = ", ".join(project.project.target_languages) or "(none)"
        self.log_line(f"  languages      source={src} · targets={targets}")

    def _cmd_help(self, arg: str) -> None:
        rows = [
            ("/new <audio>", "create project + import audio"),
            ("/open [name|n]", "list/open recent projects"),
            ("/transcribe", "run transcription"),
            ("/review", "caption review overlay"),
            ("/translate [lang]", "translate (default target remembered)"),
            ("/export [formats]", "export SRT/ASS"),
            ("/speakers", "name diarization speakers"),
            ("/settings", "manual provider/model settings"),
            ("/wizard", "re-run guided setup"),
            ("/models", "local whisper model manager"),
            ("/status", "pipeline stage states"),
            ("/quit", "exit"),
        ]
        self.log_line("[b]commands[/b]")
        for cmd, desc in rows:
            self.log_line(f"  [b]{cmd:<20}[/b] {desc}")
        self.log_line("[dim]leading '/' optional · esc backs out of overlays[/dim]")

    def _cmd_quit(self, arg: str) -> None:
        self._host.exit()

    def action_focus_prompt(self) -> None:
        self.query_one("#prompt", Input).focus()

    def action_quit(self) -> None:
        self._host.exit()
