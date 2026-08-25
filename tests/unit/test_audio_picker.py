"""Searchable audio file picker tests (PRD §7 /new flow)."""

from pathlib import Path

from subforge.tui.app import SubForgeApp
from subforge.tui.screens.audio_picker import AudioFilePickerScreen


def make_files(tmp_path: Path) -> list[Path]:
    (tmp_path / "media").mkdir()
    a = tmp_path / "take01.wav"
    b = tmp_path / "media" / "take02.flac"
    c = tmp_path / "media" / "final_v2.mp3"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    c.write_bytes(b"x")
    return [a, b, c]


def _options(picker: AudioFilePickerScreen) -> list[str]:
    return [str(o.prompt) for o in picker.query_one("#audio-files").options]


async def test_lists_files_with_pinned_path_row(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = AudioFilePickerScreen(make_files(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        options = _options(picker)
        assert options[0].startswith("⌨")  # pinned "type a path" row
        assert len(options) == 4 and all(("take" in o or "final" in o) for o in options[1:])
        assert picker.query_one("#audio-files").highlighted == 1  # first file match


async def test_typing_filters_by_name_and_folder(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = AudioFilePickerScreen(make_files(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        search = picker.query_one("#audio-search")
        search.value = "final"
        await pilot.pause()
        options = _options(picker)
        assert len(options) == 2 and "final_v2" in options[1]

        search.value = "media"
        await pilot.pause()
        options = _options(picker)
        assert len(options) == 3  # pinned row + the two files under media/
        assert "take02" in options[1] and "final_v2" in options[2]


async def test_enter_picks_highlighted_file(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = AudioFilePickerScreen(make_files(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        await pilot.press("down")  # highlight row 2 (take02)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert picker.result is not None and picker.result.endswith("take02.flac")


async def test_enter_accepts_typed_existing_path(tmp_path):
    app = SubForgeApp()
    audio = tmp_path / "elsewhere" / "song.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"x")
    # file NOT discoverable (outside the scanned root) — but exists on disk
    async with app.run_test() as pilot:
        picker = AudioFilePickerScreen(make_files(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        search = picker.query_one("#audio-search")
        search.value = str(audio)
        await pilot.pause()
        options = _options(picker)
        assert len(options) == 1  # no matches -> only the path row

        picker.on_input_submitted(type("Evt", (), {"input": search})())
        await pilot.pause()
        assert picker.result == str(audio.resolve())


async def test_no_match_enter_hands_off_to_path_typing(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = AudioFilePickerScreen(make_files(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        search = picker.query_one("#audio-search")
        search.value = "no_such_file.wav"  # not on disk either
        await pilot.pause()
        picker.on_input_submitted(type("Evt", (), {"input": search})())
        await pilot.pause()
        assert picker.result == AudioFilePickerScreen.PATH_ENTRY


async def test_path_row_selection_hands_off_to_path_typing(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = AudioFilePickerScreen(make_files(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        await pilot.press("up")  # from row 1 up to the pinned path row
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert picker.result == AudioFilePickerScreen.PATH_ENTRY


async def test_escape_cancels(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        picker = AudioFilePickerScreen(make_files(tmp_path))
        await app.push_screen(picker)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
        assert picker.result is None