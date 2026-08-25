# Plan: Redesign home as subtitle REPL (pi/coding-CLI style)

> Execution: superpowers:executing-plans · gates: pytest + ruff + mypy strict
> Docs-sync leads (PRD §7 pivot). Approved by owner: full REPL replaces list-menu;
> review/edit flows stay as overlay screens launched by commands.

**Goal:** SubForge's home becomes a transcript-driven REPL like pi/Claude Code/Codex:
scrolling session log, one bottom `>` prompt, thin footer status line, slash commands.

---

## Task 1: Spec pivot — DOCS FIRST

- [x] PRD §7 rewritten: REPL mockup, command table (`/new /open /transcribe /review
      /translate /export /speakers /settings /wizard /models /status /help /quit`),
      keyboard-only block retained, list-menu removed everywhere.
- [x] ARCHITECTURE §3.2 extended: REPL shell anatomy (RichLog transcript + prompt +
      footer status), command registry routes to `app/*` services (rule 7 intact).
- [x] Commit: `docs:` immediately.

## Task 2: REPL shell core

- [x] `tui/screens/repl.py::ReplScreen`: RichLog transcript + `#prompt` Input +
      docked footer status bar (project · stage glyphs ✓●✗○– · active models).
- [x] Command registry + parser: `run_command(raw)` public seam; unknown → error line;
      bare-word aliases accepted (leading `/` optional).
- [x] Orchestration moves from MainMenuScreen verbatim: pipeline_factory seam,
      busy-guards (`_running_stages`), `_launch_stage`, do_transcribe/do_translate/
      do_export, readiness-guidance lines pointing at `/settings`.
- [x] `/new <audio>` seeds meta.source_language from AppConfig (closes gap noted in
      language feature).
- [x] `/open` lists recents (numbered) when bare; opens by index or name.
- [x] `/status` prints stage states; `/help` prints command table; `/quit` exits.

## Task 3: Overlay commands + navigation

- [x] `/settings`, `/wizard` (prefilled), `/review`, `/speakers`, `/models` push the
      existing modal screens; Esc returns to the REPL transcript.
- [x] `app.py`: mount `ReplScreen` (first-run wizard still overlays it);
      `_setup_finished` notifies the REPL.

## Task 4: Tests — port + new (AGENTS testing rules)

- [x] New `tests/unit/test_repl.py`: welcome/help/unknown-cmd; `/new`→`/transcribe`→
      `/translate en`→`/export` e2e with scripted providers asserting files +
      `project.json` states; unconfigured `[SETUP]` guidance; busy-guard; `/open`
      listing + index/name selection; `/status` output.
- [x] Retire `test_tui_flow.py` + `main_menu.py` (superseded); port navigation tests to
      REPL base; update wizard first-run stack assertions.
- [x] Gates green.

## Task 5: README quick-start rewrite to command flow

---

## Decisions

- Slash commands with optional leading-slash aliases; bare `q` dropped (input eats it) —
  exit is `/quit` or Ctrl+C.
- Review/edit remain overlay screens (owner-approved), launched by commands.

## Task 6: /new interactive audio locate (`@` browse)

- [x] Bare `/new` enters **locate mode**: prompt repurposed for the audio path
      (placeholder + footer reflect it), Esc cancels, Enter submits a path.
- [x] Typing `@` (optionally `@query`) and submitting opens an `AudioFilePickerScreen`
      overlay: audio files under the working directory (junk dirs pruned, newest
      first), arrow-select, Enter returns the path into the prompt for confirmation.
- [x] `app/projects.py::discover_audio_files(root, limit)` powers the index.
- [x] Docs: PRD §7 `/new` row notes interactive locate; PRD §7 keyboard block gains
      the `@` pattern.
- [x] Tests: mode enter/cancel; path submit creates project; `@` opens picker with
      filtered matches; picking fills the prompt (project created on second Enter).
