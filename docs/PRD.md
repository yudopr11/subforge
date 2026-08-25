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

- Video editing, playback preview, waveform visualization (V2+).
- Burning subtitles into video.
- Real-time/live captioning.
- Being an LLM prompt playground — translation is a focused, constrained task.

## 7. Primary UX flow (Terminal UI)

`subforge` launches the Textual TUI. The main menu matches this mockup:

```
┌──────────────────────────────────────────────────────────┐
│ SUBFORGE — local-first subtitles                         │
│                                                          │
│  ▸ Select Audio / Open Project                           │
│    Transcribe                                            │
│    Review Captions                                       │
│    Translate                                             │
│    Review Translation                                    │
│    Export SRT / ASS                                      │
│    Settings                                              │
│                                                          │
│ ↑↓ Enter · n new · o open · s settings · m spk    q: Quit │
└──────────────────────────────────────────────────────────┘
```

The Settings screen offers both **re-running the setup wizard** (prefilled with current
values) and direct manual editing of every transcription/translation option.

End-to-end flow:

```
final_audio.wav
      ↓
 Transcribe (local WhisperX or remote STT)
      ↓
 Review Captions (edit text; timing stays application-owned)
      ↓
 Translate   (LM Studio / Ollama / OpenAI-compatible LLM)
      ↓
 Review Translation
      ↓
 subtitle.id.srt · subtitle.en.srt · subtitle.en.ass …
```

Setup happens inside the TUI (**Settings**, reachable from the main menu or `s`) and
can be changed at any time without restarting the project — including re-running the
full setup wizard:

1. **Transcribe** — *Local*: pick/install a Whisper model sized for your machine;
   or *Provider*: paste your OpenAI API key → pick a model from the live list.
2. **Translate** — *Local*: point at your LM Studio/Ollama URL → pick a model;
   or *Provider*: choose OpenAI / OpenCode Zen / OpenCode Go → paste API key →
   pick a model (+ reasoning level if the model offers one).

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
navigation by row, edits persist immediately to the project file. Timing is displayed
but owned by the application (§10). The MVP editing surface is text correction;
split/merge/delete/add arrive in V2 (see §23).

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

## 12. Speaker diarization & speaker naming

Optional stage. When enabled, speakers are detected and assigned to segments as
anonymous IDs (`SPEAKER_00`, `SPEAKER_01`, …). A speaker-map screen lets the user name
speakers ("SPEAKER_00" → "Adi"). Diarization being off never blocks the rest of the
pipeline — the stage records SKIPPED.

## 13. Translation review

Side-by-side source/translation table with inline fixes, identical persistence rules
as §9. Reviewing is part of the core workflow, not an afterthought.

## 14. Live model discovery

Users never type model IDs. For any configured provider the app fetches
`GET {base_url}/models` live and presents the actual list:

| Stage | Local option | Provider option |
|---|---|---|
| Transcribe | WhisperX (`large-v3` … `base`, install on demand) | OpenAI Audio API (`whisper-1`, `gpt-4o-transcribe`, …) |
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

Any source language the ASR layer detects or the user selects; translations target one
language per run in the MVP, extensible to multiple targets in V2. Language codes are
stored in canonical form (e.g. `id`, `en`, `ja`) and drive output filenames.

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
`subforge`.

## 20. Configuration & privacy defaults (local-first)

Defaults favor fully-local operation: transcription `local/large-v3/auto/auto`,
diarization disabled, translation via OpenAI-compatible URL pointing at LM Studio
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
upstream stages. Stages: transcription → diarization → translation → review → export.
The project file (`project.json`) is the single source of truth and survives restarts
mid-pipeline.

## 23. MVP scope (v0.2.0) & acceptance criteria

In scope:

1. **Transcription** — local WhisperX (large-v3 → base, installable in-app) or OpenAI
   Audio API; segment timestamps; auto/manual language. Acceptance: a scripted-provider
   project goes audio-in → normalized transcript persisted → segments merged, timing
   untouched.
2. **Caption review** (§9) — view/edit/correct generated captions; edits persist.
3. **Translation** (§10–§11) — contextual batches of five with strict validation;
   LM Studio / Ollama / OpenAI / OpenCode Zen / OpenCode Go.
4. **Speaker diarization** *(optional)* (§12) — anonymous IDs, mappable names.
5. **Export** — SRT (universal) + ASS (styled default), source language plus completed
   translations; incomplete translations are skipped, never half-written.
6. **Resumable pipeline** (§22) — retry just the failed stage; completed stages stay done.
7. **TUI** (§7) — full setup and workflow in-terminal; no `.env` step required.

Explicitly deferred to V2/V3: multiple target languages, translation memory &
terminology dictionaries, better segmentation, split/merge/delete/add caption
operations, waveform visualization, batch processing, sound-event captions
(`[laughter]`, `♪ music ♪`), plugin architecture, styling templates, video preview.

## 24. Success metrics

- Median time-to-export under 20 minutes for a 15-minute video.
- < 1% of translation batches failing validation against well-behaved models.
- Zero support cases of timing drift after translation (guarantee §10).
- Share of users running fully local pipelines (privacy goal).

## 25. Roadmap

- **V2** — multiple target languages, translation memory & terminology dictionaries,
  better segmentation, waveform visualization, batch processing.
- **V3** — automatic sound-event captions (`[laughter]`, `♪ music ♪`), plugin
  architecture, subtitle styling templates, video preview.

## 26. Philosophy

> AI handles the repetitive work. The creator remains the editor.

AI output is never assumed perfect — every caption and translation passes through human
review before export.
