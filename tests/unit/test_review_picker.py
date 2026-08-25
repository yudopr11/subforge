"""Searchable review picker tests (PRD §7 /review flow)."""

from pathlib import Path

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.review_picker import ReviewPickerScreen


def seed(tmp_path: Path, translations: dict[str, str] | None = None) -> Path:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id", target_languages=["en", "jv"]))
    project = load_project(d)
    project.segments = [
        Segment(id=1, start=1.0, end=2.0, source="halo", translations=translations or {}),
        Segment(id=2, start=2.0, end=3.0, source="dunia", translations=translations or {}),
    ]
    save_project(d, project)
    return d


def _options(picker: ReviewPickerScreen) -> list[str]:
    return [str(o.prompt) for o in picker.query_one("#review-options").options]


async def test_lists_captions_and_only_translated_languages(tmp_path):
    # "jv" has translations; "en" is a target but nothing translated yet
    d = seed(tmp_path, {"jv": "halo dunya"})
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ReviewPickerScreen(d)
        await app.push_screen(picker)
        await pilot.pause()

        options = _options(picker)
        assert any("Captions" in o for o in options)
        assert any("jv" in o and "2 segments" in o for o in options)
        assert not any("Translation \u00b7 en" in o for o in options)  # untranslated hidden


async def test_typing_filters_and_enter_selects(tmp_path):
    d = seed(tmp_path, {"jv": "halo dunya"})
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ReviewPickerScreen(d)
        await app.push_screen(picker)
        await pilot.pause()

        search = picker.query_one("#review-search")
        search.value = "jv"
        await pilot.pause()
        options = _options(picker)
        assert len(options) == 1 and "jv" in options[0]

        picker.on_input_submitted(type("Evt", (), {"input": search})())
        await pilot.pause()
        assert picker.result == "jv"


async def test_captions_row_dismisses_with_captions(tmp_path):
    d = seed(tmp_path)
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ReviewPickerScreen(d)
        await app.push_screen(picker)
        await pilot.pause()

        options = _options(picker)
        picker.on_option_list_option_selected(
            type("Evt", (), {"option": type("O", (), {"prompt": options[0]})()})()
        )
        await pilot.pause()
        assert picker.result == ReviewPickerScreen.CAPTIONS


async def test_escape_cancels(tmp_path):
    d = seed(tmp_path)
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = ReviewPickerScreen(d)
        await app.push_screen(picker)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
        assert picker.result is None