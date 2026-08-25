from subforge.tui.app import SubForgeApp
from subforge.tui.screens.model_picker import ModelPickerScreen


class _Evt:
    def __init__(self, prompt: str) -> None:
        self.option = type("Opt", (), {"prompt": prompt})()


async def test_picker_lists_models_and_returns_selection():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen("Choose translation model", lambda: ["glm-5.2", "kimi-k3"])
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("OptionList").option_count == 2
        screen.on_option_list_option_selected(_Evt("kimi-k3"))
        await pilot.pause()
        assert screen.result == "kimi-k3"


async def test_empty_model_list_shows_hint():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen("Choose model", list)
        await app.push_screen(screen)
        await pilot.pause()
        assert "No models found" in str(screen.query_one("#picker-status").render())
