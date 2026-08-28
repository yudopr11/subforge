# SubForge — Product Requirements Document

**Version:** 0.2.0 · **Status:** Active · **Last revised:** 2026-08-25

> **Create once. Caption for everyone. Translate for the world.**

Companion document: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). Section numbers in this
document are referenced throughout the codebase and plans (`PRD §N`) — change them
only with a repo-wide search.

---

## 1. Purpose of this document

This is the authoritative statement of what SubForge does for users and why. It defines
the MVP feature set (§23), the behavioral guarantees that make SubForge trustworthy
(§10–§12), and the UX contract the TUI implements (§7–§9). Technical design lives in
ARCHITECTURE.md.

## 2. Vision

SubForge is a **local-first subtitle generation and translation tool** for content
creators. Export the final audio from your video editor, and SubForge turns it into
accurate, timestamped captions — then translates them into other languages while
preserving every timestamp.

Built accessibility-first: captions let Deaf and hard-of-hearing viewers follow content,
and translated subtitles let the rest of the world enjoy it too.

## 3. Problem

Manual subtitling takes 1–3 hours per video. Creators who want to reach beyond their
language face either expensive agencies or machine tools that silently shift timings,
corrupt segment alignment, or ship their audio to unknown servers. Existing ASR tools
stop at transcription; existing translation tools don't understand subtitles.

## 4. Target users

| Persona | Need | Typical setup |
|---|---|---|
| Solo YouTuber (ID-speaking) | ID captions + EN translations on a budget | CPU or mid GPU, whisper.cpp + LM Studio local LLM |
| Accessibility-focused educator | Reliable, reviewable captions | Local whisper.cpp, human review every step |
| Agency / batch producer | Speed across many videos | Cloud providers, headless automation |
| Privacy-sensitive creator | Audio never leaves the machine | Fully local pipeline |

## 5. Goals

1. 10–20 minutes from final-audio export to reviewed, exported subtitles.
2. Zero cloud calls unless the user explicitly configures a remote provider.
3. AI accelerates the work; the creator remains the editor (human review always).
4. Works on modest hardware via selectable model sizes and remote fallbacks.

## 6. Non-goals (v0.2.x)

- Video editing, playback preview, waveform visualization.
- Burning subtitles into video.
- Real-time/live captioning.
- Being an LLM prompt playground — translation is a focused, constrained task.

## 7. Primary UX flow — subtitle REPL

SubForge's home is a **transcript-driven REPL**, modeled on terminal coding tools
(pi, Claude Code, Codex CLI): a scrolling session log, a single `>` prompt, and a thin
footer status line. There is no list menu — commands do the work.

```
 subforge v0.1.0                     episode · transcribe ✓ · translate ● · export ○
 ────────────────────────────────────────────────────────────────────────────
   Local-first subtitles. Type /new to start, ? for help.

   ▸ created project 'episode' from episode.wav
   ✓ transcribed — 24 captions (local/small)
   ▸ translating to 'en'…
   ✓ translated — 24 segments

 > /export
 ────────────────────────────────────────────────────────────────────────────
 /new /open /projects /delete /models /language /transcribe /review /export /wizard /status ? quit
```

### Commands

| Command | Effect |
|---|---|
| `/new <audio>` | create project around an exported audio file; bare `/new` opens a
  **searchable audio picker** of files found under the working directory (newest first)
  — type to filter by name/folder, `↑`/`↓` to move, `Enter` creates; the pinned
  *type a file path* row (or typing a full path directly) switches to manual path entry |
| `/open [name|n]` | bare `/open` opens a **searchable picker** of recent projects — type
  to filter, `↑`/`↓` to move, `Enter` to open (plus a *create new* row); `/open <name|n>`
  still opens directly by name or list number |
| `/projects` | open the interactive project manager |
| `/delete [name]` | delete a project and associated files |
| `/models` | open the **Model Manager** to inspect, download, delete, and select local Whisper GGML models |
| `/language [lang]` | set default audio source language (or auto-detect) via interactive ISO picker |
| `/transcribe [force]` | run or rerun transcription; if already completed, opens a confirmation dialog before overwriting captions (or accepts `force` / `--force` to bypass confirmation) |
| `/review` | open caption review table: edit text, audio playback preview, undo/redo (§9) |
| `/export [formats]` | export SRT/ASS for source captions |
| `/wizard` | re-run the setup wizard, prefilled with current values |
| `/status` | print pipeline stage states |
| `/help`, `?` | command list |
| `/quit`, Ctrl+C | exit |

