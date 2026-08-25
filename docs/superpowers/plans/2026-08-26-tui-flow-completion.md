# TUI Flow Completion Plan

> **Execution:** superpowers:executing-plans · one commit per task · gates per task:
> `uv run pytest tests/ -q && uv run ruff check src tests && uv run mypy src`

**Goal:** Turn the skeleton TUI into the real creator flow: first-run setup →
project open/create → transcribe → review (with audio preview) → translate →
review → export, with provider-driven reasoning, busy-guards, and back navigation.

**Baseline:** MVP core plan (`2026-08-25-subforge-mvp-core.md`) tasks 0–25 complete.
Specs: `docs/PRD.md`, `docs/ARCHITECTURE.md` (v0.2.0).

---

## Task 1: Core enablers — detected language + reasoning passthrough — DONE

- [x] Pipeline fills `meta.source_language` from ASR-detected language when auto (`test_pipeline_language.py`)
- [x] `TranslationService` forwards `reasoning_effort` verbatim; protocol + fakes updated
- Commit: `feat: detected-language capture and reasoning-effort passthrough`

## Task 2: AppConfig → Pipeline builders (TUI seam) — DONE

- [x] `resolve_reasoning_effort(cfg, client)` drops stale/local values; survives catalog failure
- [x] `build_translation_service`, `build_pipeline` wire providers or leave stages unset
- [x] `transcription_configured` / `translation_configured` readiness checks
- Commits: `feat: AppConfig-driven pipeline/service builders…`

## Task 3: Project helpers + discovery — DONE

- [x] `create_project_from_audio` (copy into layout, collision suffixes)
- [x] `find_audio_file`
- [x] `discover_projects` (recent-first, project.json filter)

## Task 4: Main-menu wiring + project picker — DONE

- [x] New-from-audio / Open-project flows
- [x] `ProjectPickerScreen`: existing projects listed recent-first + `[+] Create new…`
- [x] Guided setup: unconfigured Transcribe/Translate opens Settings instead of dead-ending
- [x] Flow-aware status bar ("next: Translate", "done — files in exports/")

## Task 5: Stage busy-guards + Esc-back navigation — DONE

- [x] One run per stage; second press → `[BUSY] … already running`; ⏳ status while running
- [x] CaptionReview / ReviewTranslate / SpeakerMap converted to modals; Esc returns to menu

## Task 6: Caption-review audio preview — DONE

- [x] `app/audio_player.py`: ffplay/mpv/cvlc detection, segment-range commands, stop/kill
- [x] Review screen ▶ Play (p) / ■ Stop (x) + buttons; injectable player for offline tests

## Task 7: Language preferences — DONE

- [x] `TranscriptionConfig.language` ("" = auto-detect) asked in wizard + Settings button;
      seeded into new projects' meta so ASR gets it
- [x] `TranslationConfig.default_target` asked at end of wizard; remembered and used as
      TargetLanguageScreen default; persisted back after each translate

## Task 8: First-run setup wizard — IN PROGRESS ← current

- [x] `FirstRunSetupScreen`: Step 1 transcribe (Local→model→install offer | OpenAI→key→live model list)
- [x] Step 2 translate (Local→URL→optional key→live model list | Cloud→preset→key→live model list)
- [x] App routes to wizard when `is_first_run()`; Esc skips without saving
- [x] Validation blocks save until both models chosen (+URL/key where applicable)
- [ ] **Reasoning-effort prompt after translation model choice** (PRD §15): cloud only,
      offers exactly the model's discovered values via `ReasoningPickerScreen`; skipped
      silently for local servers / non-reasoning models / catalog failure
      ← code written, tests pending, NOT committed

## Task 9: CI — DONE

- [x] GitHub Actions: ruff + mypy strict + pytest on 3.11–3.13

## Task 10: Release hygiene — PENDING

- [ ] Full gate re-run + amend any stragglers
- [ ] README quick-start reflects wizard + shortcuts
- [ ] Push to origin (`git push -u origin main`) — needs owner go-ahead
