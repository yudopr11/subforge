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
| Solo YouTuber (ID-speaking) | ID captions + EN translations on a budget | CPU or mid GPU, LM Studio local LLM |
| Accessibility-focused educator | Reliable, reviewable captions | Local WhisperX, human review every step |
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

 > /translate ja
 ────────────────────────────────────────────────────────────────────────────
 /new /open /transcribe /review /translate /export /settings ?  q quit
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
| `/transcribe` | run the transcription stage (busy-guarded, retryable) |
| `/review [lang]` | caption review (edit text, play segment audio); with a `<lang>`
  argument: translation review for that language — both explicit-save with undo/redo |
| `/translate [lang]` | translate into a language code; defaults to remembered target |
| `/export [formats]` | export SRT/ASS for source + completed translations |
| `/settings` | two-stage menu — **Transcribe** or **Translation**; after picking
  local or cloud, a **step menu** lists the remaining steps (see below); each step
  saves on completion and returns to the step menu |
| `/wizard` | re-run the setup wizard, prefilled with current values |
| `/status` | print pipeline stage states |
| `/help`, `?` | command list |
| `/quit`, Ctrl+C | exit |

Setup happens inside the TUI: on **first launch** (no config file yet) the wizard
opens automatically; after that, **Settings** (`/settings`) opens a two-choice menu — pick
**Transcribe** or **Translation**, then **Local or Cloud**, then a **step menu** of
what's left to configure; or `/wizard` re-runs full wizard-style setup. Providers
rebuild without restarting the project:

- **Transcribe — Local**: `[Select model, Source language]`
- **Transcribe — Cloud (OpenAI)**: `[Connect (API key), Select model, Source language]`
- **Translate — Local**: `[Select model (server URL + model), Default target language]`
- **Translate — Cloud**: `[Connect (provider + API key), Select model + reasoning,
  Default target language]`

Steps are jumped to directly from the step menu; each completed step **persists
immediately** and returns to the step menu, so Esc at any depth never loses finished
work. The **Connect** step always asks for the API key — prefilled and preselected
with the stored key — so reconnecting replaces it instead of skipping it. `/settings`
reads `config.json` fresh from disk, so manual edits to the file are honored, never
overwritten by stale in-memory values. Languages are chosen from a **searchable ISO
639-1 picker**: type to filter by code or English name, `↑`/`↓` to move, `Enter` to
select (§16). An empty language selection maps to application defaults — source
auto-detect, target falls back to the remembered default.

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
  `Enter` runs it), `Esc` dismisses. `q` and `quit` both exit.
- **Command history:** `↑`/`↓` on the prompt recalls previously submitted commands
  (newest first, drafted text preserved and restored when you pass the newest entry;
  consecutive repeats are deduped, max 100 entries). While the slash picker is open,
  arrows steer the picker instead; `Enter` on a recalled command re-submits it.
- Review/edit/model screens are full-keyboard overlays launched by commands;
  each renders its own key legend on-screen (`p` play, `x` stop, `i` install, …).
- `/settings` and `/wizard` are **modal overlays** over the live REPL — the transcript
  stays visible behind them, and the wizard mirrors its current step into the transcript
  as it runs (Pi-style), so setup reads like a conversation. `/settings` opens a
  **two-choice menu** (Transcribe / Translation); after the local/cloud choice a
  **step menu** of the remaining steps (`[model, language]` local, `[connect, model,
  language]` cloud — see §7 table); `Esc` on a step returns to the step menu,
  `Esc` on the step menu returns to the two-choice menu, `Esc` there closes settings.
- **Searchable choices:** every picker (provider, model, reasoning, language) is a
  keyboard-driven list — type to filter, `↑`/`↓` move the highlight, `Tab`/`Enter` select.
- Forms: `Tab` / arrows move focus; `Enter` submits the focused field.
- Mouse support is incidental convenience, never a requirement.

Every interactive screen ships its key legend on-screen so the interface stays
discoverable without documentation.


## 8. Hardware profiles & local model management

Whisper models are offered as named profiles with VRAM guidance; installation happens
on demand from within the app (models download automatically on first use and are
cached locally):

| Model | Profile | Guidance |
|---|---|---|
| `large-v3` *(default)* | Quality | ~10 GB VRAM |
| `medium` | Balanced | ~5 GB VRAM |
| `small` | Lightweight | ~2 GB VRAM |
| `base` | Lightweight | ~1 GB VRAM |

Suggested pairings:

| Your hardware | Suggested setup |
|---|---|
| High-end GPU | WhisperX large-v3 + local Qwen |
| Mid-range GPU | WhisperX medium + local/remote LLM |
| CPU only | WhisperX small + remote LLM |
| Very low-end | Remote ASR + remote LLM |

The model manager shows which models are already cached and installs missing ones;
local inference requires the optional extra (`pip install "subforge[local]"`).

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
| Transcribe | WhisperX (`large-v3` … `base`, install on demand) | OpenAI Audio API (`whisper-1`, `gpt-4o-transcribe`, …); any OpenAI-style `/transcriptions` endpoint is registered as a provider (`remote`) but not yet surfaced in Settings |
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

Python ≥ 3.11, installed via pip/uv. Core install has no heavy ML dependencies;
local transcription is an explicit extra (`subforge[local]`). Console command:
`subforge [project_dir]` — an optional project directory opens directly;
`subforge --version` prints the version.

## 20. Configuration & privacy defaults (local-first)

Defaults favor fully-local operation: transcription `local/large-v3/auto/auto`,
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
upstream stages. Stages recorded: `transcription` → `alignment` (informational only —
WhisperX aligns inside transcription, so v0.2.0 never runs it as its own stage) →
one `translation_<lang>` per target language → `caption_review` →
`export`. The project file (`project.json`) is the single source of truth and survives
restarts mid-pipeline. Every completed stage also leaves a durable artifact next to it:
`transcripts/source.json` after transcription and `translations/<lang>.json` (id + text
snapshots, one per completed language) after translation — rendered SRT/ASS then go to
`exports/` (§17).

## 23. MVP scope (v0.2.0) & acceptance criteria

In scope:

1. **Transcription** — local WhisperX (large-v3 → base, installable in-app) or OpenAI
   Audio API; segment timestamps; auto/manual language. Acceptance: a scripted-provider
   project goes audio-in → normalized transcript persisted → segments merged, timing
   untouched.
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