Setup happens inside the TUI: on **first launch** (no config file yet) the wizard
opens automatically; after that, **Model Manager** (`/models`) and **Language Picker** (`/language`)
provide dedicated configuration screens, or `/wizard` re-runs full wizard-style setup.

- **Model Management (`/models`)**: `[Select / download GGML model with [RECOMMENDED] badge]`
- **Source Language (`/language`)**: `[Select audio source language or auto-detect]`

Languages are chosen from a **searchable ISO 639-1 picker**: type to filter by code or English name,
`↑`/`↓` to move, `Enter` to select (§16). An empty language selection maps to application defaults (auto-detect).

### Interaction model — keyboard only

The TUI is CLI-style: **every action must be reachable from the keyboard, and no flow
may require the mouse.**

- Global: `Ctrl+C` exit · `Esc` back / cancel / dismiss overlays.
- **Transcript copy:** drag the mouse over the transcript to select text; `Ctrl+C`
  or **right-click** copies the selection to the system clipboard (OSC 52), clears it,
  and a second `Ctrl+C` exits as usual. Plain `RichLog` can't extract selections, so
  the transcript uses a selectable variant that attaches the offsets Textual's
  compositor needs and paints the live selection highlight.
- Home prompt accepts slash commands (`/transcribe`) and bare aliases (`transcribe`).
- **Slash autocomplete:** typing `/` in the prompt opens a filtered command picker;
  `↑`/`↓` highlight, `Tab` or `Enter` fills the prompt with the chosen command (then
  `Enter` runs it), `Esc` dismisses. `quit` exits.
- **Command history:** `↑`/`↓` on the prompt recalls previously submitted commands
  (newest first, drafted text preserved and restored when you pass the newest entry;
  consecutive repeats are deduped, max 100 entries). While the slash picker is open,
  arrows steer the picker instead; `Enter` on a recalled command re-submits it.
- Review/edit/model screens are full-keyboard overlays launched by commands;
  each renders its own key legend on-screen (`p` play, `x` stop, `i` install, …).
- `/wizard` is a **modal overlay** over the live REPL — the transcript
  stays visible behind it, and the wizard mirrors its current step into the transcript
  as it runs (Pi-style), so setup reads like a conversation.
- **Searchable choices:** every picker (model, language) is a
  keyboard-driven list — type to filter, `↑`/`↓` move the highlight, `Tab`/`Enter` select.
- Forms: `Tab` / arrows move focus; `Enter` submits the focused field.
- Mouse support is incidental convenience, never a requirement.

Every interactive screen ships its key legend on-screen so the interface stays
discoverable without documentation.


## 8. Hardware profiles & local model management

Whisper GGML models are offered as named profiles with memory guidance and hardware-aware
recommendations. During setup and model selection, SubForge detects available RAM and CPU cores to
dynamically tag the optimal model with a `[RECOMMENDED]` badge. Models download on demand
directly from the official GGML repositories into local app storage:

| Model | Profile | Memory Guidance | Model File Size | Recommended For |
|---|---|---|---|---|
| `large-v3-turbo` *(default)* | Optimal Quality | ~4 GB RAM | ~800 MB | Modern Desktop (16–32 GB RAM, 6+ cores) |
| `large-v3` | Maximum Quality | ~8 GB RAM | ~3.1 GB | Workstation (> 32 GB RAM, 12+ cores) |
| `medium` | High Quality | ~5 GB RAM | ~1.5 GB | Mid-to-High (16 GB RAM) |
| `small` | Balanced | ~2 GB RAM | ~466 MB | Mid-range (10–16 GB RAM, 4–6 cores) |
| `base` | Lightweight | ~1 GB RAM | ~142 MB | Budget (< 10 GB RAM, 4 cores) |
| `tiny` | Ultra-light | ~500 MB RAM | ~75 MB | Low-end (< 6 GB RAM, <= 2 cores) |

Suggested pairings:

| Your hardware | Suggested setup |
|---|---|
| Modern PC / Laptop (16+ GB RAM) | whisper.cpp large-v3-turbo + local/remote LLM |
| Mid-range PC (8–16 GB RAM) | whisper.cpp small + local/remote LLM |
| Budget / Low-end CPU | whisper.cpp base / tiny + remote LLM |

