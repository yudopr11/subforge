# AGENTS.md — Guidance for Coding Agents Working on SubForge

Instructions for AI coding agents (and human contributors using agent tooling) working in this repository.

## Project Overview

SubForge is a **local-first subtitle generation and translation tool** for content creators. It transcribes exported final audio into timestamped captions, optionally translates them via LLMs, and exports SRT/ASS files through a Textual TUI.

**Read these before doing anything non-trivial:**

- `docs/PRD.md` — what SubForge is (product requirements, v0.2.0)
- `docs/ARCHITECTURE.md` — how it must be built (technical architecture, v0.2.0)
- `docs/superpowers/plans/` — current implementation plans

## Non-Negotiable Architectural Rules

These come from ARCHITECTURE.md §37. Violating any of them is a bug even if tests pass:

1. **Provider independence.** The application core depends only on the protocols in `src/subforge/providers/base.py`. Never import a concrete provider (`whisperx`, `openai_compatible`, …) outside its own module. New providers are registered in `src/subforge/providers/registry.py`.
2. **Local first, not local only.** Heavy ML deps (whisperx, torch) are optional extras `[local]`. Import them lazily inside functions; never at module top level.
3. **AI does not own metadata.** LLMs generate text only. Segment IDs, timestamps, project state, file paths are application-owned and validated on merge. Translation output missing/duplicating IDs or empty text must fail that batch — never silently corrupt the project.
4. **Human review.** All AI output is editable; review screens are part of the core workflow, not an afterthought.
5. **Resumable pipeline.** Every expensive stage records explicit state (`PENDING/RUNNING/COMPLETED/FAILED/SKIPPED`) in `project.json`. Retrying a stage must never rerun completed upstream stages.
6. **Canonical internal representation.** SRT and ASS are *output formats only*. The canonical model is `Segment {id, start: float seconds, end: float seconds, source, speaker?, translations{lang→text}}` in `src/subforge/models/project.py`. Never store formatted timestamps as data.
7. **The TUI contains no business logic.** Screens construct and call `app/pipeline.py`, `app/export.py`, etc.

## Commands

```bash
uv sync                          # install deps (or pip install -e .)
uv run pytest                    # all tests
uv run pytest tests/unit -v      # unit only
uv run ruff check src tests      # lint
uv run mypy src                  # type check (strict)
```

All tests must pass without network access, GPU, downloaded models, or running LLM servers. Use fakes/mocks (`httpx.MockTransport`, scripted providers) — see `tests/integration/test_full_flow.py` for the pattern.

## Conventions

- Python ≥ 3.11, full type hints, `mypy --strict` clean.
- Formatting/linting via ruff (`line-length = 100`).
- Pydantic models for anything serialized to `project.json`; frozen dataclasses for provider value objects.
- Tests live in `tests/unit/`, `tests/integration/`, fixtures in `tests/fixtures/`. One test file per module, mirroring `src/` layout.
- Commit style: conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Work task-by-task from a plan in `docs/superpowers/plans/`; each plan task ends with a commit.
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit.

## Security & Privacy (ARCHITECTURE §29)

Never commit:

- `.env` or any API key
- Secrets live only in: (a) the TUI-authored AppConfig at `~/.config/subforge/config.json` (`chmod 600`, atomic writes — primary path) and (b) environment variables for headless automation (`OPENAI_API_KEY`, `OPENCODE_API_KEY`). Never hardcode keys, never echo them in logs/tests/output.
- user audio (`*.wav`, `*.mp3`, `*.flac`)
- generated subtitles (`*.srt`, `*.ass`)
- model weights, caches, or user project data

`.gitignore` already covers these — keep it that way. Test audio fixtures must be synthetic/openly licensed; generate binary fixtures at test time when possible.

## Error Handling Style

User-facing failures follow PRD §21: explicit, prefixed messages (e.g., `[ERROR] LM Studio is not running.`) raised as `StageError` from pipeline stages, so the TUI can display them and the user can retry just that stage. Fail loudly at validation boundaries; never swallow exceptions in providers.

## Cloud Providers & Model Discovery

Preset URLs live ONLY in `src/subforge/config/providers.py`; user keys/models live ONLY in AppConfig:

- Transcription: `local-whisperx` (default) · `openai` → `https://api.openai.com/v1/audio/transcriptions`
- Translation: local OpenAI-compatible URL (LM Studio/Ollama) · `openai` → `https://api.openai.com/v1` · `opencode-zen` → `https://opencode.ai/zen/v1` · `opencode-go` → `https://opencode.ai/zen/go/v1`

Model IDs are discovered live via `GET {base_url}/models` — never hardcode model lists. **Reasoning parameters are metadata-driven**: allowed effort values come from the models.dev catalog (`providers/capabilities.py`) and vary per model (`glm-5.2`=[high,max], `kimi-k3`=[max], some use toggles, non-reasoning models have none). Pass them through verbatim; validate stored choices against the current model's spec and reset stale ones.

## When Adding a Provider

1. Implement the protocol from `providers/base.py` (`TranscriptionProvider`, `DiarizationProvider`, or `TranslationProvider`).
2. Normalize output to the internal types (`Transcript`, `TranslationOutput`) inside your module.
3. Register with `REGISTRY.register_*("<name>", Factory)` at module bottom.
4. Unit-test with mocks (no real network/models).
5. Core pipeline code stays untouched — if you find yourself editing `pipeline.py` to add a provider, stop and re-read rule 1.

## When Touching Translation

- Batch size default is 5 (contextual batches, PRD §11).
- Validation rules (ARCH §16): valid JSON, one output per input ID, no unknown IDs, no duplicates, non-empty text. Enforced in `app/translation_service.py::_validate_batch` — extend there, not in providers.
- The system prompt lives in the OpenAI-compatible provider; keep it language-agnostic and JSON-only.
