# SubForge — Go & Bubble Tea Rewrite Design Specification

**Date:** 2026-08-29  
**Status:** Approved for Implementation Planning  
**Target:** Pure Go implementation with Bubble Tea TUI  

---

## 1. Context & Motivation

SubForge is a local-first subtitle generation and editing tool for content creators. The initial Python implementation (~140MB dev environment, ~50MB standalone PyInstaller binary, ~60MB RAM footprint) proved the core workflows and UX.

Rewriting SubForge in Go achieves:
1. **Ultra-lightweight distribution:** Standalone static binary (~10–15 MB), zero Python/pip/venv requirements for end-users.
2. **Instant startup & low memory:** <20ms startup time, 10–20MB idle memory.
3. **Rock-solid cross-compilation:** Easy static builds for Linux, macOS (Apple Silicon & Intel), and Windows from any platform (`CGO_ENABLED=0`).
4. **Delightful TUI:** Powered by the Charmbracelet ecosystem (`bubbletea`, `lipgloss`, `bubbles`).

### Scope Simplification
Per agreement, **LLM translation has been dropped / scrapped**. SubForge in Go focuses 100% on being the fastest and cleanest **Local ASR Transcribe $\rightarrow$ Review & Speaker Tagging $\rightarrow$ Export (SRT/ASS)** tool.

---

## 2. Goals & Non-Goals

### Goals
- **1:1 Feature Parity** with core transcription, review, and export workflows.
- **Pure Go (Zero CGO)**: Clean compilation without requiring native C toolchains.
- **Hardware-Aware Model Management**: Automatically detect RAM and CPU cores to recommend Whisper GGML models (`tiny`, `base`, `small`, `medium`, `large-v3`), and download models directly from HuggingFace with live progress.
- **Automatic Helper Binaries**: Download official precompiled `whisper-cli` executable if not found on the system.
- **Terminal REPL UX**: Command-driven interface (`/new`, `/open`, `/transcribe`, `/review`, `/export`, `/models`, `/language`, `/wizard`, `/status`, `/projects`).
- **Interactive Caption Reviewer**: Interactive table with inline text editing, manual speaker tagging, undo support, and segment audio playback preview via CLI players (`ffplay`, `mpv`, `cvlc`, `powershell`).
- **Standard Exports**: Clean `.srt` and styled `.ass` file generation.
- **Robust Storage**: Atomic JSON persistence for `project.json` and user config `config.json`.

### Non-Goals
- LLM translation integration (scrapped).
- In-process CGO whisper bindings (external CLI process execution is preferred for memory safety and zero-CGO builds).
- Real-time live audio capture.
- Video playback or rendering burn-in.

---

## 3. Project & Package Layout

```
subforge/
├── cmd/
│   └── subforge/
│       └── main.go                 # Application entrypoint & CLI dispatcher
├── internal/
│   ├── app/
│   │   ├── binaries/               # whisper-cli & ffmpeg detection / auto-download
│   │   ├── config/                 # AppConfig (~/.config/subforge/config.json) & DeviceDetector
│   │   ├── export/                 # Subtitle generators (SRT, ASS)
│   │   ├── models/                 # GGML ModelManager (HuggingFace downloader, validator)
│   │   ├── pipeline/               # 16kHz audio conversion + whisper-cli runner + progress parsing
│   │   ├── player/                 # Segment audio preview (ffplay, mpv, cvlc, powershell)
│   │   └── project/                # Project store & atomic lifecycle (project.json in working dir)
│   ├── domain/
│   │   ├── project.go              # Canonical Project, Segment, StageStatus data models
│   │   ├── transcript.go           # Raw Whisper JSON transcript data parser
│   │   └── timeutils.go            # Millisecond / centisecond formatting & parsing
│   └── tui/
│       ├── app.go                  # Root Bubble Tea model & screen routing state
│       ├── theme/                  # Lip Gloss palettes, borders, banner styles
│       ├── views/
│       │   ├── repl/               # Command-driven REPL screen with scrolling session log
│       │   ├── wizard/             # First-run setup & hardware check wizard
│       │   ├── audiopicker/        # Interactive fuzzy audio/video file selector
│       │   ├── projectpicker/      # Interactive project selector
│       │   ├── modelmgr/           # Interactive Whisper GGML model manager
│       │   ├── langpicker/         # ISO language code selector
│       │   ├── review/             # Interactive caption & speaker review table
│       │   └── confirm/            # Reusable confirmation modal
│       └── components/             # Reusable widgets (status footer, table, spinner)
├── go.mod
├── go.sum
└── Makefile
```

---

## 4. Domain & Data Models

### Canonical Models (`internal/domain/project.go`)

```go
package domain

import "time"

type StageStatus string

const (
    StatusPending   StageStatus = "pending"
    StatusRunning   StageStatus = "running"
    StatusCompleted StageStatus = "completed"
    StatusFailed    StageStatus = "failed"
    StatusSkipped   StageStatus = "skipped"
)

type Segment struct {
    ID      int     `json:"id"`                // 1-based index
    Start   float64 `json:"start"`             // Timestamp in seconds (e.g. 1.450)
    End     float64 `json:"end"`               // Timestamp in seconds (e.g. 4.200)
    Source  string  `json:"source"`            // Transcribed text / edited text
    Speaker string  `json:"speaker,omitempty"` // Optional manual speaker name/tag (default empty)
}

type Project struct {
    Name          string                 `json:"name"`
    AudioPath     string                 `json:"audio_path"`
    AudioDuration float64                `json:"audio_duration,omitempty"`
    Language      string                 `json:"language"` // "auto" or ISO-639-1 code
    Model         string                 `json:"model"`    // e.g. "small", "base", "medium"
    Stages        map[string]StageStatus `json:"stages"`   // "transcribe", "export"
    Error         string                 `json:"error,omitempty"`
    Segments      []Segment              `json:"segments"`
    CreatedAt     time.Time              `json:"created_at"`
    UpdatedAt     time.Time              `json:"updated_at"`
}
```

