import pytest

from subforge.tui.app import SubForgeApp
from subforge.tui.screens.confirm_dialog import ConfirmDialogScreen


@pytest.mark.asyncio
async def test_confirm_dialog_arrow_navigation_and_enter():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        results: list[bool] = []
        screen = ConfirmDialogScreen("Delete", "Are you sure?")
        await app.push_screen(screen, callback=lambda r: results.append(r) if r is not None else None)
        await pilot.pause()

        # By default, confirm button is focused
        assert app.focused and app.focused.id == "btn-confirm"

        # Press Right arrow -> moves focus to Cancel button
        await pilot.press("right")
        await pilot.pause()
        assert app.focused and app.focused.id == "btn-cancel"

        # Press Enter while Cancel is focused -> dismisses with False
        await pilot.press("enter")
        await pilot.pause()
        assert results == [False]


@pytest.mark.asyncio
async def test_confirm_dialog_left_arrow_then_enter():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        results: list[bool] = []
        screen = ConfirmDialogScreen("Delete", "Are you sure?")
        await app.push_screen(screen, callback=lambda r: results.append(r) if r is not None else None)
        await pilot.pause()

        # Move to cancel, then back to confirm with left arrow
        await pilot.press("right")
        await pilot.pause()
        assert app.focused and app.focused.id == "btn-cancel"

        await pilot.press("left")
        await pilot.pause()
        assert app.focused and app.focused.id == "btn-confirm"

        # Press Enter while Confirm is focused -> dismisses with True
        await pilot.press("enter")
        await pilot.pause()
        assert results == [True]


@pytest.mark.asyncio
async def test_confirm_dialog_direct_hotkeys():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        # Test 'y' key
        res_y: list[bool] = []
        await app.push_screen(ConfirmDialogScreen(), callback=lambda r: res_y.append(r) if r is not None else None)
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert res_y == [True]

        # Test 'n' key
        res_n: list[bool] = []
        await app.push_screen(ConfirmDialogScreen(), callback=lambda r: res_n.append(r) if r is not None else None)
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert res_n == [False]
