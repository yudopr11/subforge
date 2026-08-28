from pathlib import Path

import pytest

from subforge.app.project_store import save_project
from subforge.models.project import Project, ProjectMeta, StageState
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.repl import ReplScreen


@pytest.mark.asyncio
async def test_dashboard_hotkeys_and_next_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path))
    proj_dir = tmp_path / "Demo"
    proj = Project(
        project=ProjectMeta(name="Demo", source_language="id"),
        segments=[],
    )
    save_project(proj_dir, proj)

    app = SubForgeApp()
    async with app.run_test() as pilot:
        repl = app.screen
        assert isinstance(repl, ReplScreen)
        repl._project_opened(proj_dir)
        await pilot.pause()

        # Suggestion should guide to transcribe
        next_step = repl._render_next_step()
        assert "Transcribe" in next_step or "transcribe" in next_step


@pytest.mark.asyncio
async def test_dashboard_stepper_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path))
    proj_dir = tmp_path / "DemoStepper"
    proj = Project(
        project=ProjectMeta(name="DemoStepper", source_language="id"),
        segments=[],
    )
    proj.set_stage("transcription", StageState.COMPLETED)
    save_project(proj_dir, proj)

    app = SubForgeApp()
    async with app.run_test() as pilot:
        repl = app.screen
        assert isinstance(repl, ReplScreen)
        repl._project_opened(proj_dir)
        await pilot.pause()

        stepper = repl._render_pipeline_stepper()
        assert "Transcribe" in stepper
        assert "Review" in stepper


@pytest.mark.asyncio
async def test_dashboard_hotkey_actions_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path))
    app = SubForgeApp()
    async with app.run_test() as pilot:
        repl = app.screen
        assert isinstance(repl, ReplScreen)

        called: list[str] = []
        repl._cmd_open = lambda arg: called.append("open")
        repl._cmd_models = lambda arg: called.append("models")
        repl._cmd_settings = lambda arg: called.append("settings")
        repl._cmd_new = lambda arg: called.append("new")

        # Test direct action methods
        repl.action_hotkey_projects()
        repl.action_hotkey_models()
        repl.action_hotkey_settings()
        repl.action_hotkey_new()

        assert called == ["open", "models", "settings", "new"]

        # Test keyboard pilot.press triggers for single-key and ctrl-key hotkeys
        called.clear()
        await pilot.press("p")
        await pilot.pause()
        assert "open" in called

        called.clear()
        await pilot.press("m")
        await pilot.pause()
        assert "models" in called

        called.clear()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert "settings" in called


@pytest.mark.asyncio
async def test_dashboard_export_refreshes_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path))
    proj_dir = tmp_path / "DemoExport"
    proj = Project(
        project=ProjectMeta(name="DemoExport", source_language="id"),
        segments=[],
    )
    save_project(proj_dir, proj)

    app = SubForgeApp()
    async with app.run_test() as pilot:
        repl = app.screen
        assert isinstance(repl, ReplScreen)
        repl._project_opened(proj_dir)
        await pilot.pause()

        refreshed: list[bool] = []
        original_refresh = repl.refresh_status

        def wrapped_refresh() -> None:
            refreshed.append(True)
            original_refresh()

        repl.refresh_status = wrapped_refresh  # type: ignore[method-assign]
        repl._cmd_export("")
        assert len(refreshed) >= 1

