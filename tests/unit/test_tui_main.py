from subforge.tui.app import SubForgeApp


async def test_app_boots_and_shows_actions():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        labels = [
            str(item.children[0].render())
            for item in app.screen.query_one(".action-list").children
        ]
        assert "Transcribe" in labels
        assert "Export SRT / ASS" in labels
