"""Searchable project picker tests (PRD §7 /open flow)."""

from pathlib import Path

from subforge.app.project_store import create_project
from subforge.models.project import ProjectMeta
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.project import ProjectPickerScreen


def make_projects(tmp_path: Path) -> list[Path]:
    d1 = create_project(tmp_path / "episode-one", ProjectMeta(name="episode-one", source_language="id"))
    d2 = create_project(tmp_path / "episode-two", ProjectMeta(name="episode-two", source_language="id"))
    return [d2, d1]  # recent first


def _options(picker: ProjectPickerScreen) -> list[str]:
    return [str(o.prompt) for o in picker.query_one("#projects").options]


async def test_lists_projects_recent_first_with_create_new(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ProjectPickerScreen(make_projects(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        options = _options(picker)
        assert options[0].startswith("[+] Create new")
        assert "episode-two" in options[1]  # recent first
        assert "episode-one" in options[2]


async def test_typing_filters_and_enter_selects(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ProjectPickerScreen(make_projects(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        search = picker.query_one("#project-search")
        search.value = "two"
        await pilot.pause()

        filtered = _options(picker)
        assert len(filtered) == 1 and "episode-two" in filtered[0]
        assert not any(o.startswith("[+]") for o in filtered)  # create-new hidden

        picker.on_input_submitted(type("Evt", (), {"input": search})())
        await pilot.pause()
        assert isinstance(picker.result, Path)
        assert picker.result.name == "episode-two"


async def test_arrows_move_highlight_and_tab_selects(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ProjectPickerScreen(make_projects(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        search = picker.query_one("#project-search")
        search.value = "episode"
        await pilot.pause()
        assert picker.query_one("#projects").highlighted == 0

        await pilot.press("down")
        await pilot.pause()
        assert picker.query_one("#projects").highlighted == 1

        await pilot.press("tab")
        await pilot.pause()
        assert isinstance(picker.result, Path)
        assert picker.result.name == "episode-one"


async def test_create_new_row_dismisses_new(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ProjectPickerScreen(make_projects(tmp_path))
        result: list[object] = []
        await app.push_screen(picker, lambda r: result.append(r))
        await pilot.pause()

        await pilot.press("down")  # highlight the + create-new row (index 0)
        await pilot.pause()
        # go back up to it, then Enter selects the highlighted row
        await pilot.press("up")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert result == [ProjectPickerScreen.NEW]


async def test_escape_cancels_without_selecting(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ProjectPickerScreen(make_projects(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
        assert picker.result is None