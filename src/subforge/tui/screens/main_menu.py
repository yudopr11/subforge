"""Main menu: wires user actions to app-layer services (ARCH §3.1).

Blocking stage work runs in thread workers; the synchronous ``do_*`` methods
contain the actual orchestration calls and are the tested seam.
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView

from subforge.app.export import export_subtitles
from subforge.app.pipeline import Pipeline, StageError
from subforge.app.project_store import load_project
from subforge.app.projects import create_project_from_audio, discover_projects, find_audio_file
from subforge.app.provider_factory import (
    build_pipeline,
    build_translation_service,
    transcription_configured,
    translation_configured,
)
from subforge.models.project import StageState
from subforge.tui.screens.caption_review import CaptionReviewScreen
from subforge.tui.screens.project import (
    NewProjectScreen,
    OpenProjectScreen,
    ProjectPickerScreen,
    TargetLanguageScreen,
)
from subforge.tui.screens.review_translate import ReviewTranslateScreen
from subforge.tui.screens.settings import SettingsScreen
from subforge.tui.screens.speaker_map import SpeakerMapScreen

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp

ACTIONS: list[tuple[str, str]] = [
    ("select-audio", "Select Audio / Open Project"),
    ("transcribe", "Transcribe"),
    ("review-captions", "Review Captions"),
    ("translate", "Translate"),
    ("review-translation", "Review Translation"),
    ("export", "Export SRT / ASS"),
    ("settings", "Settings"),
]


class MainMenuScreen(Screen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("n", "new_project", "New"),
        ("o", "open_project", "Open"),
        ("s", "settings", "Settings"),
        ("m", "speakers", "Speakers"),
    ]

    @property
    def _host(self) -> "SubForgeApp":
        """The running SubForgeApp (typed access to session state)."""
        return cast("SubForgeApp", self.app)

    def __init__(self, pipeline_factory: Callable[[Path], Pipeline] | None = None) -> None:
        super().__init__()
        # Test seam: override how Pipelines are constructed. Default builds from AppConfig.
        self.pipeline_factory = pipeline_factory
        self._running_stages: set[str] = set()

    # ---- rendering -------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]SUBFORGE[/b] — local-first subtitles")
            yield ListView(
                *[ListItem(Label(label), name=slug) for slug, label in ACTIONS],
                classes="action-list",
                id="actions",
            )
            yield Label("Status: Ready", id="status")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        handlers = {
            "select-audio": self.action_new_project,
            "transcribe": self._begin_transcribe,
            "review-captions": self._show_caption_review,
            "translate": self._begin_translate,
            "review-translation": self._show_translation_review,
            "export": self._begin_export,
            "settings": self.action_settings,
        }
        handler = handlers.get(event.item.name or "")
        if handler is not None:
            event.stop()
            handler()

    def on_mount(self) -> None:
        if self._host.project_dir is not None:
            self._set_flow_status()

    # ---- project selection ----------------------------------------------

    def action_new_project(self) -> None:
        projects = discover_projects()
        if projects:
            self._host.push_screen(ProjectPickerScreen(projects), self._project_picked)
        else:
            self._host.push_screen(NewProjectScreen(), self._project_chosen)

    def action_open_project(self) -> None:
        self._host.push_screen(OpenProjectScreen(), self._project_opened)

    def _project_picked(self, choice: object) -> None:
        if choice is None:
            return
        if choice == ProjectPickerScreen.NEW:
            self._host.push_screen(NewProjectScreen(), self._project_chosen)
        elif isinstance(choice, Path):
            self._project_opened(choice)

    def _project_chosen(self, audio_path: Path | None) -> None:
        if audio_path is None:
            return
        try:
            directory = create_project_from_audio(audio_path)
        except ValueError as exc:
            self._set_status(str(exc))
            return
        self._host.project_dir = directory
        self._set_flow_status("Project created")

    def _project_opened(self, directory: Path | None) -> None:
        if directory is None:
            return
        self._host.project_dir = directory
        name = load_project(directory).project.name
        self._set_flow_status(f"Opened: {name}")

    # ---- settings ---------------------------------------------------------

    def action_speakers(self) -> None:
        project_dir = self._require_project()
        if project_dir is not None:
            self._host.push_screen(SpeakerMapScreen(project_dir))

    def action_settings(self) -> None:
        self._host.push_screen(
            SettingsScreen(self._host.app_config, on_saved=self._config_reloaded)
        )

    def _config_reloaded(self) -> None:
        from subforge.config.app_config import (
            load_app_config,
        )

        self._host.app_config = load_app_config()
        self._set_status("Settings saved — providers rebuilt on next action.")

    # ---- pipeline seam ----------------------------------------------------

    def _make_pipeline(self, project_dir: Path) -> Pipeline:
        if self.pipeline_factory is not None:
            return self.pipeline_factory(project_dir)
        return build_pipeline(project_dir, self._host.app_config)

    def _require_project(self) -> Path | None:
        if self._host.project_dir is None:
            self._set_status("[ERROR] No project open — select audio first (n).")
            return None
        return self._host.project_dir

    # ---- stage actions (synchronous, tested seam) --------------------------

    def do_transcribe(self) -> str:
        project_dir = self._require_project()
        if project_dir is None:
            return "[ERROR] No project open."
        audio = find_audio_file(project_dir)
        if audio is None:
            return f"[ERROR] No audio file in {project_dir / 'audio'}"
        pipeline = self._make_pipeline(project_dir)
        try:
            pipeline.run_transcription(audio.name)
        except StageError as exc:
            return str(exc)
        return f"Transcription complete — {len(pipeline.load().segments)} captions."

    def do_translate(self, target_language: str) -> str:
        project_dir = self._require_project()
        if project_dir is None:
            return "[ERROR] No project open."
        pipeline = self._make_pipeline(project_dir)
        try:
            pipeline.run_translation(target_language)
        except StageError as exc:
            return str(exc)
        count = sum(1 for s in pipeline.load().segments if target_language in s.translations)
        return f"Translation '{target_language}' complete — {count} segments."

    def do_export(self) -> str:
        project_dir = self._require_project()
        if project_dir is None:
            return "[ERROR] No project open."
        languages = [lang for lang in load_project(project_dir).project.target_languages if lang]
        try:
            paths = export_subtitles(project_dir, formats=["srt", "ass"], languages=languages)
        except ValueError as exc:
            return str(exc)
        return "Exported: " + ", ".join(p.name for p in paths)

    # ---- worker wrappers ----------------------------------------------------

    def _launch_stage(self, stage: str, work: Callable[[], str], busy_label: str) -> None:
        """Run a blocking stage off the UI thread; one run per stage at a time."""
        if stage in self._running_stages:
            self._set_status(f"[BUSY] {busy_label.capitalize()} is already running — please wait.")
            return
        self._running_stages.add(stage)
        self._set_status(f"⏳ {busy_label}… (please wait)")

        def runner() -> None:
            try:
                message = work()
            except StageError as exc:
                message = str(exc)
            except Exception as exc:  # noqa: BLE001 — last-resort guard for the UI thread
                message = f"[ERROR] {exc}"
            finally:
                self._host.call_from_thread(self._running_stages.discard, stage)
            self._host.call_from_thread(self._set_flow_status, message)

        self.run_worker(runner, thread=True, exclusive=False, group=f"stage-{stage}")

    def _begin_transcribe(self) -> None:
        if "transcription" in self._running_stages:
            self._set_status("[BUSY] Transcription is already running — please wait.")
            return
        if self._require_project() is None:
            return
        if not transcription_configured(self._host.app_config):
            self.action_settings()
            self._set_status(
                "[SETUP] No transcription provider yet — pick one here, Save, then run Transcribe again."
            )
            return
        self._launch_stage("transcription", self.do_transcribe, "Transcribing")

    def _begin_translate(self) -> None:
        if self._require_project() is None:
            return
        self._host.push_screen(TargetLanguageScreen(), self._language_chosen)

    def _language_chosen(self, language: str | None) -> None:
        if language is None:
            return
        if "translation" in self._running_stages:
            self._set_status("[BUSY] Translation is already running — please wait.")
            return
        if not translation_configured(self._host.app_config):
            self.action_settings()
            self._set_status(
                "[SETUP] No translation provider yet — pick one here, Save, then run Translate again."
            )
            return
        self._launch_stage(
            "translation", lambda: self.do_translate(language), f"Translating to '{language}'"
        )

    def _begin_export(self) -> None:
        if self._require_project() is not None:
            self._launch_stage("export", self.do_export, "Exporting")

    # ---- review screens ------------------------------------------------------

    def _show_caption_review(self) -> None:
        project_dir = self._require_project()
        if project_dir is not None:
            self._host.push_screen(CaptionReviewScreen(project_dir))

    def _show_translation_review(self) -> None:
        project_dir = self._require_project()
        if project_dir is None:
            return
        try:
            service = build_translation_service(self._host.app_config)
        except ValueError:
            service = None  # screen still supports editing + export without a provider
        self._host.push_screen(ReviewTranslateScreen(project_dir, service))

    # ---- helpers ---------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Label).update(message)

    def _flow_hint(self) -> str:
        """PRD §7 flow guidance: what the user should do next."""
        if self._host.project_dir is None:
            return "start: n new · o open"
        project = load_project(self._host.project_dir)
        stage = project.get_stage("transcription")
        if stage in (StageState.PENDING, StageState.RUNNING):
            return "next: Transcribe"
        if stage is StageState.FAILED:
            return "transcription failed — run Transcribe again"
        translated = any(s.translations for s in project.segments)
        if not translated:
            return "captions ready — next: Translate"
        if project.get_stage("export") is StageState.COMPLETED:
            return "done — files in exports/"
        return "translation ready — next: Export SRT / ASS"

    def _set_flow_status(self, message: str | None = None) -> None:
        name = self._host.project_dir.name if self._host.project_dir else None
        parts = [p for p in (message, f"Project: {name}" if name else None, self._flow_hint()) if p]
        try:
            self.query_one("#status", Label).update(" · ".join(parts))
        except NoMatches:
            pass  # status label not composed yet (unit seam)

