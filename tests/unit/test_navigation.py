"""Stage re-entry guards and screen dismissal behavior."""

from pathlib import Path

import pytest

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.caption_review import CaptionReviewScreen
from subforge.tui.screens.main_menu import MainMenuScreen
from subforge.tui.screens.review_translate import ReviewTranslateScreen
from subforge.tui.screens.speaker_map import SpeakerMapScreen


async def test_transcribe_busy_guard_blocks_second_run(tmp_path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    (d / "audio" / "a.wav").write_bytes(b"x")
    app = SubForgeApp(project_dir=d)
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.screen
        assert isinstance(menu, MainMenuScreen)

        menu._running_stages.add("transcription")  # simulate a run in flight
        menu._begin_transcribe()
        await pilot.pause()

        status = str(menu.query_one("#status").render())
        assert "already" in status.lower()
        assert "transcription" in status.lower()


async def test_translate_busy_guard(tmp_path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    app = SubForgeApp(project_dir=d)
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.screen
        assert isinstance(menu, MainMenuScreen)

        menu._running_stages.add("translation")
        menu._language_chosen("en")
        await pilot.pause()

        assert "already" in str(menu.query_one("#status").render()).lower()


def seed_segments(tmp_path: Path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id", target_languages=["en"]))
    project = load_project(d)
    project.segments = [Segment(id=1, start=1.0, end=2.0, source="halo", translations={"en": "hello"})]
    save_project(d, project)
    return d


@pytest.mark.parametrize(
    "screen_factory",
    [
        lambda d: CaptionReviewScreen(d),
        lambda d: ReviewTranslateScreen(d),
        lambda d: SpeakerMapScreen(d),
    ],
)
async def test_escape_returns_to_main_menu(tmp_path, screen_factory):
    from subforge.app.translation_service import TranslationService

    d = seed_segments(tmp_path)
    app = SubForgeApp(project_dir=d)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = screen_factory(d)
        if isinstance(screen, ReviewTranslateScreen):
            screen.service = TranslationService(provider=None)  # type: ignore[arg-type]
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, MainMenuScreen)