The model manager shows which models are already cached and installs missing ones.
Transcription runs natively via `whisper.cpp` without requiring PyTorch, CUDA, or heavy ML dependencies.

## 9. Caption review

After transcription the user reviews every caption: text is editable per segment,
navigation by row. Editing is **explicit-save**: `Enter` applies an edit to the
review table in memory (with a live `● unsaved changes` status), and `Ctrl+S`
persists it to the project file — `Esc` with unsaved changes warns once before
discarding. `Ctrl+Z`/`Ctrl+Y` undo/redo edits, including across saves. Timing is
displayed but owned by the application (§10). The editing surface is text correction.

## 10. Metadata ownership guarantee

**A core guarantee:** the LLM only ever produces text. Segment IDs and timestamps are
owned by the application and validated on merge — translation can never shift your
timing. Concretely:

- Providers receive `{id, text}` pairs and must return `{id, text}` pairs keyed to the
  same IDs.
- No provider output can create, destroy, renumber, or retime segments.
- Every merge passes validation (ARCH §16); invalid batches fail loudly and leave the
  project untouched.

## 11. Contextual batch translation

Translation runs over small context windows of **five consecutive segments** (default;
configurable). The prompt includes source/target languages and asks for natural,
subtitle-length lines. Each batch's output is strictly validated before merging:
valid JSON, exactly one output per input ID, no unknown IDs, no duplicates, non-empty
text. A failed batch fails alone — completed batches keep their results, and retry
re-runs only the failed stage.

## 12. Audio ingestion

`/new <audio>` imports an exported final-audio file into the project (`<project>/audio/`),
accepting `wav flac mp3 m4a aac ogg opus`. Bare `/new` opens a **searchable picker** of
discoverable audio files under the working directory (newest first): type to filter by
name or folder, `↑`/`↓` to move, `Enter` creates the project immediately. A pinned
*type a file path* row (or typing a full path that exists directly into the search box)
falls back to manual path entry in locate mode, where `@` (or `@query`) re-opens the
picker pre-filtered. Each project owns exactly one audio file; the transcript and
exports live alongside it (§21 guarantees in ARCH).

## 13. Translation review

Side-by-side source/translation table with inline fixes, identical explicit-save
rules as §9 (`Enter` applies in memory, `Ctrl+S` persists, `Ctrl+Z`/`Ctrl+Y` undo/redo)
— reachable via `/review <lang>` for any translated language. Reviewing is part of
the core workflow, not an afterthought.

## 14. Live model discovery

Users never type model IDs. For any configured provider the app fetches
`GET {base_url}/models` live and presents the actual list:

| Stage | Local option | Provider option |
|---|---|---|
| Transcribe | whisper.cpp (`large-v3-turbo`, `small`, `base`, … install on demand) | Always local (cloud transcribe removed for privacy) |
| Translate | any OpenAI-compatible URL (LM Studio `localhost:1234/v1`, Ollama) | OpenAI · OpenCode Zen · OpenCode Go |

Cloud presets (verified live 2026-08-25): `openai` → `https://api.openai.com/v1`,
`opencode-zen` → `https://opencode.ai/zen/v1`,
`opencode-go` → `https://opencode.ai/zen/go/v1`.

## 15. Reasoning controls (provider-driven)

When the selected model supports reasoning effort, SubForge offers **exactly the values
that model accepts** — discovered from model metadata (models.dev catalog), never
hardcoded. Values genuinely vary per model, e.g.:

- `glm-5.2` → `[high, max]`
- `kimi-k3` → `[max]`
- `grok-4.5` → `[low, medium, high]`
- `gpt-5.6-luna` → includes `none`
- some models expose a toggle instead of effort levels; non-reasoning models offer none.

If a model exposes no effort vocabulary the UI hides the control and requests omit the
parameter entirely. Sending an unlisted value fails upstream (OpenCode Zen replies
`expected one of "max"|"xhigh"|"high"|"medium"|"low"|"minimal"|"none"`), so stored
choices are revalidated against the current model after any model change and stale
values reset.

## 16. Languages

