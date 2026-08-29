# SubForge

> **Create once. Caption for everyone.**

SubForge is a fast, ultra-lightweight, local-first subtitle generation and editing tool for content creators built in pure **Go** with **Bubble Tea**. Export the final audio from your video editor, and SubForge turns it into accurate, timestamped captions ready for review and export.

Built accessibility-first: captions that let Deaf and hard-of-hearing viewers follow your content.

![SubForge — subtitle REPL](public/SS.png)

## Quick Install (One-Line Installer)

You can install SubForge with a single terminal command — standalone static binary, zero Python or environment setup required!

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/yudopr11/subforge/master/install.ps1 | iex
```

### Linux & macOS (Terminal)
```bash
curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/install.sh | sh
```

After installation completes, simply open a new terminal window and type:
```bash
subforge
```

### Uninstallation

To uninstall SubForge:

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/yudopr11/subforge/master/uninstall.ps1 | iex
```

**Linux & macOS (Terminal):**
```bash
curl -fsSL https://raw.githubusercontent.com/yudopr11/subforge/master/uninstall.sh | sh
```

---

## How It Works

```
final_audio.wav
      ↓
 Transcribe (local whisper.cpp CLI)
      ↓
 Review Captions (edit text, speaker tag & timing preview)
      ↓
 Export ({project_name}.srt · {project_name}.ass)
```

## Features

- 🎙️ **Local-First Transcription** — standalone whisper.cpp CLI (GGML models `tiny` … `large-v3`, hardware recommendations based on CPU/RAM, automatic on-demand download in-app with progress bars).
- ✍️ **Caption & Speaker Review** — interactive table view, edit caption text (`Enter`), edit speaker tags (`s`), segment audio preview (`Space`), and undo (`u`) in an interactive terminal UI.
- 💾 **Direct Export** — export clean SRT & styled ASS files directly to your current working directory.
- ⚡ **Ultra Lightweight & Fast** — single static binary (~10 MB), instant startup (<20ms), and low memory footprint (~15MB RAM) powered by Go & Bubble Tea.
- 🖥️ **Hardware Aware** — automatic CPU & RAM detection with tailored Whisper model recommendations.

---

## Quick Start (Commands)

Launch SubForge in your terminal:
```bash
subforge
```

Then work with simple slash commands:

- `/new [audio]` — Create project from audio/video file (or open interactive picker).
- `/open [name]` — Open an existing project (or open interactive picker).
- `/transcribe [force]` — Transcribe audio using local whisper.cpp.
- `/review` — Open interactive caption & speaker review table with audio preview.
- `/export [srt|ass|all]` — Export `.srt` and `.ass` to current working directory.
- `/models` — Install, manage, and inspect local Whisper GGML models.
- `/language [code]` — Set default audio source language (or auto-detect).
- `/projects` — List all projects in working directory.
- `/wizard` — Re-run the guided first-run setup wizard.
- `/status` — View pipeline stage states.
- `?` or `/help` — View all commands.
- `quit` or `exit` — Exit application.

---

## Developer Setup

For developers contributing or building from source:

```bash
git clone https://github.com/yudopr11/subforge.git
cd subforge

# Run tests
make test

# Build single static binary
make build

# Run
./bin/subforge
```
