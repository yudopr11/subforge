"""Stage re-entry guards and screen dismissal behavior."""

from pathlib import Path

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.caption_review import CaptionReviewScreen
from subforge.tui.screens.repl import ReplScreen


def seed_segments(tmp_path: Path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    project = load_project(d)
    project.segments = [Segment(id=1, start=1.0, end=2.0, source="halo")]
    save_project(d, project)
    return d


async def test_escape_returns_to_repl_home(tmp_path):
    d = seed_segments(tmp_path)
    app = SubForgeApp(project_dir=d)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = CaptionReviewScreen(d)
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ReplScreen)