### Time Formatting Utilities (`internal/domain/timeutils.go`)
- **SRT Format:** `HH:MM:SS,mmm` (e.g., `00:01:23,450`).
- **ASS Format:** `H:MM:SS.cc` (e.g., `0:01:23.45` with 2 decimal places for centiseconds).
- Robust conversion functions: `FormatSRTTime(seconds float64) string`, `FormatASSTime(seconds float64) string`, `ParseTime(formatted string) (float64, error)`.

---

## 5. Core Subsystems

### 5.1 Storage & Configuration (`internal/app/config/` & `internal/app/project/`)
- User configuration is stored in `~/.config/subforge/config.json` (`chmod 0600` on Unix).
- Hardware detector inspects total system RAM and CPU threads to provide default model recommendations:
  - `< 4 GB` RAM: `tiny` or `base`
  - `4 – 8 GB` RAM: `small` (standard recommended)
  - `> 8 GB` RAM: `medium` or `large-v3`
- All JSON writes use atomic replacement: write to `*.tmp` $\rightarrow$ flush & sync $\rightarrow$ `os.Rename`.

### 5.2 Helper Binary & Model Manager (`internal/app/binaries/` & `internal/app/models/`)
- Paths: `~/.local/share/subforge/bin/` (executables) and `~/.local/share/subforge/models/` (GGML weights).
- Automatic HuggingFace downloads for GGML models with sha256 / size verification and streaming progress reporting via channels.
- Binary locator checks both local app bin directory and system `$PATH` for `whisper-cli` and `ffmpeg`.

### 5.3 Pipeline Execution (`internal/app/pipeline/`)
1. **Audio Prep**: Uses `ffmpeg` to extract and downmix input audio to 16kHz 16-bit mono WAV (`audio.wav` cached in project folder).
2. **Transcription**: Executes `whisper-cli -m <model_path> -f audio.wav --output-json -l <lang>`. Streams stdout/stderr percentage progress lines to the TUI.
3. **Parse & Store**: Parses Whisper JSON output into canonical `[]domain.Segment`, updates stage status to `completed`, and saves `project.json`.

### 5.4 Subtitle Exporters (`internal/app/export/`)
- **SRT Exporter**: Sequential index, SRT timestamps `00:00:00,000 --> 00:00:00,000`, speaker prefix if present (e.g. `[Speaker]: Text`), and caption body.
- **ASS Exporter**: Full Advanced SubStation Alpha header with SubForge styling parameters (Font, Size, PrimaryColour, Outline, Shadow, Alignment) and Dialogue events.

### 5.5 Segment Audio Player (`internal/app/player/`)
- Launches non-blocking playback for specific segment time ranges `[start, end]` using system audio players (`ffplay`, `mpv`, `cvlc`, or Windows PowerShell audio player fallback).
- Starting a new segment automatically stops any currently playing audio process.

---

## 6. Bubble Tea TUI Architecture

### Elm Architecture Flow
1. **Model**: Root state struct holding current `Screen`, active `Project`, `AppConfig`, window dimensions (`width`, `height`), and sub-models.
2. **Messages (`tea.Msg`)**:
   - `SwitchScreenMsg(screen Screen)`
   - `ProjectLoadedMsg(*domain.Project)`
   - `TranscribeProgressMsg{Percent float64, Message string}`
   - `TranscribeFinishedMsg{Err error}`
   - `DownloadProgressMsg{Model string, Current int64, Total int64}`
   - `AudioPlayMsg{Start float64, End float64}`
3. **Commands (`tea.Cmd`)**:
   - Background downloads and pipeline executions return channels converted to Bubble Tea messages.
4. **Views**:
   - **REPL View**: Scrolling session history + autocomplete command input prompt.
   - **Caption Review View**: Interactive segment table with hotkeys (`Enter` to edit caption, `s` to edit speaker, `Space` to play audio segment, `u` for undo, `Esc` to save and exit).
   - **Model Manager View**: Download/delete Whisper GGML models with progress bars.
   - **Pickers**: Fuzzy searchable lists for audio files, existing projects, and ISO languages.

---

## 7. Testing & Verification Plan

### Test Layers
1. **Unit Tests**:
   - Timestamp conversions (edge cases: zero, sub-second centiseconds, hours overflow).
   - Exporters: Validated output strings for SRT and ASS.
   - Domain logic & Atomic store tests.
   - Hardware detection logic on varied simulated RAM values.
2. **Integration / Fake Executable Tests**:
   - Pipeline runner tested with a mock/scripted `whisper-cli` and `ffmpeg` to verify stdout parsing, error propagation, and state file persistence.
3. **TUI View Tests**:
   - Bubble Tea test harness verifying screen transitions, keybindings, and command executions.

### Quality Gates
- `go test -v -race ./...` (All tests passing with zero race conditions).
- `go vet ./...` (Zero issues).
- `CGO_ENABLED=0 go build -ldflags="-s -w" -o subforge ./cmd/subforge` (Builds clean single static binary).
