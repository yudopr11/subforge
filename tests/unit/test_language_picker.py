"""Searchable ISO 639-1 language picker tests (PRD §16)."""

from subforge.tui.app import SubForgeApp
from subforge.tui.screens.language_picker import LanguagePickerScreen
from subforge.tui.screens.languages import ISO_LANGUAGES, resolve_language

# ---- resolution helper ------------------------------------------------------


def test_resolve_language_exact_code():
    assert resolve_language("id") == "id"
    assert resolve_language("en") == "en"
    assert resolve_language(" ES ") == "es"


def test_resolve_language_by_english_name():
    assert resolve_language("indonesian") == "id"
    assert resolve_language("spanish") == "es"


def test_resolve_language_prefix_and_arbitrary_fallback():
    assert resolve_language("ger") == "de"  # German prefix
    assert resolve_language("xx") == "xx"  # unknown -> raw code stays usable
    assert resolve_language("") == ""


def test_catalog_is_iso_and_unique():
    codes = [c for c, _ in ISO_LANGUAGES]
    assert "id" in codes and "en" in codes and "ja" in codes
    assert len(codes) == len(set(codes))  # no duplicate codes


async def _boot():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        yield app, pilot


async def test_typing_filters_and_enter_selects():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        picker = LanguagePickerScreen("Target language")
        await app.push_screen(picker)
        await pilot.pause()

        search = picker.query_one("Input")
        search.value = "id"
        await pilot.pause()

        ol = picker.query_one("#lang-list")
        options = [str(o.prompt) for o in ol.options]
        assert options[0].startswith("id  —  Indonesian")
        assert ol.highlighted == 0

        picker.on_input_submitted(type("Evt", (), {"input": search})())
        await pilot.pause()
        assert picker.result == "id"


async def test_arrows_move_highlight_and_enter_selects():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        picker = LanguagePickerScreen("Target language", current="en")
        await app.push_screen(picker)
        await pilot.pause()

        await pilot.press("down")
        await pilot.pause()
        assert picker.query_one("#lang-list").highlighted == 1
        await pilot.press("enter")
        await pilot.pause()
        # down moved off the exact 'en' match; selection follows the highlighted row
        assert picker.result is not None and len(picker.result) <= 3


async def test_empty_search_enter_returns_none():
    """Enter with an empty search is a deliberate 'no code' (auto-detect)."""
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        picker = LanguagePickerScreen("Source language")
        result: list[str | None] = []

        async def go():
            await app.push_screen(picker, lambda r: result.append(r))
            await pilot.pause()
            search = picker.query_one("Input")
            picker.on_input_submitted(type("Evt", (), {"input": search})())
            await pilot.pause()

        await go()
        assert result == [None]
        assert picker.result is None


async def test_escape_cancels_picker():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        picker = LanguagePickerScreen("Target language")
        await app.push_screen(picker)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert picker.result is None
