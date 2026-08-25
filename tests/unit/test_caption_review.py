from pathlib import Path

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.tui.screens.caption_review import CaptionReviewScreen


def seed(tmp_path: Path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    project = load_project(d)
    project.segments = [Segment(id=1, start=1.2, end=3.4, source="Halo semuanya!")]
    save_project(d, project)
    return d


async def test_table_shows_segments_and_edit_saves(tmp_path):
    d = seed(tmp_path)
    from subforge.tui.app import SubForgeApp

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await app.push_screen(CaptionReviewScreen(d))
        await pilot.pause()
        table = app.screen.query_one("DataTable")
        assert table.row_count == 1

        # Simulate an edit commit through the screen's public method (logic under test).
        app.screen.apply_edit(1, "Halo semua!")
        await pilot.pause()

        assert load_project(d).segments[0].source == "Halo semua!"
