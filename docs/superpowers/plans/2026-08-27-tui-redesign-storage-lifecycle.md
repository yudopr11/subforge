# TUI Studio Redesign, Unified OS Storage & Resource Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform SubForge into a visual studio TUI with an Action Center dashboard, unify all storage paths into OS-standard directories with auto-migration, support deletion of local GGML models and projects, and provide automated self-provisioning of `whisper-cli` and `ffmpeg` on Windows and Linux.

**Architecture:** A centralized `storage.py` manages OS-standard paths (`%LOCALAPPDATA%\subforge` on Windows, `~/.config/subforge` & `~/.local/share/subforge` on Linux) with legacy project auto-migration. A dedicated `binaries.py` provisions `ffmpeg` and `whisper-cli` binaries. A reusable `ConfirmDialogScreen` enables keyboard-driven deletion of models and projects. The `ReplScreen` is redesigned as a Studio Dashboard with a project status header, pipeline progress stepper, dynamic next-step suggestions, and one-key hotkey navigation.

**Tech Stack:** Python 3.11+, Textual TUI, Pydantic, HTTPX, GGML Whisper, Pytest, Ruff, Mypy.

**Spec:** `docs/superpowers/specs/2026-08-27-tui-redesign-storage-lifecycle.md`

## Global Constraints
- Strictly zero PyTorch / TorchAudio / CUDA dependencies (<50 MB environment).
- Strict typing (`mypy --strict src`), 100% clean ruff linting.
- Canonical model is `Segment` with float timestamps.
- Zero business logic inside TUI screens (delegate to `app/*`).
- Keyboard-only navigation with visible hotkey legend.

---

### Task 1: Centralized OS Storage Resolver & Legacy Migration

**Files:**
- Create: `src/subforge/app/storage.py`
- Modify: `src/subforge/config/app_config.py`
- Modify: `src/subforge/app/projects.py`
- Modify: `src/subforge/app/model_manager.py`
- Test: `tests/unit/test_storage.py`
- Modify: `tests/unit/test_projects.py`

**Interfaces:**
- Consumes: `os`, `pathlib.Path`, `shutil`
- Produces: `get_subforge_dir()`, `get_config_path()`, `get_bin_dir()`, `get_models_dir()`, `get_projects_dir()`, `migrate_legacy_projects()`

- [x] **Step 1: Write failing tests for storage resolver and legacy migration**

```python
# tests/unit/test_storage.py
import os
import shutil
from pathlib import Path
from unittest.mock import patch

from subforge.app.storage import (
    get_bin_dir,
    get_config_path,
    get_models_dir,
    get_projects_dir,
    get_subforge_dir,
    migrate_legacy_projects,
)


def test_storage_paths_env_override(tmp_path: Path, monkeypatch):
    custom = tmp_path / "custom_subforge"
    monkeypatch.setenv("SUBFORGE_HOME", str(custom))

    assert get_subforge_dir() == custom
    assert get_config_path() == custom / "config.json"
    assert get_bin_dir() == custom / "bin"
    assert get_models_dir() == custom / "models"
    assert get_projects_dir() == custom / "projects"


def test_storage_paths_windows_default(monkeypatch):
    monkeypatch.delenv("SUBFORGE_HOME", raising=False)
    monkeypatch.delenv("SUBFORGE_CONFIG", raising=False)
    monkeypatch.delenv("SUBFORGE_PROJECTS_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\test\\AppData\\Local")

    with patch("os.name", "nt"):
        assert get_subforge_dir() == Path("C:\\Users\\test\\AppData\\Local\\subforge")
        assert get_config_path() == Path("C:\\Users\\test\\AppData\\Local\\subforge\\config.json")
        assert get_projects_dir() == Path("C:\\Users\\test\\AppData\\Local\\subforge\\projects")


def test_migrate_legacy_projects(tmp_path: Path, monkeypatch):
    target_projects = tmp_path / "target_projects"
    legacy_dir = tmp_path / "repo_projects"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "ProjectA").mkdir()
    (legacy_dir / "ProjectA" / "project.json").write_text('{"name": "ProjectA"}')

    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(target_projects))

    migrated = migrate_legacy_projects(source_dir=legacy_dir)
    assert len(migrated) == 1
    assert (target_projects / "ProjectA" / "project.json").exists()
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_storage.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'subforge.app.storage')

- [x] **Step 3: Implement `src/subforge/app/storage.py` and integrate with config & projects**

```python
# src/subforge/app/storage.py
import os
import shutil
from pathlib import Path


