from pathlib import Path

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.tui.app import SubForgeApp
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


class FakePlayer:
    available = True
    name = "fake"

    def __init__(self):
        self.calls: list[tuple[float, float]] = []
        self.stopped = 0

    def play_segment(self, start: float, end: float) -> str:
        self.calls.append((start, end))
        return f"▶ {start}→{end}"

    def stop(self) -> str:
        self.stopped += 1
        return "■ stopped"


async def test_play_selected_plays_cursor_segment(tmp_path):
    d = seed(tmp_path)
    player = FakePlayer()
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = CaptionReviewScreen(d, player=player)
        await app.push_screen(screen)
        await pilot.pause()

        status = screen.play_selected()
        assert player.calls == [(1.2, 3.4)]  # seeded segment timing
        assert "▶" in status

        screen.stop_playback()
        assert player.stopped == 1


async def test_play_without_audio_reports_error(tmp_path):
    d = create_project(tmp_path / "q", ProjectMeta(name="q", source_language="id"))
    project = load_project(d)
    project.segments = [Segment(id=1, start=0.0, end=1.0, source="x")]
    save_project(d, project)

    from subforge.tui.screens.caption_review import CaptionReviewScreen as CRS

    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = CRS(d, player=None)
        await app.push_screen(screen)
        await pilot.pause()
        status = screen.play_selected()
        assert "[ERROR]" in status
