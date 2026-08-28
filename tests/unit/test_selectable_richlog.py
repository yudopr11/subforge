"""Drag-select + Ctrl+C copy over the transcript (PRD §7 interaction model).

RichLog advertises ALLOW_SELECT but renders no offset style metadata, so the
compositor can't compute content offsets and selection comes back empty. Our
``SelectableRichLog`` attaches the offset meta and extracts from stored lines.
"""

from textual import events
from textual.selection import Offset, Selection

from subforge.config.app_config import AppConfig
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.repl import ReplScreen
from subforge.tui.widgets import SelectableRichLog


async def test_transcript_is_selectable_richlog():
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        log = app.repl.query_one("#transcript")
        assert isinstance(log, SelectableRichLog)
        assert log.ALLOW_SELECT


async def test_render_line_attaches_offset_meta():
    """Rendered lines carry the content ``offset`` meta the compositor needs."""
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        log = app.repl.query_one("#transcript", SelectableRichLog)
        log.scroll_to(y=0, animate=False)
        await pilot.pause()
        strip = log.render_line(1)  # second content line
        metas = [
            seg.style.meta.get("offset")
            for seg in strip
            if seg.style is not None and seg.style.meta
        ]
        assert metas, "expected offset meta on rendered segments"
        assert all(offset[1] == 1 for offset in metas)  # y = content line index


async def test_selection_highlight_is_rendered():
    """The dragged span is painted with the screen--selection style."""
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        log = app.repl.query_one("#transcript", SelectableRichLog)
        log.scroll_to(y=0, animate=False)
        await pilot.pause()
        selection_style = log.screen.get_component_rich_style("screen--selection")
        assert selection_style is not None and selection_style.bgcolor is not None
        sel_bg = selection_style.bgcolor

        def has_highlight(strip) -> bool:
            return any(
                seg.style is not None
                and seg.style.bgcolor is not None
                and seg.style.bgcolor == sel_bg
                for seg in strip
            )

        plain = log.render_line(0)
        assert not has_highlight(plain)  # nothing selected yet

        log.screen.selections = {log: Selection.from_offsets(Offset(2, 0), Offset(10, 0))}
        highlighted = log.render_line(0)
        assert has_highlight(highlighted)


async def test_get_selection_extracts_content():
    app = SubForgeApp(app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        log = app.repl.query_one("#transcript", SelectableRichLog)
        log.scroll_home()
        stripped = "".join(s.text for s in log.lines[0])
        selection = Selection.from_offsets(Offset(0, 0), Offset(6, 0))
        extracted, _ = log.get_selection(selection)
        assert extracted == stripped[:6]


async def test_ctrl_c_copies_selection_without_quitting():
    app = SubForgeApp(app_config=AppConfig())
    copied: list[str] = []
    exited: list[bool] = []
    app.copy_to_clipboard = lambda t: copied.append(t)  # type: ignore[assignment]
    app.exit = lambda *a, **k: exited.append(True)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        log = repl.query_one("#transcript", SelectableRichLog)
        log.scroll_home()
        repl.selections = {log: Selection.from_offsets(Offset(0, 0), Offset(6, 0))}

        await pilot.press("ctrl+c")
        await pilot.pause()

        assert copied and len(copied[0]) == 6
        assert exited == []  # not quit
        assert not repl.selections  # cleared for the next Ctrl+C


async def test_ctrl_c_again_quits_after_copy():
    app = SubForgeApp(app_config=AppConfig())
    copied: list[str] = []
    exited: list[bool] = []
    app.copy_to_clipboard = lambda t: copied.append(t)  # type: ignore[assignment]
    app.exit = lambda *a, **k: exited.append(True)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        log = repl.query_one("#transcript", SelectableRichLog)
        log.scroll_home()
        repl.selections = {log: Selection.from_offsets(Offset(0, 0), Offset(6, 0))}

        await pilot.press("ctrl+c")  # copy
        await pilot.pause()
        await pilot.press("ctrl+c")  # no selection now -> quit
        await pilot.pause()

        assert copied and exited == [True]


async def test_ctrl_c_without_selection_quits():
    app = SubForgeApp(app_config=AppConfig())
    exited: list[bool] = []
    app.exit = lambda *a, **k: exited.append(True)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert exited == [True]


async def test_right_click_copies_selection():
    """Right-click copies the current selection and clears it (terminal UX)."""
    app = SubForgeApp(app_config=AppConfig())
    copied: list[str] = []
    app.copy_to_clipboard = lambda t: copied.append(t)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        log = repl.query_one("#transcript", SelectableRichLog)
        log.scroll_home()
        repl.selections = {log: Selection.from_offsets(Offset(2, 0), Offset(12, 0))}

        await pilot.mouse_down("#transcript", offset=(5, 0), button=3)  # right click
        await pilot.pause()
        await pilot.mouse_up("#transcript", offset=(5, 0))
        await pilot.pause()

        stripped = "".join(s.text for s in log.lines[0])
        assert copied == [stripped[2:12]]
        assert not repl.selections  # cleared after copy


async def test_right_click_without_selection_is_harmless():
    app = SubForgeApp(app_config=AppConfig())
    copied: list[str] = []
    app.copy_to_clipboard = lambda t: copied.append(t)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.mouse_down("#transcript", offset=(5, 0), button=3)
        await pilot.pause()
        await pilot.mouse_up("#transcript", offset=(5, 0))
        await pilot.pause()
        assert copied == []  # nothing selected -> no copy, no crash


async def test_left_drag_still_selects_not_copies():
    """Left-click drag keeps selecting; only right-click copies."""
    app = SubForgeApp(app_config=AppConfig())
    copied: list[str] = []
    app.copy_to_clipboard = lambda t: copied.append(t)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        log = repl.query_one("#transcript", SelectableRichLog)
        log.scroll_home()
        region = repl.screen.find_widget(log).region

        await pilot.mouse_down("#transcript", offset=(0, 0))
        await pilot.pause()
        x1, y1 = region.x + 8, region.y + 0
        repl.screen.post_message(
            events.MouseMove(
                widget=repl.screen,
                x=x1,
                y=y1,
                delta_x=8,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=x1,
                screen_y=y1,
            )
        )
        await pilot.pause()
        await pilot.mouse_up("#transcript", offset=(8, 0))
        await pilot.pause()

        assert copied == []  # left drag never copies
        assert repl.get_selected_text()


async def test_full_mouse_drag_copies_on_ctrl_c():
    app = SubForgeApp(app_config=AppConfig())
    copied: list[str] = []
    exited: list[bool] = []
    app.copy_to_clipboard = lambda t: copied.append(t)  # type: ignore[assignment]
    app.exit = lambda *a, **k: exited.append(True)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        assert isinstance(repl, ReplScreen)
        log = repl.query_one("#transcript", SelectableRichLog)
        log.scroll_home()
        region = repl.screen.find_widget(log).region

        await pilot.mouse_down("#transcript", offset=(0, 0))
        await pilot.pause()
        x1, y1 = region.x + 12, region.y + 0
        repl.screen.post_message(
            events.MouseMove(
                widget=repl.screen,
                x=x1,
                y=y1,
                delta_x=12,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=x1,
                screen_y=y1,
            )
        )
        await pilot.pause()
        await pilot.mouse_up("#transcript", offset=(12, 0))
        await pilot.pause()

        assert repl.get_selected_text(), "drag should select transcript content"
        expected = repl.get_selected_text()
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert copied and copied[0] == expected
        assert exited == []
