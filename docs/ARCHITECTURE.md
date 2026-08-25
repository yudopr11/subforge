# SubForge — Technical Architecture

**Version:** 0.2.0 · **Status:** Active · **Last revised:** 2026-08-25

Companion document: [`docs/PRD.md`](PRD.md). Section numbers are referenced throughout
the codebase and plans (`ARCH §N`) — change them only with a repo-wide search.

---

## 1. System context

SubForge is a local Python application (Textual TUI) that turns exported final audio
into timestamped captions and translations, exporting SRT/ASS. External systems are
pluggable providers: local WhisperX / LM Studio / Ollama, and cloud OpenAI Audio API /
OpenAI / OpenCode Zen / OpenCode Go. The application core never knows which.

## 2. Tech stack

Python ≥ 3.11 · pydantic v2 (+pydantic-settings semantics) · httpx · Textual ·
pytest + pytest-asyncio · ruff (`line-length = 100`) · mypy `--strict`. Heavy ML deps
(whisperx/torch) are optional extras — never core dependencies.

## 3. Repository layout & layering

```
src/subforge/
  models/        canonical data models (no I/O, no providers)
  subtitles/     SRT/ASS writers + timeutils (pure functions)
  app/           services: project_store, pipeline, translation_service,
                 export, model_manager, provider_factory
  providers/     base protocols, registry, concrete providers per family
  config/        settings (env), app_config (TUI-authored), providers (presets)
  tui/           Textual app + screens (presentation only)
  cli/           entrypoint
tests/unit/  tests/integration/  tests/fixtures/
```

### 3.1 The TUI contains no business logic

Screens construct and call `app/pipeline.py`, `app/export.py`, etc. Widgets render
state and forward user intent; sequencing, validation, persistence live in `app/`.

### 3.2 Keyboard-only interaction

Screens are keyboard-first by contract (PRD §7):

- Every user-reachable action is exposed as a Textual `BINDINGS` entry; pointer events
  are treated as incidental duplicates.
- Each screen renders an always-visible key legend so shortcuts are discoverable.
- Focus order follows visual order (`AUTO_FOCUS` targets the primary control);
  `Tab`/arrows walk every control, `Enter` activates.
- Widgets that consume typing (e.g. `Input`) naturally shadow single-letter bindings
  while focused, preventing collisions.

- The home screen is a **REPL shell**: a scrolling transcript log, one bottom prompt,
  and a footer status line (project · stage glyphs · active models). Commands are parsed
  by a registry (`repl.py::COMMANDS`) that routes to `app/*` services — the screen adds
  presentation only (rule 7). Review/edit screens are overlays pushed above the REPL.

## 4. Core runtime components

`Project`/`Segment` (models) → `Pipeline` orchestrates stages over them → providers do
inference → `translation_service` validates LLM output → writers render →
`project_store` persists atomically.

## 5. Provider architecture

The application core depends only on the protocols in `src/subforge/providers/base.py`.
Concrete providers are resolved via `providers/registry.py`; new providers register in
their own module. Core pipeline code stays untouched when a provider is added.

## 6. Provider protocols & normalization

- `TranscriptionProvider.transcribe(audio_path, language=None) -> Transcript`
- `DiarizationProvider.diarize(audio_path) -> list[DiarizationTurn]`
- `TranslationProvider.translate(segments, source_language, target_language) -> list[TranslationOutput]`

Every provider normalizes to identical internal types inside its own module:
`Transcript` is byte-for-byte the same shape regardless of where inference ran.
Diarization turns carry anonymous speakers (`SPEAKER_00`, …).

## 7. Optional dependencies policy

whisperx/torch live behind the `[local]` extra. Import them lazily inside functions,
never at module top level; raise actionable errors naming the extra when missing.

## 8. Model lifecycle (local ASR)

`LocalModelManager` probes the HF cache for installed models, downloads on demand via
faster-whisper utilities, and reports profile/VRAM metadata (PRD §8).

## 9. Capability discovery

Per-model reasoning vocabularies come from the models.dev catalog at request time;
values are passed through verbatim or omitted (PRD §15). Catalog fetch failure degrades
to "unsupported", hiding the control — never a crash.

## 10. Remote STT contract

OpenAI-style `POST {base_url}/audio/transcriptions`, multipart file upload,
`response_format=verbose_json`. Responses normalize into `Transcript`; models without
segment timestamps degrade to a single `[0, duration]` segment rather than failing.

## 11. Translation request shape

`POST {base_url}/chat/completions` with `response_format={"type":"json_object"}`,
`max_tokens: 2048`, a language-agnostic JSON-only system prompt, and user content
carrying `{source_language, target_language, segments:[{id,text}]}`.
`reasoning_effort` is included ONLY when non-None (§9).

## 12. Response parsing

Robust parsing: markdown code fences stripped; invalid JSON raises `ValueError`;
reasoning-only responses (`content: null`, seen from MiMo/Nemotron on OpenCode) raise a
clear error instead of crashing batch processing.

## 13. Diarization merge rule

Speaker assignment uses maximum-overlap-wins between segment interval and turn interval;
fully uncovered segments get no speaker.

## 14. OpenAI-compatible translation provider

One provider class serves LM Studio, Ollama, OpenAI, OpenCode Zen/Go — differing only
in base URL/key/model (PRD §14 table). Auth: `Authorization: Bearer <key>`.
`list_models()` fetches `GET {base_url}/models` sorted for stable UI ordering.

## 15–16. Batch flow & output validation

Batches of five consecutive segments (default). **Validation rules enforced in
`app/translation_service.py::_validate_batch`** (extend there, not in providers):

1. Output parses as the agreed JSON shape (provider-level).
2. Exactly one output per input ID — missing IDs fail the batch.
3. No unknown IDs.
4. No duplicate IDs.
5. Non-empty text.

