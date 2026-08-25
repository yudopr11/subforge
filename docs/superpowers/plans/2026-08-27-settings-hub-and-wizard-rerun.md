# Plan: Settings hub — re-run wizard or edit manually

> Execution: superpowers:executing-plans · gates per task: pytest + ruff + mypy strict
> Spec-sync rule applies (AGENTS.md "Documentation Sync"): PRD §7 mockup must gain the
> Settings entry in the same changeset.

**Goal:** Main menu shows a visible **Settings** action. Inside Settings the user can
(a) **re-run the setup wizard** (prefilled with current values) or (b) manually edit any
transcription/translation setting (already built — keep working unchanged).

---

## Task 1: Visible Settings action on the main menu

- [x] Append `("settings", "Settings")` to `MainMenuScreen.ACTIONS` (7th item).
- [x] Route the existing `action_settings()` through the selection dispatcher.
- [x] Tests (`tests/unit/test_tui_flow.py`):
  - menu labels include `"Settings"`;
  - driving the `settings` slug pushes `SettingsScreen`.

## Task 2: Wizard re-run from Settings (prefilled)

- [x] `FirstRunSetupScreen(initial_config: AppConfig | None = None)` — wizard starts from
      a deep copy of the caller's config when given, else fresh defaults (first-run path
      unchanged).
- [x] `SettingsScreen`: header-level button `Re-run setup wizard…` (`btn-wizard`) +
      public seam `open_wizard()` that pushes the wizard prefilled with `self.cfg`.
- [x] On wizard completion: reload `self.cfg` from disk, refresh all labels, invoke
      `on_saved` (providers rebuild mid-session, no restart).
- [x] Tests (`tests/unit/test_settings_screen.py`):
  - `open_wizard()` puts `FirstRunSetupScreen` on top and **prefills** it (mutate
    `cfg.transcription.model`, see it inside the wizard);
  - finishing the wizard persists to disk, `screen.cfg` reflects saved values,
    `on_saved` fired exactly once.

## Task 3: Documentation sync (AGENTS.md rule)

- [x] `docs/PRD.md` §7: mockup gains a `Settings / Run setup again` line; one sentence
      noting wizard re-run is offered alongside manual editing.
- [x] Commit order: `feat:` (tasks 1–2) then `docs:` immediately after.

## Deferred

- Splitting Settings into tabbed sections; per-stage "Test connection" buttons.
