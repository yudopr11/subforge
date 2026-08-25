# Plan: Keyboard-only TUI interaction model

> Execution: superpowers:executing-plans · gates: pytest + ruff + mypy strict
> Docs-sync: PRD §7 / ARCHITECTURE §3 updated in this changeset (docs commit leads).

**Goal:** All TUI interaction is keyboard-first, CLI-style — no action may require the
mouse. Settings gets explicit one-letter bindings for every field plus an always-visible
key legend; source pickers become cycle-buttons (no radio widgets needed).

---

## Task 1: Specs — keyboard-only interaction model — DOCS FIRST

- [ ] `PRD.md` §7: new "Interaction model — keyboard only" block (global/menu/settings
      keys, mouse optional-never-required) + footer hint in mockup.
- [ ] `ARCHITECTURE.md`: new **§3.2 Keyboard-only interaction** (BINDINGS-first design,
      focus order, legend rule, Input-focus absorbs typing so bindings don't collide).
- [ ] `AGENTS.md` Conventions bullet pointing at ARCH §3.2.
- [ ] Commit: `docs:` immediately.

## Task 2: Settings screen keyboard UX

- [ ] One-letter BINDINGS for every control:
      `w` wizard · `t` transcribe source · `y` transcribe model · `k` transcribe key ·
      `o` audio language · `c` translate source · `p` preset · `i` translate key ·
      `d` translate model · `n` base URL · `r` reasoning · `b` batch · `g` target lang ·
      `ctrl+s` save · `esc` back.
- [ ] Always-visible key-map legend label.
- [ ] Replace RadioButtons with cycle-buttons (`btn-tc-source`, `btn-tl-source`) that
      show current value; `set_*` seams unchanged.
- [ ] `AUTO_FOCUS = "#btn-wizard"`; Tab/arrows walk the rest.
- [ ] Tests: key-driven toggling (`t`), wizard launch (`w`), save (`ctrl+s` persists),
      esc-back-to-menu; existing seams/dom assertions still pass.

## Task 3: Consistency sweep

- [ ] Other screens keep/declare their key legends (menu status, review screens).
- [ ] Gates + plan checkboxes ticked; conventional commits.
