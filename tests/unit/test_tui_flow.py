"""End-to-end TUI wiring tests: menu actions drive app services via seams.

All blocking calls go through the synchronous ``do_*`` methods; workers are
only wrappers for real interactive use and are not exercised here.
"""

from pathlib import Path

from subforge.app.export import export_subtitles
from subforge.app.pipeline import Pipeline
from subforge.app.project_store import create_project, load_project
from subforge.config.app_config import AppConfig
from subforge.models.project import ProjectMeta, StageState
from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.base import TranslationInput, TranslationOutput
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.main_menu import ACTIONS, MainMenuScreen


class FakeASR:
    def __init__(self, transcript: Transcript):
        self.transcript = transcript

    def transcribe(self, audio_path, language=None):
        return self.transcript


class FakeTranslator:
    def translate(
        self,
        segments: list[TranslationInput],
        source_language: str,
        target_language: str,
        reasoning_effort: str | None = None,
    ):
        return [TranslationOutput(id=s.id, text=f"EN:{s.text}") for s in segments]


def fake_pipeline_factory(tmp_path: Path):
    def factory(project_dir: Path) -> Pipeline:
        transcript = Transcript(language="id", segments=[TranscriptSegment(id=1, start=1.0, end=2.0, text="halo")])
        from subforge.app.translation_service import TranslationService

        return Pipeline(
            project_dir,
            _settings(),
            transcription=FakeASR(transcript),
            translation_service=TranslationService(FakeTranslator()),
        )

    return factory


def _settings():
    from subforge.config.settings import Settings

    return Settings()


def seed_audio(tmp_path: Path) -> Path:
    src = tmp_path / "episode.wav"
    src.write_bytes(b"RIFF-fake")
    return src


async def test_menu_lists_all_actions():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        labels = [str(item.children[0].render()) for item in app.screen.query_one(".action-list").children]
        assert labels == [label for _, label in ACTIONS]


async def test_new_project_then_transcribe_translate_export(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path / "projects"))
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.screen
        assert isinstance(menu, MainMenuScreen)
        menu.pipeline_factory = fake_pipeline_factory(tmp_path)

        # simulate the NewProjectScreen dismissal callback with an audio path
        audio = seed_audio(tmp_path)
        menu._project_chosen(audio)
        await pilot.pause()

        assert app.project_dir is not None
        project = load_project(app.project_dir)
        assert project.project.name == "episode"
        assert (app.project_dir / "audio" / "episode.wav").exists()

        status = menu.do_transcribe()
        assert "complete" in status
        assert "2" not in status  # one caption

        status = menu.do_translate("en")
        assert "'en' complete" in status

        status = menu.do_export()
        assert "en.srt" in status
        exports = app.project_dir / "exports"
        assert {p.name for p in exports.iterdir()} == {"source.srt", "source.ass", "en.srt", "en.ass"}
        final = load_project(app.project_dir)
        assert final.get_stage("transcription") is StageState.COMPLETED
        assert final.get_stage("export") is StageState.COMPLETED


async def test_do_transcribe_reports_missing_provider_as_error_status(tmp_path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    (d / "audio" / "a.wav").write_bytes(b"x")
    app = SubForgeApp(project_dir=d, app_config=AppConfig())  # nothing configured
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.screen
        assert isinstance(menu, MainMenuScreen)

        status = menu.do_transcribe()
        assert status.startswith("[ERROR] No transcription provider configured")

        # transcription never produced segments, so that is the accurate diagnosis
        status = menu.do_translate("en")
        assert status.startswith("[ERROR] No captions to translate")


async def test_require_project_without_project_sets_error_status():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.screen
        assert isinstance(menu, MainMenuScreen)

        assert menu.do_transcribe() == "[ERROR] No project open."
        assert "No project open" in str(menu.query_one("#status").render())


async def test_open_existing_project(tmp_path):
    d = create_project(tmp_path / "p", ProjectMeta(name="opened", source_language="id"))
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.screen
        assert isinstance(menu, MainMenuScreen)

        menu._project_opened(d)
        await pilot.pause()

        assert app.project_dir == d
        assert "Project opened: opened" in str(menu.query_one("#status").render())


def _keep_export_import_referenced() -> None:
    assert export_subtitles is not None
