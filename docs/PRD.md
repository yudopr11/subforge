# SubForge — Product Requirements Document

**Version:** 0.3.0 · **Status:** Active · **Last revised:** 2026-08-29

> **Create once. Caption for everyone.**

Companion document: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). Section numbers in this
document are referenced throughout the codebase and plans (`PRD §N`) — change them
only with a repo-wide search.

---

## 1. Purpose of this document

This is the authoritative statement of what SubForge does for users and why. It defines
the feature set (§5, §7–§9), behavioral guarantees (§10–§12), and the UX contract the
Bubble Tea TUI implements (§7–§9). Technical design lives in ARCHITECTURE.md.

## 2. Vision

SubForge is a **local-first subtitle generation, review, and export tool** for content
creators. Export the final audio from your video editor, and SubForge turns it into
accurate, timestamped captions via local Whisper models, provides an interactive
keyboard-driven review interface for editing captions and speaker tags with audio
playback preview, and exports clean SRT and ASS subtitle files.

Built accessibility-first: captions let Deaf and hard-of-hearing viewers follow content,
and video creators reach global audiences easily without audio ever leaving the machine.

## 3. Problem

Manual subtitling takes 1–3 hours per video. Creators face either expensive agencies or
cloud machine tools that silently shift timings, corrupt segment alignment, or ship their
audio to unknown servers. Existing ASR tools produce raw unformatted outputs without
integrated review, speaker tagging, or standard subtitle formatting.

## 4. Target users

| Persona | Need | Typical setup |
|---|---|---|
| Solo YouTuber / Creator | Fast local captions on a budget | CPU or GPU, local Whisper GGML models |
| Accessibility-focused educator | Reliable, reviewable captions | Local whisper-cli, human review every step |
| Privacy-sensitive creator | Audio never leaves the machine | Fully local pipeline, zero cloud dependency |

## 5. Goals & Non-goals

### Goals
1. **Instant startup & ultra-lightweight**: Single static binary (~5.5 MB), instant startup (<10ms), zero Python/pip dependencies.
2. **Local first**: 100% offline transcription via standalone `whisper-cli` and GGML models.
3. **Human review first**: Accurate, interactive caption review with inline text editing, speaker tagging, and segment audio playback preview.
4. **Hardware-aware auto-provisioning**: Automatic hardware detection (RAM/CPU) for model recommendations, and automated downloader for helper binaries and HuggingFace GGML models with live progress bars.
5. **Unified, consistent TUI**: Consistent 3-tier screen architecture (Header Banner, Content/Table, Footer Keybindings) across all interactive views.

### Non-goals (v0.3.x)
- LLM translation integration (scrapped in v0.3.0 to keep SubForge lightweight and focused).
- Video editing, playback preview, waveform visualization.
- Burning subtitles into video.
- Real-time/live captioning.

---

## 6. Primary UX Flow — Subtitle REPL

SubForge's home is a **transcript-driven REPL**, modeled on modern terminal tools:
a scrolling session log, a single `>` prompt, and a bottom key legend.

```text
 subforge v0.3.0                          episode · transcribed ✓ (24 captions)
 ────────────────────────────────────────────────────────────────────────────
   Local-first subtitles. Type /new to start, ? for help.

   ▸ created project 'episode' from episode.mp3
   ▸ Converting audio & running Whisper...
   ✓ Transcribed 24 captions successfully

 > /export
 ────────────────────────────────────────────────────────────────────────────
 /new  /open  /projects  /models  /language  /transcribe  /review  /export  /wizard  /status  ?  quit
```

### Commands

| Command | Effect |
|---|---|
| `/new [audio]` | Create a new project; bare `/new` opens the **Audio File Picker** |
| `/open [path]` | Open existing `project.json`; bare `/open` opens the **Project Manager Picker** |
| `/projects` | Open the interactive Project Picker to browse and switch projects |
| `/models` | Open the **Model Manager** to inspect, download, delete, and select GGML models |
| `/language [code]` | Set default audio source language (or auto-detect) via ISO picker |
| `/transcribe` | Run local Whisper transcription pipeline (with live progress streaming) |
| `/review` | Open caption & speaker review table: inline text editing, speaker tagging, audio preview, undo |
| `/export [srt\|ass]` | Export SRT and ASS subtitle files |
| `/wizard` | Re-run the hardware setup wizard |
| `/status` | Print active project metadata and pipeline stage status |
| `?` / `help` | Show command reference |
| `quit` / `exit` | Exit SubForge |

---

## 7. Unified Screen & Modal Layout Contract

Every interactive screen and picker in SubForge strictly follows the **3-tier unified presentation layout**:

1. **Top Header Banner**: Rendered via `components.RenderHeader("subforge v0.3.0", "<Screen Name>", width)`. Left side displays the bold cyan application title; right side displays the contextual screen name / project status, underlined with a clean horizontal divider.
2. **Central Content Area**: Clean, column-aligned table or list with selection cursor (`▸ ` in cyan) and responsive width padding.
3. **Bottom Keybindings Footer**: Rendered via `components.RenderFooter([]string{...}, width)` displaying all valid keyboard shortcuts.

### Screen Gallery & Keybindings

#### Model Manager (`/models`)
```text
 subforge v0.3.0                                                 Model Manager 
 ───────────────────────────────────────────────────────────────────────────────

  Model       Size        Status              Description
  ──────────────────────────────────────────────────────────────────────────────
▸ tiny          75 MB    [Installed ✓]       Fastest, minimal RAM (<1GB)
  small        466 MB    [Not Installed]     Recommended: Best speed & accuracy

 ───────────────────────────────────────────────────────────────────────────────
 [↑/↓] Select  [Enter] Download / Set Active  [d] Delete  [Esc] Back to REPL
```

#### Audio & Project Pickers (`/new`, `/open`)
- **Navigation**: `↑`/`↓`/`j`/`k` to select items.
- **Filter**: Press `/` to search and filter items in real-time.
- **Select**: Press `Enter` to create or open the selected project.
- **Back**: Press `Esc` or `q` (when not filtering) to return to the REPL.

#### Caption & Speaker Reviewer (`/review`)
- **Navigation**: `↑`/`↓`/`j`/`k` to navigate caption rows.
- **Edit Caption**: `Enter` or `e` to edit caption text inline (`Esc` cancels, `Enter` saves).
- **Edit Speaker**: `s` to edit/tag speaker name (default is empty/null).
- **Audio Preview**: `Space` plays audio segment for the selected timestamp `[start → end]`.
- **Undo**: `u` or `Ctrl+Z` to undo text/speaker edits.
- **Back**: `Esc` saves changes and returns to REPL.
