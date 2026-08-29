# SubForge — Technical Architecture

**Version:** 0.3.0 · **Status:** Active · **Last revised:** 2026-08-29

Companion document: [`docs/PRD.md`](PRD.md). Section numbers are referenced throughout
the codebase and plans (`ARCH §N`) — change them only with a repo-wide search.

---

## 1. System Context

SubForge is a pure Go local application with a Bubble Tea TUI that transcribes audio into timestamped captions, provides interactive keyboard-driven review with audio preview, and exports SRT/ASS subtitle files. It operates 100% offline via standalone `whisper-cli` executables and local GGML models.

## 2. Tech Stack

- **Language:** Go ≥ 1.24 (Pure Go, Zero CGO: `CGO_ENABLED=0`)
- **TUI Stack:** Charmbracelet ecosystem:
  - `github.com/charmbracelet/bubbletea` (Elm architecture runtime)
  - `github.com/charmbracelet/lipgloss` (Visual styling & layout)
  - `github.com/charmbracelet/bubbles` (Interactive widgets: list, textinput, table, spinner)
- **Distribution:** Single static binary (~5.5 MB) for Linux (amd64, arm64), macOS (arm64, amd64), and Windows (amd64).

## 3. Repository Layout & Layering

```
subforge/
├── cmd/
│   └── subforge/
│       └── main.go                 # Executable entrypoint & Bubble Tea bootstrapper
├── internal/
│   ├── app/
│   │   ├── binaries/               # whisper-cli & ffmpeg discovery & auto-downloader
│   │   ├── config/                 # AppConfig (~/.config/subforge/config.json) & Hardware Detector
│   │   ├── export/                 # Subtitle generators (SRT, ASS)
│   │   ├── models/                 # Whisper GGML Model Manager (HuggingFace downloader)
│   │   ├── pipeline/               # Audio conversion (16kHz mono) + whisper-cli runner
│   │   ├── player/                 # Segment audio previewer (ffplay, mpv, cvlc, powershell)
│   │   └── project/                # Atomic project storage (project.json in working dir)
│   ├── domain/
│   │   ├── project.go              # Canonical Project, Segment, StageStatus data models
│   │   ├── transcript.go           # Whisper JSON transcript parser
│   │   └── timeutils.go            # Millisecond / centisecond timestamp formatters
│   └── tui/
│       ├── app.go                  # Root Bubble Tea router and screen state machine
│       ├── theme/                  # Lip Gloss color palettes and semantic styles
│       ├── components/             # Reusable UI widgets (Header banner, Footer key legend)
│       └── views/
│           ├── repl/               # Command-driven REPL screen with session log
│           ├── wizard/             # First-run hardware check & setup wizard
│           ├── audiopicker/        # Interactive audio file selector
│           ├── projectpicker/      # Interactive project selector
│           ├── modelmgr/           # Interactive Whisper GGML model manager
│           ├── langpicker/         # ISO language code selector
│           └── review/             # Interactive caption & speaker editor
├── tests/
│   └── integration/                # End-to-end user flow integration tests
├── Makefile                        # Build, test, lint automation
├── go.mod
└── go.sum
```

---

## 4. Unified 3-Tier Screen Layout Architecture

Every interactive screen in SubForge (`REPL`, `Wizard`, `AudioPicker`, `ProjectPicker`, `LanguagePicker`, `ModelManager`, `Review`) strictly conforms to the **3-Tier Screen Architecture**:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  subforge v0.3.0                                            <Screen Title>  │  <-- 1. Top Header Banner
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                            [ Content / Table / List ]                       │  <-- 2. Central Content Area
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Key1] Action1   [Key2] Action2   [/] Filter   [Esc/q] Back to REPL        │  <-- 3. Bottom Key Legend
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **Top Header Banner**: Rendered via `components.RenderHeader("subforge v0.3.0", subtitle, width)`. Left side displays the bold cyan title; right side displays screen-specific status.
2. **Central Content Area**: Column-aligned Lip Gloss tables or Bubbles lists (`l.SetShowTitle(false)`, `l.SetShowHelp(false)`) with cyan cursor (`▸ `).
3. **Bottom Key Legend**: Rendered via `components.RenderFooter(keys, width)` displaying all accessible keybindings for keyboard discoverability.

---

## 5. Non-Negotiable Architectural Rules (ARCH §37)

1. **Pure Go, Zero CGO**: Always build with `CGO_ENABLED=0` to ensure static binaries and instant cross-compilation without C toolchains.
2. **Local First, Zero Bloat**: Transcription executes standalone `whisper-cli` binaries with GGML models. No Python, Torch, or CUDA dependencies.
3. **AI text only, Application owns metadata**: Segment IDs, start/end timestamps, project status, and file paths are application-owned.
4. **Human Review Always**: All AI output is reviewable and editable in `/review` with undo support and audio preview.
5. **Resumable Pipeline**: Stages track explicit state (`pending`, `running`, `completed`, `failed`) in `project.json`. Completed stages are never re-run unnecessarily.
6. **Canonical Representation**: SRT and ASS are output formats only. The canonical data model is `domain.Segment {ID, Start (float64 seconds), End (float64 seconds), Source, Speaker}`.
7. **TUI Contains No Business Logic**: Bubble Tea views render state and forward user intent (`tea.Msg`); pipeline execution, model downloads, and persistence live in `internal/app/`.
8. **Atomic File Persistence**: All `project.json` and `config.json` writes use atomic staging (`.tmp` write followed by `os.Rename`).

---

## 6. Commands & Verification

```bash
make test        # Run all unit and integration tests with race detector (go test -v -race ./...)
make lint        # Run linter (go vet ./...)
make build       # Compile standalone static binary to bin/subforge
make clean       # Clean build artifacts
```
