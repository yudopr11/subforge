# AGENTS.md — Guidance for Coding Agents Working on SubForge

Instructions for AI coding agents (and human contributors using agent tooling) working in this repository.

## Project Overview

SubForge is a **local-first subtitle generation, review, and export tool** for content creators. It transcribes audio into timestamped captions using local Whisper models, provides a keyboard-driven Bubble Tea TUI for editing captions and speaker tags with audio playback preview, and exports SRT/ASS subtitle files.

**Read these before doing anything non-trivial:**

- `docs/PRD.md` — product requirements and UX specification (v0.3.0)
- `docs/ARCHITECTURE.md` — technical architecture, package layout, and guarantees (v0.3.0)
- `docs/superpowers/plans/` — implementation plans

---

## Non-Negotiable Architectural Rules

These rules come from `docs/ARCHITECTURE.md §5`. Violating any of them is a bug even if tests pass:

1. **Pure Go, Zero CGO.** Always build with `CGO_ENABLED=0` to ensure static standalone binaries (~5.5 MB) and instant cross-compilation without C toolchains.
2. **Local first, zero-bloat.** Transcription uses standalone `whisper-cli` executables with GGML models. Zero heavy PyTorch, TorchAudio, or CUDA dependencies.
3. **Application owns metadata.** Segment IDs, start/end timestamps, project state, and file paths are application-owned.
4. **Human review.** All transcription output is editable; caption review with speaker tagging and audio preview is a first-class citizen.
5. **Resumable pipeline.** Every expensive stage records explicit state (`pending`, `running`, `completed`, `failed`) in `project.json`.
6. **Canonical internal representation.** SRT and ASS are *output formats only*. The canonical model is `domain.Segment {ID int, Start float64, End float64, Source string, Speaker string}`. Never store formatted timestamp strings in project state.
7. **The TUI contains no business logic.** Bubble Tea views render presentation and dispatch messages (`tea.Msg`); pipeline execution, model management, and file storage live in `internal/app/`.
8. **Unified 3-Tier Screen Layout.** Every interactive screen (`REPL`, `Wizard`, `AudioPicker`, `ProjectPicker`, `LanguagePicker`, `ModelManager`, `Review`) must use the standard 3-tier structure:
   - **Top Header Banner**: `components.RenderHeader("subforge v0.3.0", subtitle, width)`
   - **Central Content Area**: Clean, column-aligned table or list with `▸ ` selection cursor
   - **Bottom Key Legend**: `components.RenderFooter(keys, width)`
9. **Atomic file writes.** All `project.json` and `config.json` writes must write to a temporary file (`.tmp`) first before atomic `os.Rename`.

---

## Commands & Quality Gates

```bash
make test        # Run all unit and integration tests with race detector (go test -v -race ./...)
make lint        # Run linter (go vet ./...)
make build       # Compile standalone static binary to bin/subforge
```

All tests must pass without network access, GPU, downloaded models, or running servers. Use in-memory mocks, temporary directories (`t.TempDir()`), and mock binaries.

---

## Testing Requirements (every feature)

A feature is complete only when all three gates pass:

1. **Unit tests** (`*_test.go`) cover logic and edge cases in the respective package.
2. **Integration / UI tests** exercise full flows (e.g. `tests/integration/full_flow_test.go`, `internal/tui/app_test.go`).
3. **Quality gates**: `make test && make lint && make build`.

---

## Keybindings & Navigation Standards

- Every sub-screen (`AudioPicker`, `ProjectPicker`, `LanguagePicker`, `ModelManager`, `Review`, `Wizard`) must allow returning to the REPL via `Esc` or `q` (when not actively filtering).
- In the REPL, commands are entered at the `> ` prompt (`/new`, `/open`, `/transcribe`, `/review`, `/export`, `/models`, `/language`, `/wizard`, `/status`, `quit`, `exit`, `?`).

---

## Documentation Sync

`docs/PRD.md` and `docs/ARCHITECTURE.md` are load-bearing:
- Any new behavior, UX flow, or design decision must update `docs/PRD.md` and `docs/ARCHITECTURE.md` in the same change set.
- Plans in `docs/superpowers/plans/` use checkbox tracking (`- [ ]` / `- [x]`) and must stay current.
