"""Searchable model picker tests (PRD §14 live discovery, keyboard-first)."""

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

        assert screen.query_one("#models").option_count == 2
        screen.on_option_list_option_selected(_Evt("kimi-k3"))  # direct seam
        await pilot.pause()
        assert screen.result == "kimi-k3"


async def test_empty_model_list_shows_zero_status():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen("Choose model", list)
        await app.push_screen(screen)
        await pilot.pause()
        assert "0 models" in str(screen.query_one("#picker-status").render())


async def test_loader_failure_shows_error_not_crash():
    def boom() -> list[str]:
        raise RuntimeError("network down")

    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen("Choose model", boom)
        await app.push_screen(screen)
        await pilot.pause()
        assert "Couldn't load models" in str(screen.query_one("#picker-status").render())


async def test_typing_filters_model_list():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen(
            "Choose model",
            lambda: ["glm-5.2", "gpt-4o", "gpt-4o-transcribe", "whisper-1", "kimi-k3"],
        )
        await app.push_screen(screen)
        await pilot.pause()

        search = screen.query_one("#model-search")
        search.value = "tran"
        await pilot.pause()
        options = [str(o.prompt) for o in screen.query_one("#models").options]
        assert options == ["gpt-4o-transcribe"]


async def test_search_enter_selects_filtered_model():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen(
            "Choose model", lambda: ["glm-5.2", "whisper-1", "kimi-k3"]
        )
        await app.push_screen(screen)
        await pilot.pause()

        search = screen.query_one("#model-search")
        search.value = "kim"
        await pilot.pause()
        screen.on_input_submitted(type("Evt", (), {"input": search})())
        await pilot.pause()
        assert screen.result == "kimi-k3"


async def test_arrows_move_highlight():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen(
            "Choose model", lambda: ["glm-5.2", "gpt-4o", "kimi-k3"]
        )
        await app.push_screen(screen)
        await pilot.pause()

        search = screen.query_one("#model-search")
        search.value = "g"  # matches glm-5.2 and gpt-4o
        await pilot.pause()
        assert screen.query_one("#models").highlighted == 0
        await pilot.press("down")
        await pilot.pause()
        assert screen.query_one("#models").highlighted == 1
        await pilot.press("enter")
        await pilot.pause()
        assert screen.result == "gpt-4o"


async def test_typed_custom_model_without_match_is_accepted():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen("Choose model", lambda: ["glm-5.2"])
        await app.push_screen(screen)
        await pilot.pause()

        search = screen.query_one("#model-search")
        search.value = "my-custom-model"
        await pilot.pause()
        screen.on_input_submitted(type("Evt", (), {"input": search})())
        await pilot.pause()
        assert screen.result == "my-custom-model"


async def test_tab_selects_and_escape_cancels():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen("Choose model", lambda: ["glm-5.2", "kimi-k3"])
        await app.push_screen(screen)
        await pilot.pause()

        search = screen.query_one("#model-search")
        search.value = "glm"
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        assert screen.result == "glm-5.2"

        # reopen and Esc cancels
        screen2 = ModelPickerScreen("Choose model", lambda: ["glm-5.2"])
        await app.push_screen(screen2)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert screen2.result is None
