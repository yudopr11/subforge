import pytest

from subforge.app.model_manager import KNOWN_WHISPER_MODELS, LocalModelManager
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.model_manager import ModelManagerScreen


def cached(models: set[str]):
    return lambda repo_id: any(m in repo_id for m in models)


def make_manager(
    installed: set[str],
    downloads: list[str] | None = None,
    deletions: list[str] | None = None,
) -> LocalModelManager:
    def downloader(model_id):
        if downloads is not None:
            downloads.append(model_id)
        installed.add(model_id)
        return f"/cache/{model_id}"

    def deleter(model_id):
        if deletions is not None:
            deletions.append(model_id)
        if model_id in installed:
            installed.remove(model_id)
            return True
        return False

    return LocalModelManager(
        cache_checker=cached(installed),
        downloader=downloader,
        deleter=deleter,
    )


async def test_table_lists_profiles_and_install_status():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelManagerScreen(manager=make_manager({"small"}))
        await app.push_screen(screen)
        await pilot.pause()

        table = screen.query_one("DataTable")
        assert table.row_count == len(KNOWN_WHISPER_MODELS)
        # public seam returns the same data the table shows
        infos = {i.id: i for i in screen.list_models()}
        assert infos["small"].installed is True
        assert infos["large-v3"].installed is False


async def test_install_downloads_then_marks_installed():
    downloads: list[str] = []
    app = SubForgeApp()
    async with app.run_test() as pilot:
        manager = make_manager(set(), downloads)
        screen = ModelManagerScreen(manager=manager)
        await app.push_screen(screen)
        await pilot.pause()

        status = screen.install("base")
        await pilot.pause()

        assert "base" in downloads
        assert "installed" in status.lower()
        assert screen.query_one("#mm-status").render()


async def test_install_selected_via_row_selection():
    downloads: list[str] = []
    app = SubForgeApp()
    async with app.run_test() as pilot:
        manager = make_manager(set(), downloads)
        screen = ModelManagerScreen(manager=manager)
        await app.push_screen(screen)
        await pilot.pause()

        # Pressing 'i' triggers install on the cursor row without dismissing
        await pilot.press("i")
        await pilot.pause()

        assert len(downloads) == 1
        assert "installed" in str(screen.query_one("#mm-status").render())


def test_unknown_model_surfaces_error_message():
    manager = make_manager(set())
    with pytest.raises(ValueError, match="unknown local model"):
        manager.install("nonexistent")


async def test_delete_model_screen_action():
    deletions: list[str] = []
    installed = {"small"}
    app = SubForgeApp()
    async with app.run_test() as pilot:
        manager = make_manager(installed, deletions=deletions)
        screen = ModelManagerScreen(manager=manager)
        await app.push_screen(screen)
        await pilot.pause()

        status = screen.delete("small")
        await pilot.pause()

        assert "small" in deletions
        assert "deleted" in status.lower()
        assert screen.list_models()[2].installed is False


async def test_delete_selected_via_dialog():
    deletions: list[str] = []
    # Index 0 in KNOWN_WHISPER_MODELS is 'tiny'
    installed = {"tiny"}
    app = SubForgeApp()
    async with app.run_test() as pilot:
        manager = make_manager(installed, deletions=deletions)
        screen = ModelManagerScreen(manager=manager)
        await app.push_screen(screen)
        await pilot.pause()

        from subforge.tui.screens.confirm_dialog import ConfirmDialogScreen

        # Press 'd' to trigger delete modal
        await pilot.press("d")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDialogScreen)
        # Confirm with 'y'
        await pilot.press("y")
        await pilot.pause()

        assert "tiny" in deletions
        assert "tiny" not in installed


async def test_enter_on_installed_model_dismisses_with_model_id():
    selected_result: list[str | None] = []
    app = SubForgeApp()
    async with app.run_test() as pilot:
        # 'tiny' is at index 0 and installed
        manager = make_manager({"tiny"})
        screen = ModelManagerScreen(manager=manager)
        await app.push_screen(screen, callback=lambda res: selected_result.append(res))
        await pilot.pause()

        # Press Enter on 'tiny'
        await pilot.press("enter")
        await pilot.pause()

        assert selected_result == ["tiny"]


async def test_enter_on_uninstalled_model_installs_and_dismisses():
    selected_result: list[str | None] = []
    downloads: list[str] = []
    app = SubForgeApp()
    async with app.run_test() as pilot:
        manager = make_manager(set(), downloads=downloads)
        screen = ModelManagerScreen(manager=manager)
        await app.push_screen(screen, callback=lambda res: selected_result.append(res))
        await pilot.pause()

        # Press Enter on index 0 ('tiny')
        await pilot.press("enter")
        await pilot.pause()

        assert "tiny" in downloads
        assert selected_result == ["tiny"]


async def test_press_i_installs_without_dismissing():
    selected_result: list[str | None] = []
    downloads: list[str] = []
    app = SubForgeApp()
    async with app.run_test() as pilot:
        manager = make_manager(set(), downloads=downloads)
        screen = ModelManagerScreen(manager=manager)
        await app.push_screen(screen, callback=lambda res: selected_result.append(res))
        await pilot.pause()

        # Press 'i' on index 0 ('tiny')
        await pilot.press("i")
        await pilot.pause()

        assert "tiny" in downloads
        assert selected_result == []  # Not dismissed
        assert isinstance(app.screen, ModelManagerScreen)


