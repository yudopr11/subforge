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
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView

from subforge.app.export import export_subtitles
from subforge.app.pipeline import Pipeline, StageError
from subforge.app.project_store import load_project
from subforge.app.projects import create_project_from_audio, find_audio_file
from subforge.app.provider_factory import build_pipeline, build_translation_service
from subforge.tui.screens.caption_review import CaptionReviewScreen
from subforge.tui.screens.project import NewProjectScreen, OpenProjectScreen, TargetLanguageScreen
from subforge.tui.screens.review_translate import ReviewTranslateScreen
from subforge.tui.screens.settings import SettingsScreen

if TYPE_CHECKING:
    from subforge.tui.app import SubForgeApp

ACTIONS: list[tuple[str, str]] = [
    ("select-audio", "Select Audio / Open Project"),
    ("transcribe", "Transcribe"),
    ("review-captions", "Review Captions"),
    ("translate", "Translate"),
    ("review-translation", "Review Translation"),
    ("export", "Export SRT / ASS"),
]


class MainMenuScreen(Screen[None]):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("n", "new_project", "New"),
        ("o", "open_project", "Open"),
        ("s", "settings", "Settings"),
    ]

    @property
    def _host(self) -> "SubForgeApp":
        """The running SubForgeApp (typed access to session state)."""
        return cast("SubForgeApp", self.app)

    def __init__(self, pipeline_factory: Callable[[Path], Pipeline] | None = None) -> None:
        super().__init__()
        # Test seam: override how Pipelines are constructed. Default builds from AppConfig.
        self.pipeline_factory = pipeline_factory

    # ---- rendering -------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]SUBFORGE[/b] — local-first subtitles")
            yield ListView(
                *[ListItem(Label(label), name=slug) for slug, label in ACTIONS],
                classes="action-list",
                id="actions",
            )
            yield Label("Status: Ready — open a project to begin (n=new · o=open · s=settings)", id="status")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        handlers = {
            "select-audio": self.action_new_project,
            "transcribe": self._begin_transcribe,
            "review-captions": self._show_caption_review,
            "translate": self._begin_translate,
            "review-translation": self._show_translation_review,
            "export": self._begin_export,
        }
        handler = handlers.get(event.item.name or "")
        if handler is not None:
            event.stop()
            handler()

    # ---- project selection ----------------------------------------------

    def action_new_project(self) -> None:
        if self._host.project_dir is None:
            self._host.push_screen(NewProjectScreen(), self._project_chosen)
        else:
            self._host.push_screen(OpenProjectScreen(), self._project_opened)

    def action_open_project(self) -> None:
        self._host.push_screen(OpenProjectScreen(), self._project_opened)

    def _project_chosen(self, audio_path: Path | None) -> None:
        if audio_path is None:
            return
        try:
            directory = create_project_from_audio(audio_path)
        except ValueError as exc:
            self._set_status(str(exc))
            return
        self._host.project_dir = directory
        self._set_status(f"Project ready: {directory.name}")

    def _project_opened(self, directory: Path | None) -> None:
        if directory is None:
            return
        self._host.project_dir = directory
        name = load_project(directory).project.name
        self._set_status(f"Project opened: {name}")

    # ---- settings ---------------------------------------------------------

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

    def _launch_stage(self, work: Callable[[], str]) -> None:
        """Run a blocking stage off the UI thread; surface its status message."""

        def runner() -> None:
            try:
                message = work()
            except StageError as exc:
                message = str(exc)
            except Exception as exc:  # noqa: BLE001 — last-resort guard for the UI thread
                message = f"[ERROR] {exc}"
            self._host.call_from_thread(self._set_status, message)

        self.run_worker(runner, thread=True, exclusive=True, group="stage")

    def _begin_transcribe(self) -> None:
        if self._require_project() is not None:
            self._launch_stage(self.do_transcribe)

    def _begin_translate(self) -> None:
        if self._require_project() is None:
            return
        self._host.push_screen(TargetLanguageScreen(), self._language_chosen)

    def _language_chosen(self, language: str | None) -> None:
        if language is not None:
            self._launch_stage(lambda: self.do_translate(language))

    def _begin_export(self) -> None:
        if self._require_project() is not None:
            self._launch_stage(self.do_export)

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

