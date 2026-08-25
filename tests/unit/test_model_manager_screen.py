import pytest

from subforge.app.model_manager import KNOWN_WHISPER_MODELS, LocalModelManager
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.model_manager import ModelManagerScreen


def cached(models: set[str]):
    return lambda repo_id: any(m in repo_id for m in models)


def make_manager(installed: set[str], downloads: list[str] | None = None) -> LocalModelManager:
    def downloader(model_id):
        if downloads is not None:
            downloads.append(model_id)
        installed.add(model_id)
        return f"/cache/{model_id}"

    return LocalModelManager(cache_checker=cached(set(installed)), downloader=downloader)


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


def test_unknown_model_surfaces_error_message():
    manager = make_manager(set())
    with pytest.raises(ValueError, match="unknown local model"):
        manager.install("nonexistent")
