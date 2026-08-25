# SubForge

> **Create once. Caption for everyone. Translate for the world.**

SubForge is a local-first subtitle generation and translation tool for content creators. Export the final audio from your video editor, and SubForge turns it into accurate, timestamped captions — then translates them into other languages while preserving every timestamp.

Built for accessibility first: captions that let Deaf and hard-of-hearing viewers follow your content, and translated subtitles that let the rest of the world enjoy it too.

## Why SubForge?

- **Accessibility** — videos without captions exclude Deaf and hard-of-hearing viewers (and everyone watching on mute).
- **Reach** — Indonesian content shouldn't stay Indonesian. Generate source captions once, translate to English, Japanese, Spanish, and more.
- **Time** — manual subtitling takes 1–3 hours per video. SubForge targets 10–20 minutes, with you as the editor.
- **Privacy** — local-first by default. Your audio and transcripts never leave your machine unless *you* configure a remote provider.

## How It Works

```
final_audio.wav
      ↓
 Transcribe (local WhisperX or remote STT)
      ↓
 Review Captions (edit text & timing)
      ↓
 Translate   (LM Studio / Ollama / OpenAI-compatible LLM)
      ↓
 Review Translation
      ↓
 subtitle.id.srt · subtitle.en.srt · subtitle.en.ass
```

**A core guarantee:** the LLM only ever produces text. Segment IDs and timestamps are owned by the application and validated on merge — translation can never shift your timing.

## Features (MVP)

- 🎙️ **Transcription** — local WhisperX (large-v3 → base models, installable in-app) or the OpenAI Audio API, segment timestamps, auto/manual language selection
- 🔎 **Live model discovery** — enter your API key (or local server URL) and SubForge fetches the available model list automatically; you just pick one — for transcription *and* translation
- 🧠 **Provider-driven reasoning control** — when a model supports reasoning effort, SubForge offers exactly the values that model accepts (they differ per model!); otherwise the control is hidden
- ✍️ **Caption review** — view, edit, and correct generated captions in a terminal UI
- 🌐 **Translation** — LM Studio / Ollama (local), OpenAI, OpenCode Zen & OpenCode Go (cloud) — contextual batch translation with strict structured-output validation
- 📤 **Export** — SRT (universal compatibility) and ASS (advanced styling), source language plus translations
- 🔁 **Resumable pipeline** — retry just the failed stage; completed stages never rerun
- 🖥️ **Terminal UI** — built with [Textual](https://textual.textualize.io/)

## Installation

Requires Python 3.11+.

```bash
pip install subforge          # core (works with remote providers)

# Optional: local transcription (installs whisperx + torch)
pip install "subforge[local]"
```

**Required for caption audio preview:** [ffmpeg](https://ffmpeg.org) — used to play a
caption's audio range while you review (`p` in the Review Captions screen):

```bash
sudo apt install ffmpeg       # Debian/Ubuntu
brew install ffmpeg           # macOS
```

Whisper models download automatically on first use and are cached locally.

## Quick Start

```bash
subforge            # launches the subtitle REPL
```

First launch opens guided setup: pick where Transcription runs (*Local* WhisperX with
model install, or OpenAI with API key + live model list) and where Translation runs
(*Local* LM Studio/Ollama URL [+ optional key], or OpenAI / OpenCode Zen / OpenCode Go).
Reasoning effort is offered when the chosen model supports it; choose your audio
language and default target language. Everything is editable later via `/settings`,
or re-run `/wizard` anytime.

Then work in commands:

```
 > /new podcast/final_audio.wav      # create project + import audio
 ✓ created project 'final_audio'
 > /transcribe                       # local WhisperX or OpenAI — as configured
 ✓ transcribed — 24 captions
 > /review                           # edit text, p plays the segment audio
 > /translate en                     # or just /translate for your default target
 ✓ translated — 24 segments
 > /export                           # writes exports/source.* and exports/en.*
```

`?` lists all commands (`/open`, `/transcribe`, `/review`, `/translate`, `/export`,
`/settings`, `/wizard`, `/status`, `/quit`). `Esc` backs out of any overlay. Audio
preview requires ffmpeg.

Changed your mind later? Everything above can be switched in the Settings menu at any time — no project restart.

## Configuring Providers

Everything is configured inside the TUI (**Settings** menu) and stored locally at `~/.config/subforge/config.json`:

- **API keys** are typed once into the app (masked input) — never committed, never logged, file saved with `0600` permissions.
- **Model lists are fetched live** from the provider's `/models` endpoint, so you always pick from what's actually available:

| Stage | Local option | Provider option |
|---|---|---|
| Transcribe | WhisperX (`large-v3` … `base`, install on demand) | OpenAI Audio API (`whisper-1`, `gpt-4o-transcribe`, …) |
| Translate | any OpenAI-compatible URL (LM Studio `localhost:1234/v1`, Ollama) | OpenAI · OpenCode Zen · OpenCode Go |

Headless/automation users can still configure via environment variables (`.env`) — see `.env.example`. The app clearly indicates whenever remote processing is in use.

## Hardware Friendly

No GPU? No problem. Choose lightweight local models or route transcription and/or translation through remote providers — the application core doesn't care where inference happens.

| Your hardware | Suggested setup |
|---|---|
| High-end GPU | WhisperX large-v3 + local Qwen |
| Mid-range GPU | WhisperX medium + local/remote LLM |
| CPU only | WhisperX small + remote LLM |
| Very low-end | Remote ASR + remote LLM |

## Privacy

By default everything runs locally: audio stays on disk, transcripts stay in the project folder, translation goes to your own LM Studio/Ollama instance. Nothing is sent anywhere unless you explicitly configure a remote provider.

## Development

```bash
git clone <repo-url> && cd subforge
uv sync                 # or: pip install -e "."
uv run pytest           # tests (no GPU/network required)
uv run ruff check . && uv run mypy src
```

See [AGENTS.md](AGENTS.md) for contributor/agent guidance and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design principles.

Full details: [docs/PRD.md](docs/PRD.md).

## Philosophy

> AI handles the repetitive work. The creator remains the editor.

AI output is never assumed perfect — every caption and translation passes through human review before export.

## License

MIT — see [LICENSE](LICENSE).