Any source language the ASR layer detects or the user selects; a project can carry
**multiple target languages** — the list starts empty and each `/translate <lang>` run
adds its language to the project (`target_languages`), records its own stage
(`translation_<lang>`), and `/export` writes every completed target, skipping
incomplete ones. Language codes are stored in canonical form (e.g. `id`, `en`, `ja`)
and drive output filenames.

Language selection in the TUI uses a **searchable ISO 639-1 picker**: type to filter
the catalog by code or English name, `↑`/`↓` to move the highlight, `Enter`/`Tab` to
select. An empty selection maps to application defaults — source language auto-detect,
target language falls back to the remembered default. Codes never depart the canonical
form; the ISO table is presentation data only.

## 17. Output quality bar

- Timestamps are millisecond-accurate and identical across SRT and ASS renders of the
  same project.
- Translations read like natural subtitles: concise, tone-preserving, terminology-stable.
- Exports open cleanly in players/NLEs (UTF-8, standard SRT; valid ASS header/style).

## 18. Performance expectations

Local transcription speed tracks model size and hardware (§8). Translation throughput ≈
5 segments per request. Remote providers are bound by network latency; all long stages
are individually retryable so a slow/failing provider never costs upstream work.

## 19. Platform & distribution

Python ≥ 3.11, installed via pip/uv. Core install has zero heavy ML or PyTorch dependencies,
keeping package size under 50 MB. Local transcription executes via `whisper.cpp` (`whisper-cli`).
Console command: `subforge [project_dir]` — an optional project directory opens directly;
`subforge --version` prints the version.

## 20. Configuration & privacy defaults (local-first)

Defaults favor fully-local operation: transcription `local` via `whisper.cpp`,
translation via OpenAI-compatible URL pointing at LM Studio
(`http://localhost:1234/v1`). Configuration is **TUI-first**: keys and model choices are
typed into Settings and persisted atomically (mode `0600`) at
`~/.config/subforge/config.json` (override with `SUBFORGE_CONFIG`). `.env` /
environment variables remain an optional fallback for headless automation only — the
TUI never reads secrets from `.env`. Keys are plaintext in the local config file by
design; they are never committed, never logged, and the file is user-readable only.

## 21. Error handling & messaging

User-facing failures are explicit, prefixed messages — e.g. `[ERROR] LM Studio is not
running.` — raised as stage errors so the TUI can display them and offer a retry of
just that stage. Validation boundaries fail loudly; nothing is ever silently swallowed
or auto-"fixed". A failed stage never corrupts completed work.

## 22. Pipeline & resumability

Every expensive stage records explicit state — `PENDING`, `RUNNING`, `COMPLETED`,
`FAILED`, `SKIPPED` — in the project file. Retrying a stage must never rerun completed
upstream stages. Stages recorded: `transcription` (whisper.cpp outputs full segment
timestamps directly) → one `translation_<lang>` per target language →
`caption_review` →
`export`. The project file (`project.json`) is the single source of truth and survives
restarts mid-pipeline. Every completed stage also leaves a durable artifact next to it:
`transcripts/source.json` after transcription and `translations/<lang>.json` (id + text
snapshots, one per completed language) after translation — rendered SRT/ASS then go to
`exports/` (§17).

## 23. MVP scope (v0.2.0) & acceptance criteria

In scope:

1. **Transcription** — always-local whisper.cpp (GGML models installable in-app with
   hardware recommendations); segment timestamps; auto/manual language. Acceptance: a
   scripted-provider project goes audio-in → normalized transcript persisted → segments
   merged, timing untouched.
2. **Caption review** (§9) — view/edit/correct generated captions; edits persist.
3. **Translation** (§10–§11) — contextual batches of five with strict validation;
   LM Studio / Ollama / OpenAI / OpenCode Zen / OpenCode Go.
4. **Export** — SRT (universal) + ASS (styled default), source language plus completed
   translations; incomplete translations are skipped, never half-written.
5. **Resumable pipeline** (§22) — retry just the failed stage; completed stages stay done.
6. **TUI** (§7) — full setup and workflow in-terminal; no `.env` step required.

## 24. Success metrics

- Median time-to-export under 20 minutes for a 15-minute video.
- < 1% of translation batches failing validation against well-behaved models.
- Zero support cases of timing drift after translation (guarantee §10).
- Share of users running fully local pipelines (privacy goal).

## 25. Philosophy

> AI handles the repetitive work. The creator remains the editor.

AI output is never assumed perfect — every caption and translation passes through human
review before export.