Invalid output fails that batch only: its segments stay untouched, successful batches
still merge, errors aggregate, stage records FAILED, nothing corrupts the project.

## 17. Canonical data shapes

```json
{ "id": 0, "start": 1.2, "end": 3.4, "source": "…", "speaker": null,
  "translations": { "en": "…" } }
```

SRT and ASS are *output formats only*; seconds-as-floats is the internal truth.
Never store formatted timestamps as data.

## 18. Export service

`export_subtitles(project_dir, formats, languages)` renders from the canonical model.
It never calls an LLM. Source always exports; a translation language exports only when
complete across all segments. Unknown formats raise `ValueError`.

## 19. SRT format

`HH:MM:SS,mmm` stamps, comma milliseconds, integer rounding at ms precision, blocks of
`id / stamp --> stamp / text`.

## 20. ASS format

`H:MM:SS.cc` centisecond stamps; header carries `PlayResX/Y` and one configurable
`Style: Default` line (font, size, primary colour); one `Dialogue:` event per segment.
Speaker-specific styles are V2+.

## 21. Project storage

```
<project>/
  project.json      # single source of truth (pydantic-validated)
  audio/            # user-supplied final audio
  transcripts/      # normalized source.json after transcription
  translations/
  exports/
```

Saves are atomic: write `.json.tmp`, then `os.replace`. Floats stay floats in JSON.

## 22. Stage state machine

Exactly five states recorded in `project.json`: `PENDING`, `RUNNING`, `COMPLETED`,
`FAILED`, `SKIPPED`. Every expensive stage records explicit state before/after work.

## 23. Resumability rules

Persist state around every transition. Retrying must never rerun completed upstream
stages; `retry(stage)` re-runs only non-completed stages. Failed stages rerun cleanly
because inputs (canonical segments) are immutable downstream of their owning stage.

## 24. Layered configuration

Defaults < `.env` file < environment variables. Env names follow explicit
`<GROUP>_<FIELD>` mapping (e.g. `TRANSCRIPTION_MODEL`, `TRANSLATION_BASE_URL`) applied
in `config/settings.py`; nested-delimiter magic is avoided because field names contain
underscores.

## 25. `.env.example`

Documents headless-only knobs (transcription/diarization/translation groups) with
placeholder values and empty `TRANSLATION_API_KEY`/`TRANSLATION_MODEL`. Never commit
a real `.env`.

## 26. Provider registry

`REGISTRY` singleton; factories registered at module bottom via
`register_transcription/register_diarization/register_translation(name, factory)`.
Resolution failures raise `ProviderNotFound`. Built-ins: transcription
`local-whisperx`, `remote`, `openai`; translation `openai-compatible`.

## 27. Lazy heavy imports

All heavy/optional imports sit inside functions (`import whisperx` within
`transcribe()`) so core installs stay light and import fast.

## 28. Preset URLs

Cloud preset URLs live ONLY in `src/subforge/config/providers.py`
(`TRANSLATION_PRESETS`, `OPENAI_TRANSCRIPTION_BASE_URL`). User keys/models live ONLY in
AppConfig. Never hardcode either elsewhere.

## 29. Security & privacy

Never commit: `.env` or any API key; user audio (`*.wav *.mp3 *.flac`); generated
subtitles (`*.srt *.ass`); model weights/caches; user project data. `.gitignore`
covers these. AppConfig holds plaintext keys by design — written atomically
(`os.replace`) with mode `0600` to `~/.config/subforge/config.json` (env override
`SUBFORGE_CONFIG`). Keys are never echoed in logs, errors, or tests.

## 30. Hardware detection (future)

Recommended profiles from runtime inspection (GPU presence/VRAM) feeding PRD §8
suggestions. Deferred.

## 31. Concurrency model

MVP runs stages synchronously; TUI workers wrap long calls. Providers own their HTTP
clients and timeouts (120 s chat completions, 600 s STT).

## 32. Audio ingestion

MVP assumes editor-exported WAV/FLAC/MP3 opened read-only. FFmpeg-based
conversion/validation is deferred.

## 33. Versioning

App version single-sourced in `src/subforge/__init__.py`; `subforge --version` prints
it. Project files tolerate additive schema changes via pydantic defaults.

## 34. Testing strategy

All tests run without network access, GPU, downloaded models, or running LLM servers:
`httpx.MockTransport` for HTTP providers, scripted fakes for ASR/diarization/LLM
(`tests/integration/test_full_flow.py` is the pattern). Binary audio fixtures are never
committed — generated deterministically at test time (`tests/fixtures/make_sine_wav.py`).
Integration covers audio → transcript → translation → export plus retry-after-failure
resumability.

## 35. CI

Lint (ruff), types (mypy --strict), tests (pytest) on push — deferred until repository
hosting exists; commands already gate locally.

## 36. Observability

Failures surface as prefixed, human-readable stage errors (PRD §21); no telemetry.
Providers raise typed exceptions; the pipeline converts them to `StageError` with
context.

## 37. Architectural principles

1. **P1 — Provider independence.** Core imports only `providers/base.py` protocols.
   Violating this is a bug even if tests pass.
2. **P2 — Local first, not local only.** Heavy ML deps optional, lazily imported (§7, §27).
3. **P3 — AI does not own metadata.** LLMs generate text only; IDs/timestamps are
   application-owned and validated on merge (PRD §10, §16).
4. **P4 — Human review.** All AI output is editable; review screens are core workflow.
5. **P5 — Resumable pipeline.** Explicit states; completed stages never rerun (§22–23).
6. **P6 — Canonical representation.** One segment shape; SRT/ASS are projections (§17).
7. **P7 — The TUI contains no business logic** (§3.1).
