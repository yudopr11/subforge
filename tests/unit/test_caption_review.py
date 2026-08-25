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


async def test_table_shows_segments_and_edit_is_memory_only(tmp_path):
    """Enter updates the table in memory; Ctrl+S persists (PRD §9)."""
    d = seed(tmp_path)
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await app.push_screen(CaptionReviewScreen(d))
        await pilot.pause()
        table = app.screen.query_one("DataTable")
        assert table.row_count == 1

        app.screen.apply_edit(1, "Halo semua!")
        await pilot.pause()

        # NOT on disk until Ctrl+S
        assert load_project(d).segments[0].source == "Halo semuanya!"
        assert app.screen._dirty is True
        status = app.screen.query_one("#status").render()
        assert "unsaved" in str(status)

        await pilot.press("ctrl+s")
        await pilot.pause()
        assert load_project(d).segments[0].source == "Halo semua!"
        assert app.screen._dirty is False
        assert "saved" in str(app.screen.query_one("#status").render())


async def test_undo_redo_edits(tmp_path):
    d = seed(tmp_path)
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = CaptionReviewScreen(d)
        await app.push_screen(screen)
        await pilot.pause()

        screen.apply_edit(1, "Halo semua!")
        screen.apply_edit(1, "Halo!")  # second edit clears redo tail
        assert screen._history.count == 2

        await pilot.press("ctrl+z")
        await pilot.pause()
        assert screen.project.segments[0].source == "Halo semua!"  # undo
        await pilot.press("ctrl+z")
        await pilot.pause()
        assert screen.project.segments[0].source == "Halo semuanya!"  # deeper undo

        await pilot.press("ctrl+y")
        await pilot.pause()
        assert screen.project.segments[0].source == "Halo semua!"  # redo
        await pilot.press("ctrl+y")
        await pilot.pause()
        assert screen.project.segments[0].source == "Halo!"  # full redo

        # nothing on disk yet
        assert load_project(d).segments[0].source == "Halo semuanya!"


async def test_new_edit_after_undo_clears_redo(tmp_path):
    d = seed(tmp_path)
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = CaptionReviewScreen(d)
        await app.push_screen(screen)
        await pilot.pause()

        screen.apply_edit(1, "A")
        screen.apply_edit(1, "B")
        screen.action_undo()  # -> "A"
        screen.apply_edit(1, "C")  # redo tail (["B"]) must be dropped
        assert screen._history.can_redo() is False
        screen.action_redo()
        assert screen.project.segments[0].source == "C"  # no-op redo path

        await pilot.pause()


async def test_escape_requires_confirm_with_unsaved_changes(tmp_path):
    d = seed(tmp_path)
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = CaptionReviewScreen(d)
        await app.push_screen(screen)
        await pilot.pause()

        screen.apply_edit(1, "edited!")
        await pilot.press("escape")
        await pilot.pause()
        assert screen in app.screen_stack  # first Esc only warns

        await pilot.press("escape")
        await pilot.pause()
        assert screen not in app.screen_stack  # second Esc discards
        assert load_project(d).segments[0].source == "Halo semuanya!"  # nothing saved


async def test_escape_without_changes_exits_directly(tmp_path):
    d = seed(tmp_path)
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = CaptionReviewScreen(d)
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
        assert screen not in app.screen_stack


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

    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = CaptionReviewScreen(d, player=None)
        await app.push_screen(screen)
        await pilot.pause()
        status = screen.play_selected()
        assert "[ERROR]" in status