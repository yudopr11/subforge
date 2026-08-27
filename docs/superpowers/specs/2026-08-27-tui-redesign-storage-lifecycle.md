# Technical Design Spec: SubForge TUI Studio Redesign, Unified Storage & Resource Lifecycle

**Date:** 2026-08-27  
**Status:** Approved  
**Scope:** TUI Action Center & Visual Polish, Cross-Platform OS Storage (`%LOCALAPPDATA%` / `~/.local/share`), Local Resource Lifecycle (ASR Model & Project Deletion), Automated Binary Tool Provisioning (whisper-cli & ffmpeg on Windows and Linux).

---

## 1. Executive Summary & Goals

This specification defines the architectural and visual overhaul of SubForge into a modern, studio-grade subtitle engineering suite:
1. **Studio Dashboard & Action Center**: Transform the single-pane REPL into an interactive visual dashboard with a persistent project status card, pipeline stepper, dynamic next-action suggestions, and one-key hotkey workflow (`[T] Transcribe`, `[R] Review`, `[L] Translate`, `[E] Export`, etc.).
2. **Unified OS-Level Storage (`subforge.app.storage`)**: Strict separation of repository code from user data. All projects, GGML models, binaries, and configurations are stored in standard OS directories on Windows (`%LOCALAPPDATA%\subforge\`) and Linux (`~/.config/subforge/` & `~/.local/share/subforge/`), with automatic legacy repo migration.
3. **Local ASR Model Deletion**: Ability to safely delete installed GGML Whisper models from disk via `[d]` / `[Delete]` in the Model Manager with immediate disk space reclamation.
4. **Project Deletion & Management**: Ability to safely delete existing projects from disk via `[d]` / `[Delete]` in the Project Picker with modal confirmation and active project state handling.
5. **Zero-Dependency Tool Provisioning (`whisper-cli` & `ffmpeg`)**: Automatic discovery and self-provisioning of `whisper-cli` and `ffmpeg` binaries on both Windows and Linux into the app's `bin/` directory if not present on the host system.

---

## 2. Directory & Storage Architecture

All SubForge user artifacts, binary dependencies, models, and configurations are governed by `subforge.app.storage`:

```text
Windows:
%LOCALAPPDATA%\subforge\
├── config.json               # Application settings & secrets
├── bin\                      # Managed standalone binaries
│   ├── whisper-cli.exe
│   └── ffmpeg.exe
├── models\                   # Downloaded GGML Whisper models
│   ├── ggml-tiny.bin
│   └── ggml-small.bin
└── projects\                 # User subtitle projects
    ├── Timeline 1-enhanced-v2\
    │   ├── project.json
    │   ├── audio.mp3
    │   └── exports\

Linux / POSIX:
~/.config/subforge/
└── config.json               # Application settings (0600 permissions)
~/.local/share/subforge/
├── bin/                      # Managed standalone binaries
│   ├── whisper-cli
│   └── ffmpeg
├── models/                   # Downloaded GGML Whisper models
│   └── ggml-small.bin
└── projects/                 # User subtitle projects
    └── Timeline 1-enhanced-v2/
```

### Environment Variable Overrides (for testing and portability)
- `SUBFORGE_HOME`: Overrides the base root directory.
- `SUBFORGE_CONFIG`: Path to `config.json`.
- `SUBFORGE_BIN_DIR`: Path to binary dependencies.
- `SUBFORGE_MODELS_DIR`: Path to GGML models directory.
- `SUBFORGE_PROJECTS_DIR`: Path to projects directory.

### Legacy Project Migration
On startup, `subforge.app.storage.migrate_legacy_projects()` scans `./projects/` relative to the current working directory. Any found projects are copied into the OS projects directory and recorded, ensuring no user data is lost.

---

## 3. Tool Self-Provisioning: `whisper-cli` & `ffmpeg`

SubForge guarantees a zero-bloat, self-contained runtime:

1. **`whisper-cli` Provisioning**:
   - Checks system `PATH`.
   - Checks `storage.get_bin_dir() / "whisper-cli"(.exe)`.
   - If missing, downloads official prebuilt release binary:
     - Windows x64: `whisper.cpp` release zip (`whisper-cli.exe` + DLLs).
     - Linux x64: `whisper.cpp` prebuilt binary for Linux.

2. **`ffmpeg` Provisioning**:
   - Checks system `PATH` for `ffmpeg`.
   - Checks `storage.get_bin_dir() / "ffmpeg"(.exe)`.
   - If missing on Windows: downloads standalone static `ffmpeg.exe` into `%LOCALAPPDATA%\subforge\bin\`.
   - If missing on Linux: downloads standalone static `ffmpeg` Linux x64 binary into `~/.local/share/subforge/bin/` and sets `chmod +x`.

---

## 4. TUI Studio Visual Redesign & Workflow

### 4.1 Dashboard Layout (`ReplScreen`)
The main interface provides immediate visual feedback and actionable next steps:

```text
┌─ SUBFORGE STUDIO ────────────────────────────────────────────────────────┐
│ Project: Timeline 1-enhanced-v2  │  Lang: id → en  │  Audio: 02:45 (WAV) │
│ Pipeline: [✓ Transcribe] ──▶ [✓ Review] ──▶ [✓ Translate] ──▶ [● Export]  │
├──────────────────────────────────────────────────────────────────────────┤
│ ▶ Next Action: Press [E] to Export Subtitles (SRT / ASS)                 │
└──────────────────────────────────────────────────────────────────────────┘
 [N] New  [T] Transcribe  [R] Review  [L] Translate  [V] View TL  [E] Export  [P] Projects  [M] Models  [S] Settings

 [20:45:12] SubForge Studio ready. Loaded project 'Timeline 1-enhanced-v2' (57 segments)
 [20:45:15] ✓ Transcription completed via whisper.cpp (small)
 [20:45:30] ✓ Translation to 'en' completed (57/57 segments)
 ───────────────────────────────────────────────────────────────────────────
 subforge ❯ /
```

### 4.2 Global Action Hotkeys (Available anywhere on the dashboard)
- `N`: New project from audio file (opens file picker modal).
- `T`: Transcribe active project (runs whisper.cpp background task).
- `R`: Review/Edit original transcribed captions.
- `L`: Translate active project to target language.
- `V`: Review/Edit translated captions.
- `E`: Export subtitles (`.srt` and `.ass`).
- `P`: Project Manager (`/projects`) — load, inspect, or delete projects.
- `M`: Model Manager (`/models`) — download, inspect, or delete GGML models.
- `S`: Settings (`/settings`) — manage models, API keys, and endpoints.
- `?`: Show keyboard shortcuts and workflow guide.

---

## 5. Resource Deletion & Lifecycle Safeguards

### 5.1 Local ASR Model Deletion
- **Location**: `ModelManagerScreen`.
- **Trigger**: Highlighting an *Installed* model in the table and pressing `[d]` or `[Delete]`.
- **Confirmation Modal**: `ConfirmDialogScreen(title="Delete Model", message="Permanently delete GGML model '{model_id}' ({size}) from disk?")`.
- **Execution**: `LocalModelManager.delete_model(model_id)` safely removes `ggml-{model_id}.bin`.
- **Visual Feedback**: Table refreshes immediately, badge turns to `Available`, and memory/disk space is updated.

### 5.2 Project Deletion
- **Location**: `ProjectPickerScreen`.
- **Trigger**: Highlighting any project in the list and pressing `[d]` or `[Delete]`.
- **Confirmation Modal**: `ConfirmDialogScreen(title="Delete Project", message="Permanently delete project '{name}' and all associated transcripts/exports?")`.
- **Execution**: `subforge.app.projects.delete_project(project_dir)` removes the folder and contents.
- **Active Project Handling**: If the deleted project was the currently active project in the REPL, the REPL resets its active project state to `None` and displays `(no project loaded)`.

---

## 6. Implementation Plan & Testing Strategy

### Unit Tests
- `tests/unit/test_storage.py`: Validate default paths across Windows (`nt`) and Linux (`posix`), environment overrides, and directory creation.
- `tests/unit/test_model_manager_delete.py`: Test `delete_model` success, missing file handling, and status reflection.
- `tests/unit/test_project_delete.py`: Test `delete_project` recursive directory deletion and active project reset.
- `tests/unit/test_ffmpeg_provision.py`: Test `ensure_ffmpeg` resolution and mock download across platforms.

### Integration / E2E Tests
- `tests/integration/test_dashboard_workflow.py`: Test the full hotkey-driven workflow from new project creation, transcription, review, translation, to export.
- `tests/unit/test_model_manager_screen.py`: Test deletion keybinding and modal confirmation flow.
- `tests/unit/test_project_picker.py`: Test project deletion keybinding and modal confirmation flow.

---

## 7. Verification & Success Criteria

1. All 260+ existing tests pass, plus new storage, deletion, and dashboard tests.
2. `ruff check src tests` and `mypy --strict src` pass with zero errors.
3. SubForge launches and stores projects in `%LOCALAPPDATA%\subforge\projects` on Windows and `~/.local/share/subforge/projects` on Linux.
4. Users can delete downloaded models and existing projects safely via keyboard.
5. Missing `whisper-cli` or `ffmpeg` binaries are automatically resolved without user intervention.