def get_subforge_dir() -> Path:
    env = os.environ.get("SUBFORGE_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(app_data) / "subforge"
    return Path.home() / ".local" / "share" / "subforge"


def get_config_path() -> Path:
    env = os.environ.get("SUBFORGE_CONFIG")
    if env:
        return Path(env)
    if os.name == "nt":
        return get_subforge_dir() / "config.json"
    return Path.home() / ".config" / "subforge" / "config.json"


def get_bin_dir() -> Path:
    env = os.environ.get("SUBFORGE_BIN_DIR")
    if env:
        return Path(env)
    return get_subforge_dir() / "bin"


def get_models_dir() -> Path:
    env = os.environ.get("SUBFORGE_MODELS_DIR")
    if env:
        return Path(env)
    return get_subforge_dir() / "models"


def get_projects_dir() -> Path:
    env = os.environ.get("SUBFORGE_PROJECTS_DIR")
    if env:
        return Path(env)
    return get_subforge_dir() / "projects"


def migrate_legacy_projects(source_dir: Path | None = None) -> list[str]:
    legacy = source_dir if source_dir is not None else Path("projects")
    if not legacy.exists() or not legacy.is_dir():
        return []
    target = get_projects_dir()
    target.mkdir(parents=True, exist_ok=True)
    migrated: list[str] = []
    for item in legacy.iterdir():
        if item.is_dir() and (item / "project.json").exists():
            dest = target / item.name
            if not dest.exists():
                shutil.copytree(item, dest)
                migrated.append(item.name)
    return migrated
```

Update `src/subforge/config/app_config.py` to use `get_config_path()`, `src/subforge/app/projects.py` to use `get_projects_dir()`, and `src/subforge/app/model_manager.py` to use `get_models_dir()`.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_storage.py tests/unit/test_projects.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/subforge/app/storage.py src/subforge/config/app_config.py src/subforge/app/projects.py src/subforge/app/model_manager.py tests/unit/test_storage.py
git commit -m "feat(storage): centralize OS-standard storage paths and add legacy project migration"
```

---

### Task 2: Self-Provisioning for `whisper-cli` and `ffmpeg`

**Files:**
- Create: `src/subforge/app/binaries.py`
- Modify: `src/subforge/providers/transcription/whisper_cpp.py`
- Test: `tests/unit/test_binaries.py`

**Interfaces:**
- Consumes: `subforge.app.storage.get_bin_dir()`, `httpx`, `shutil`
- Produces: `ensure_whisper_binary(progress_callback=None) -> Path`, `ensure_ffmpeg_binary(progress_callback=None) -> Path`

- [x] **Step 1: Write failing tests for binary resolver and provisioning**

```python
# tests/unit/test_binaries.py
import sys
from pathlib import Path
from unittest.mock import patch

from subforge.app.binaries import ensure_ffmpeg_binary, ensure_whisper_binary, find_in_path_or_bin


def test_find_in_path_or_bin_existing(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_exe = bin_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    fake_exe.write_text("fake binary")

    monkeypatch.setenv("SUBFORGE_BIN_DIR", str(bin_dir))
    found = find_in_path_or_bin("ffmpeg")
    assert found == fake_exe


def test_ensure_whisper_binary_cached(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target_name = "whisper-cli.exe" if sys.platform == "win32" else "whisper-cli"
    (bin_dir / target_name).write_text("fake whisper binary")

    monkeypatch.setenv("SUBFORGE_BIN_DIR", str(bin_dir))
    path = ensure_whisper_binary()
    assert path == bin_dir / target_name
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_binaries.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'subforge.app.binaries')

- [x] **Step 3: Implement `src/subforge/app/binaries.py`**

Support finding system binaries or auto-downloading official release zip/executables for Windows x64 and Linux x64 into `get_bin_dir()`. Integrate with `whisper_cpp.py`.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_binaries.py tests/unit/test_whisper_cpp_provider.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/subforge/app/binaries.py src/subforge/providers/transcription/whisper_cpp.py tests/unit/test_binaries.py
git commit -m "feat(binaries): add automated self-provisioning for whisper-cli and ffmpeg across platforms"
```

---

### Task 3: Local ASR Model Deletion & Reclaim in Model Manager

**Files:**
- Modify: `src/subforge/app/model_manager.py`
- Create: `src/subforge/tui/screens/confirm_dialog.py`
- Modify: `src/subforge/tui/screens/model_manager.py`
- Test: `tests/unit/test_model_manager.py`
- Modify: `tests/unit/test_model_manager_screen.py`

**Interfaces:**
- Consumes: `LocalModelManager.get_model_path`, `ConfirmDialogScreen`
- Produces: `LocalModelManager.delete_model(model_id: str) -> bool`, `ConfirmDialogScreen(title, message)`

- [x] **Step 1: Write failing test for model deletion and confirmation screen**

```python
# tests/unit/test_model_manager.py (addition)
def test_delete_model_removes_file(tmp_path: Path):
    mgr = LocalModelManager(models_dir=tmp_path)
    model_file = tmp_path / "ggml-small.bin"
    model_file.write_text("dummy model content")
    assert mgr.is_installed("small") is True

    deleted = mgr.delete_model("small")
    assert deleted is True
    assert model_file.exists() is False
    assert mgr.is_installed("small") is False


def test_delete_nonexistent_model_returns_false(tmp_path: Path):
    mgr = LocalModelManager(models_dir=tmp_path)
    assert mgr.delete_model("tiny") is False
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_model_manager.py -k test_delete_model -v`
Expected: FAIL (AttributeError: 'LocalModelManager' object has no attribute 'delete_model')

- [x] **Step 3: Implement `delete_model` and `ConfirmDialogScreen`**

1. Implement `LocalModelManager.delete_model(self, model_id: str) -> bool`.
2. Create `src/subforge/tui/screens/confirm_dialog.py` with `y`/`Enter` to confirm, `n`/`Escape` to cancel.
3. Add `d` and `Delete` keybindings to `ModelManagerScreen` to delete the selected model with confirmation.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_model_manager.py tests/unit/test_model_manager_screen.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/subforge/app/model_manager.py src/subforge/tui/screens/confirm_dialog.py src/subforge/tui/screens/model_manager.py tests/unit/test_model_manager.py tests/unit/test_model_manager_screen.py
git commit -m "feat(models): add local ASR model deletion and confirmation dialog in Model Manager"
```

---

### Task 4: Project Deletion & Active State Handling

**Files:**
- Modify: `src/subforge/app/projects.py`
- Modify: `src/subforge/tui/screens/project_picker.py`
- Modify: `src/subforge/tui/screens/repl.py`
- Test: `tests/unit/test_projects.py`
- Modify: `tests/unit/test_project_picker.py`

**Interfaces:**
- Consumes: `delete_project(project_dir: Path) -> bool`, `ConfirmDialogScreen`
- Produces: Safe project directory deletion, UI list refresh, and active project state reset.

- [x] **Step 1: Write failing test for `delete_project` and project picker deletion**

```python
# tests/unit/test_projects.py (addition)
def test_delete_project_removes_directory(tmp_path: Path):
    proj_dir = tmp_path / "TestProject"
    proj_dir.mkdir()
    (proj_dir / "project.json").write_text("{}")
    (proj_dir / "audio.wav").write_text("wav")

    assert proj_dir.exists() is True
    deleted = delete_project(proj_dir)
    assert deleted is True
    assert proj_dir.exists() is False


def test_delete_invalid_project_returns_false(tmp_path: Path):
    assert delete_project(tmp_path / "Nonexistent") is False
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_projects.py -k test_delete_project -v`
Expected: FAIL (ImportError: cannot import name 'delete_project')

- [x] **Step 3: Implement `delete_project` and project picker deletion keybinding**

1. Implement `delete_project(project_dir: Path) -> bool` in `src/subforge/app/projects.py`.
2. Add `d` and `Delete` keybindings to `ProjectPickerScreen` with `ConfirmDialogScreen`.
3. In `ReplScreen`, if the deleted project was the active project, reset `self.active_project = None` and update banner.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_projects.py tests/unit/test_project_picker.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/subforge/app/projects.py src/subforge/tui/screens/project_picker.py src/subforge/tui/screens/repl.py tests/unit/test_projects.py tests/unit/test_project_picker.py
git commit -m "feat(projects): add project deletion with confirmation and active project state reset"
```

---

### Task 5: Studio Dashboard Redesign & Action Center Workflow

**Files:**
- Modify: `src/subforge/tui/screens/repl.py`
- Modify: `src/subforge/tui/app.py`
- Test: `tests/unit/test_repl.py`
- Create: `tests/integration/test_dashboard_workflow.py`

**Interfaces:**
- Consumes: Project stage states, `Pipeline`, hotkeys (`N`, `T`, `R`, `L`, `V`, `E`, `P`, `M`, `S`, `?`)
- Produces: Studio top header, pipeline progress stepper, dynamic next-step suggestions, action hotkey bar, prompt autocompletion.

- [x] **Step 1: Write integration tests for Studio Dashboard hotkeys & workflow**

```python
# tests/integration/test_dashboard_workflow.py
import pytest
from pathlib import Path
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.repl import ReplScreen
from subforge.models.project import Project, ProjectMeta, StageState
from subforge.app.project_store import save_project


@pytest.mark.asyncio
async def test_dashboard_hotkeys_and_next_action(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path))
    proj_dir = tmp_path / "Demo"
    proj = Project(project=ProjectMeta(name="Demo", source_language="id", target_languages=["en"]))
    save_project(proj_dir, proj)

    app = SubForgeApp()
    async with app.run_test() as pilot:
        repl = app.screen
        assert isinstance(repl, ReplScreen)
        repl._load_project(proj_dir)
        await pilot.pause()

        # Suggestion should guide to transcribe
        assert "Transcribe" in repl._render_next_step()
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_dashboard_workflow.py -v`
Expected: FAIL

- [x] **Step 3: Implement redesigned Studio Dashboard in `repl.py`**

1. Create styled top header widget: Project name, audio duration, source/target languages.
2. Render interactive pipeline stepper pills: `[✓ Transcribe] ──▶ [✓ Review] ──▶ [● Translate] ──▶ [Export]`.
3. Add dynamic next-step helper banner (`▶ Suggested Next Step: ...`).
4. Implement direct keyboard bindings (`N`, `T`, `R`, `L`, `V`, `E`, `P`, `M`, `S`, `?`).
5. Ensure smooth terminal autocompletion and clear typography in `RichLog`.

- [x] **Step 4: Run all unit and integration tests**

Run: `uv run pytest && uv run ruff check src tests && uv run mypy src`
Expected: ALL PASS

- [x] **Step 5: Commit**

```bash
git add src/subforge/tui/screens/repl.py src/subforge/tui/app.py tests/unit/test_repl.py tests/integration/test_dashboard_workflow.py
git commit -m "feat(tui): redesign Studio Dashboard with action center, pipeline stepper, and hotkeys"
```

---

### Task 6: Full Verification & Live Migration Check

**Files:**
- Test: Full test suite (`uv run pytest`)
- Lint & Typecheck: `uv run ruff check src tests && uv run mypy src`

- [x] **Step 1: Run full verification suite**
Run: `uv run pytest && uv run ruff check src tests && uv run mypy src`
Expected: 270+ passing tests, zero lint errors, zero mypy errors.

- [x] **Step 2: Verify live migration of `Timeline 1-enhanced-v2` into `%LOCALAPPDATA%\subforge\projects`**
Run SubForge startup check to verify auto-migration and project loading.

- [x] **Step 3: Commit and update plan status**
```bash
git add docs/superpowers/plans/2026-08-27-tui-redesign-storage-lifecycle.md
git commit -m "docs(plan): complete implementation plan for TUI redesign, storage, and resource lifecycle"
```
