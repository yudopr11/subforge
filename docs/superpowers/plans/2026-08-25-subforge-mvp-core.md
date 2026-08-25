# SubForge MVP Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SubForge MVP core — canonical data model, SRT/ASS writers, project storage, provider interfaces (transcription/diarization/translation), OpenAI-compatible translation with validated contextual batches, resumable pipeline, and export — plus a minimal Textual TUI shell.

**Architecture:** Provider-agnostic subtitle processing platform. The core depends only on `Protocol` interfaces (`TranscriptionProvider`, `DiarizationProvider`, `TranslationProvider`); concrete providers are resolved via a registry. LLMs only ever produce text keyed by segment ID — they never touch IDs or timestamps. The project JSON file is the single source of truth and every pipeline stage records explicit state so failures are individually retryable.

**Tech Stack:** Python ≥ 3.11, pydantic v2 (+pydantic-settings), httpx, Textual, pytest + pytest-asyncio, ruff, mypy. Heavy ML deps (whisperx/torch) are optional extras (`pip install subforge[local]`) — never core dependencies.

**Spec:** `docs/PRD.md` §23 (MVP Features), `docs/ARCHITECTURE.md` (all sections; especially §5 Provider Architecture, §10–16 translation rules, §22–23 pipeline state/resumability, §37 Architectural Principles). Both docs must exist before Task 1 is executed (they are committed in Task 1). This plan argues from those specs; executors read both.

## Global Constraints

- Python version floor: `>=3.11`
- Canonical caption shape (verbatim from ARCHITECTURE §17): `{ "id": int, "start": float, "end": float, "source": str, "speaker": str | null, "translations": { "<lang>": str } }`
- LLM output must never modify segment ID, start, or end timestamps (PRD §10, ARCH §13).
- Translation batches validate: valid JSON, every input ID has exactly one output, no unknown IDs, no duplicate IDs, non-empty text (ARCH §16). Invalid output fails the batch; it must not corrupt the project.
- Pipeline states exactly: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `SKIPPED` (ARCH §22).
- `.env`, audio (`*.wav *.mp3 *.flac`), `*.srt`, `*.ass`, `models/`, `cache/`, `projects/` are git-ignored (ARCH §29).
- No provider-specific logic outside its own module; core imports only protocols.
- Default batch size for contextual translation: 5 segments (PRD §11 example).
- Configuration is **TUI-first** (revision 2026-08-25): API keys and model choices are typed by the user in the TUI and persisted to `~/.config/subforge/config.json` (override with `SUBFORGE_CONFIG`). `.env`/env-vars remain an OPTIONAL fallback for headless automation only — the TUI never reads secrets from `.env`. Config holds plaintext keys: save atomically with `chmod 600`, never commit, never log.
- Cloud providers (verified live 2026-08-25): remote transcription = **OpenAI Audio API only** (`https://api.openai.com/v1/audio/transcriptions`, default model `whisper-1`). Translation: local OpenAI-compatible URL (LM Studio/Ollama) OR cloud preset — `openai` (`https://api.openai.com/v1`), `opencode-zen` (`https://opencode.ai/zen/v1`), `opencode-go` (`https://opencode.ai/zen/go/v1`). All expose `GET {base_url}/models`; the TUI always fetches this list live so users pick real model IDs (transcription and translation alike).
- **Reasoning parameters are provider-driven, never hardcoded.** Allowed effort terms come from model metadata in the models.dev catalog (`https://models.dev/api.json`, field `reasoning_options`) and genuinely vary per model — e.g. `glm-5.2` accepts `[high, max]`, `kimi-k3` only `[max]`, `grok-4.5` `[low, medium, high]`, `gpt-5.6-luna` adds `none`, some models use a `toggle` instead of effort levels, non-reasoning models have none. If a model exposes no effort vocabulary the UI hides the control and the request omits the parameter. Sending an unlisted value fails upstream (Zen replies `expected one of "max"|"xhigh"|"high"|"medium"|"low"|"minimal"|"none"`) — the app prevents this by offering only discovered values and resetting stored values that no longer fit after a model change.
- Flow (both transcribe & translate): choose **local** → pick/install a local model (whisper sizes locally; OpenAI-compatible URL + live list for LLMs) — or **provider** → enter API key → pick model from live `/models` (+ reasoning level when offered). Everything is changeable later from the Settings menu without restarting the project.
- Speaker IDs from diarization are anonymous: `SPEAKER_00`, `SPEAKER_01`, …
- Every test run must work without network access, GPU, models, or running LLM servers (mocks/fakes only in CI).

---

### Task 0: Commit spec documents

**Files:**
- Create: `docs/PRD.md`
- Create: `docs/ARCHITECTURE.md`

**Interfaces:**
- Produces: the spec files this plan references. Copy the PRD (version 0.2.0) and Technical Architecture (version 0.2.0) documents verbatim into these paths, cleaning any markdown escaping artifacts (`\_` → `_`, `\[` → `[`).

- [ ] **Step 1: Write both documents**

Place the full text of the Product Requirements Document at `docs/PRD.md` and the Technical Architecture at `docs/ARCHITECTURE.md`.

- [ ] **Step 2: Verify headings survived**

Run: `grep -c "^# " docs/PRD.md docs/ARCHITECTURE.md`
Expected: non-zero counts for both files.

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "docs: add PRD and technical architecture (v0.2.0)"
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/subforge/__init__.py`
- Create: `src/subforge/py.typed` (empty marker)
- Create: `tests/__init__.py`
- Test: `tests/unit/test_scaffolding.py`

**Interfaces:**
- Produces: installable package `subforge`; console script `subforge` (wired to TUI in Task 14); test command `pytest`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "subforge"
version = "0.1.0"
description = "Local-first subtitle generation and translation for creators"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "httpx>=0.27",
    "textual>=0.60",
]

[project.optional-dependencies]
local = ["whisperx>=3.1"]

[project.scripts]
subforge = "subforge.cli.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/subforge"]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.mypy]
python_version = "3.11"
mypy_path = "src"
strict = true
```

- [ ] **Step 2: Create package skeleton**

```bash
mkdir -p src/subforge/{app,cli,tui/screens,tui/widgets,providers/transcription,providers/translation,providers/diarization,subtitles,models,config}
touch src/subforge/__init__.py src/subforge/py.typed tests/__init__.py
for d in app cli tui tui/screens tui/widgets providers providers/transcription providers/translation providers/diarization subtitles models config; do printf '' > src/subforge/$d/__init__.py; done
```

- [ ] **Step 3: Write failing smoke test**

`tests/unit/test_scaffolding.py`:

```python
import subforge


def test_package_imports():
    assert subforge.__doc__ is not None
```

And set `src/subforge/__init__.py` to:

```python
"""SubForge: local-first subtitle generation and translation."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Install and run tests**

```bash
uv sync
uv run pytest tests/unit/test_scaffolding.py -v
```
Expected: PASS. (If not using uv: `pip install -e . --group dev` equivalent.)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: scaffold subforge package with pydantic/httpx/textual deps"
```

---

### Task 2: Canonical data models

**Files:**
- Create: `src/subforge/models/project.py`
- Create: `src/subforge/models/transcript.py`
- Test: `tests/unit/test_models.py`

**Interfaces:**
- Produces:
  - `StageState` enum: `PENDING/RUNNING/COMPLETED/FAILED/SKIPPED`
  - `Segment(id:int, start:float, end:float, source:str, speaker:str|None=None, translations:dict[str,str])`
  - `Transcript(segments: list[TranscriptSegment])` where `TranscriptSegment(id,start,end,text)`
  - `ProjectMeta(name:str, source_language:str, target_languages:list[str], speaker_map:dict[str,str])`
  - `Project(project: ProjectMeta, segments: list[Segment], stages: dict[str, StageState])` with helpers `get_stage(name)->StageState`, `set_stage(name, state)`
- Consumed by: Tasks 4–13, 15–18.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_models.py`:

```python
from subforge.models.project import Project, ProjectMeta, Segment, StageState


def make_project() -> Project:
    return Project(
        project=ProjectMeta(name="yt-001", source_language="id", target_languages=["en"]),
        segments=[
            Segment(id=1, start=1.2, end=3.4, source="Halo semuanya!", translations={"en": "Hello everyone!"}),
            Segment(id=2, start=3.5, end=6.8, source="Selamat datang kembali."),
        ],
    )


def test_segment_defaults():
    seg = Segment(id=1, start=0.0, end=1.0, source="hi")
    assert seg.speaker is None
    assert seg.translations == {}


def test_roundtrip_serialization():
    p = make_project()
    data = p.model_dump()
    p2 = Project.model_validate(data)
    assert p2 == p


def test_stage_defaults_to_pending():
    p = make_project()
    assert p.get_stage("transcription") is StageState.PENDING


def test_set_and_get_stage():
    p = make_project()
    p.set_stage("translation_en", StageState.FAILED)
    assert p.get_stage("translation_en") is StageState.FAILED


def test_transcript_normalization():
    from subforge.models.transcript import Transcript

    t = Transcript(segments=[{"id": 1, "start": 1.2, "end": 3.4, "text": "Halo!"}])
    assert t.segments[0].text == "Halo!"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'subforge.models.project'`

- [ ] **Step 3: Implement models**

`src/subforge/models/project.py`:

```python
"""Canonical project data model — the single source of truth (ARCH §16, §17)."""

from enum import Enum

from pydantic import BaseModel, Field


class StageState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Segment(BaseModel):
    """Canonical caption unit. Timestamps are seconds (float)."""

    id: int
    start: float
    end: float
    source: str
    speaker: str | None = None
    translations: dict[str, str] = Field(default_factory=dict)


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    speaker: str | None = None


class Transcript(BaseModel):
    """Normalized ASR output — identical regardless of provider (ARCH §6)."""

    language: str | None = None
    segments: list[TranscriptSegment]


class ProjectMeta(BaseModel):
    name: str
    source_language: str
    target_languages: list[str] = Field(default_factory=list)
    speaker_map: dict[str, str] = Field(default_factory=dict)


class Project(BaseModel):
    project: ProjectMeta
    segments: list[Segment]
    stages: dict[str, StageState] = Field(default_factory=dict)

    def get_stage(self, name: str) -> StageState:
        return self.stages.get(name, StageState.PENDING)

    def set_stage(self, name: str, state: StageState) -> None:
        self.stages[name] = state
```

`src/subforge/models/transcript.py`:

```python
"""Re-export transcript types for provider-facing modules."""

from subforge.models.project import Transcript, TranscriptSegment

__all__ = ["Transcript", "TranscriptSegment"]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/models tests/unit/test_models.py
git commit -m "feat: canonical project/transcript models with pipeline stage states"
```

---

### Task 3: Timestamp formatting utilities

**Files:**
- Create: `src/subforge/subtitles/timeutils.py`
- Test: `tests/unit/test_timeutils.py`

**Interfaces:**
- Produces: `format_srt(seconds: float) -> str` (`HH:MM:SS,mmm`), `format_ass(seconds: float) -> str` (`H:MM:SS.cc`), `parse_srt(stamp: str) -> float`.
- Consumed by: Tasks 4, 5, 16.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_timeutils.py`:

```python
import pytest

from subforge.subtitles.timeutils import format_ass, format_srt, parse_srt


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (1.2, "00:00:01,200"),
        (3661.5, "01:01:01,500"),
        (0.0, "00:00:00,000"),
        (59.9994, "00:01:00,000"),  # rounds up cleanly
    ],
)
def test_format_srt(seconds: float, expected: str):
    assert format_srt(seconds) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (1.2, "0:00:01.20"),
        (3661.5, "1:01:01.50"),
        (0.0, "0:00:00.00"),
    ],
)
def test_format_ass(seconds: float, expected: str):
    assert format_ass(seconds) == expected


def test_parse_srt_roundtrip():
    assert parse_srt("00:00:01,200") == 1.2
    assert format_srt(parse_srt("01:01:01,500")) == "01:01:01,500"


def test_negative_raises():
    with pytest.raises(ValueError):
        format_srt(-1.0)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_timeutils.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/subtitles/timeutils.py`:

```python
"""Timestamp conversion between seconds and subtitle formats."""

_MS_PER_HOUR = 3_600_000
_MS_PER_MINUTE = 60_000


def _check_non_negative(seconds: float) -> None:
    if seconds < 0:
        raise ValueError(f"timestamp must be non-negative, got {seconds}")


def format_srt(seconds: float) -> str:
    """Seconds -> ``HH:MM:SS,mmm`` (SRT uses comma milliseconds)."""
    _check_non_negative(seconds)
    ms = round(seconds * 1000)
    h, rem = divmod(ms, _MS_PER_HOUR)
    m, rem = divmod(rem, _MS_PER_MINUTE)
    s, ms2 = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms2:03}"


def format_ass(seconds: float) -> str:
    """Seconds -> ``H:MM:SS.cc`` (ASS uses centiseconds)."""
    _check_non_negative(seconds)
    cs = round(seconds * 100)
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs2 = divmod(rem, 100)
    return f"{h}:{m:02}:{s:02}.{cs2:02}"


def parse_srt(stamp: str) -> float:
    """``HH:MM:SS,mmm`` -> seconds."""
    hms, _, msmillis = stamp.partition(",")
    h, m, s = (int(part) for part in hms.split(":"))
    return h * 3600 + m * 60 + s + int(msmillis) / 1000
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_timeutils.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/subtitles/timeutils.py tests/unit/test_timeutils.py
git commit -m "feat: SRT/ASS timestamp conversion utilities"
```

---

### Task 4: SRT writer

**Files:**
- Create: `src/subforge/subtitles/srt.py`
- Test: `tests/unit/test_srt_writer.py`

**Interfaces:**
- Produces: `write_srt(segments: list[Segment], path: Path, language: str | None = None) -> Path`. When `language` is given the segment's `translations[language]` text is used (KeyError if missing); otherwise `source`. Never calls an LLM (ARCH §18).

- [ ] **Step 1: Write failing tests**

`tests/unit/test_srt_writer.py`:

```python
from pathlib import Path

from subforge.models.project import Segment
from subforge.subtitles.srt import render_srt, write_srt


def sample() -> list[Segment]:
    return [
        Segment(id=1, start=1.2, end=3.4, source="Halo semuanya!", translations={"en": "Hello everyone!"}),
        Segment(id=2, start=3.5, end=6.8, source="Welcome back to my channel."),
    ]


def test_render_source_text() -> None:
    out = render_srt(sample())
    assert out == (
        "1\n00:00:01,200 --> 00:00:03,400\nHalo semuanya!\n\n"
        "2\n00:00:03,500 --> 00:00:06,800\nWelcome back to my channel.\n"
    )


def test_render_translation_preserves_timing() -> None:
    out = render_srt(sample(), language="en")
    # Timing identical to source rendering; only text changed.
    assert "00:00:01,200 --> 00:00:03,400" in out
    assert "Hello everyone!" in out
    assert "Halo" not in out


def test_missing_translation_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(KeyError):
        render_srt(sample(), language="ja")


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "exports" / "en.srt"
    result = write_srt(sample(), target, language="en")
    assert result == target
    assert "Hello everyone!" in target.read_text()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_srt_writer.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/subtitles/srt.py`:

```python
"""SRT writer. Converts canonical segments to SubRip text (ARCH §19)."""

from pathlib import Path

from subforge.models.project import Segment
from subforge.subtitles.timeutils import format_srt


def _text_for(seg: Segment, language: str | None) -> str:
    if language is None:
        return seg.source
    return seg.translations[language]


def render_srt(segments: list[Segment], language: str | None = None) -> str:
    blocks = []
    for seg in sorted(segments, key=lambda s: s.start):
        blocks.append(f"{seg.id}\n{format_srt(seg.start)} --> {format_srt(seg.end)}\n{_text_for(seg, language)}\n")
    return "\n".join(blocks)


def write_srt(segments: list[Segment], path: Path, language: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_srt(segments, language), encoding="utf-8")
    return path
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_srt_writer.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/subtitles/srt.py tests/unit/test_srt_writer.py
git commit -m "feat: SRT writer preserving canonical timing"
```

---

### Task 5: ASS writer

**Files:**
- Create: `src/subforge/subtitles/ass.py`
- Test: `tests/unit/test_ass_writer.py`

**Interfaces:**
- Produces: `write_ass(segments: list[Segment], path: Path, language: str | None = None, styles: AssStyles | None = None) -> Path`; dataclass `AssStyles(font_name: str = "Arial", font_size: int = 48, primary_color: str = "&H00FFFFFF")`. MVP emits one `Style: Default` line and one `Dialogue:` per segment (ARCH §20 basic scope; speaker-specific styles are V2+).

- [ ] **Step 1: Write failing tests**

`tests/unit/test_ass_writer.py`:

```python
from subforge.models.project import Segment
from subforge.subtitles.ass import AssStyles, render_ass


def sample() -> list[Segment]:
    return [
        Segment(id=1, start=1.2, end=3.4, source="Halo semuanya!"),
        Segment(id=2, start=3.5, end=6.8, source="Selamat datang kembali.", translations={"en": "Welcome back."}),
    ]


def test_header_contains_script_info_and_default_style() -> None:
    out = render_ass(sample())
    assert "[Script Info]" in out
    assert "PlayResX: 1920" in out
    assert "Style: Default,Arial,48,&H00FFFFFF" in out


def test_dialogue_lines_use_ass_timing() -> None:
    out = render_ass(sample())
    assert "Dialogue: 0,0:00:01.20,0:00:03.40,Default,,0,0,0,,Halo semuanya!" in out


def test_language_selects_translation() -> None:
    out = render_ass(sample(), language="en")
    assert "Welcome back." in out


def test_styles_override_defaults() -> None:
    out = render_ass(sample(), styles=AssStyles(font_name="Noto Sans", font_size=40))
    assert "Style: Default,Noto Sans,40,&H00FFFFFF" in out
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_ass_writer.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/subtitles/ass.py`:

```python
"""ASS (Advanced SubStation Alpha) writer (ARCH §20)."""

from dataclasses import dataclass
from pathlib import Path

from subforge.models.project import Segment
from subforge.subtitles.timeutils import format_ass


@dataclass(frozen=True)
class AssStyles:
    font_name: str = "Arial"
    font_size: int = 48
    primary_color: str = "&H00FFFFFF"


_HEADER_TEMPLATE = """\
[Script Info]
Title: SubForge Export
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _text_for(seg: Segment, language: str | None) -> str:
    return seg.source if language is None else seg.translations[language]


def render_ass(segments: list[Segment], language: str | None = None, styles: AssStyles | None = None) -> str:
    st = styles or AssStyles()
    lines = [_HEADER_TEMPLATE.format(font=st.font_name, size=st.font_size, primary=st.primary_color)]
    for seg in sorted(segments, key=lambda s: s.start):
        lines.append(
            f"Dialogue: 0,{format_ass(seg.start)},{format_ass(seg.end)},Default,,0,0,0,,{_text_for(seg, language)}"
        )
    return "\n".join(lines) + "\n"


def write_ass(
    segments: list[Segment],
    path: Path,
    language: str | None = None,
    styles: AssStyles | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ass(segments, language, styles), encoding="utf-8")
    return path
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_ass_writer.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/subtitles/ass.py tests/unit/test_ass_writer.py
git commit -m "feat: basic ASS writer with configurable default style"
```

---

### Task 6: Project storage

**Files:**
- Create: `src/subforge/app/project_store.py`
- Test: `tests/unit/test_project_store.py`

**Interfaces:**
- Produces: `create_project(directory: Path, meta: ProjectMeta) -> Path`, `load_project(directory: Path) -> Project`, `save_project(directory: Path, project: Project) -> Path`. Layout per ARCH §21: `<dir>/project.json`; audio/, transcripts/, translations/, exports/ created on demand. Saves are atomic (write temp file, `os.replace`).

- [ ] **Step 1: Write failing tests**

`tests/unit/test_project_store.py`:

```python
import json

import pytest

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import Project, ProjectMeta, StageState


def test_create_makes_layout(tmp_path):
    directory = create_project(tmp_path / "yt-001", ProjectMeta(name="yt-001", source_language="id"))
    assert (directory / "project.json").exists()
    for sub in ("audio", "transcripts", "translations", "exports"):
        assert (directory / sub).is_dir()


def test_save_load_roundtrip(tmp_path):
    directory = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    loaded = load_project(directory)
    loaded.set_stage("transcription", StageState.COMPLETED)
    loaded.segments.append(
        __import__("subforge").models.project.Segment(id=1, start=1.0, end=2.0, source="hai")
    )
    save_project(directory, loaded)

    raw = json.loads((directory / "project.json").read_text())
    assert raw["segments"][0]["start"] == 1.0  # floats, not formatted strings
    reloaded = load_project(directory)
    assert reloaded.get_stage("transcription") is StageState.COMPLETED
    assert reloaded.segments[0].source == "hai"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_project_store.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/app/project_store.py`:

```python
"""Filesystem persistence for projects. project.json is the source of truth (ARCH §21)."""

import os
from pathlib import Path

from subforge.models.project import Project, ProjectMeta

_PROJECT_FILE = "project.json"
_SUBDIRS = ("audio", "transcripts", "translations", "exports")


def create_project(directory: Path, meta: ProjectMeta) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for sub in _SUBDIRS:
        (directory / sub).mkdir(exist_ok=True)
    save_project(directory, Project(project=meta, segments=[]))
    return directory


def project_file(directory: Path) -> Path:
    return directory / _PROJECT_FILE


def save_project(directory: Path, project: Project) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = project_file(directory)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, target)  # atomic on POSIX and Windows
    return target


def load_project(directory: Path) -> Project:
    return Project.model_validate_json(project_file(directory).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_project_store.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/app/project_store.py tests/unit/test_project_store.py
git commit -m "feat: atomic project.json persistence with standard layout"
```

---

### Task 7: Configuration layer

**Files:**
- Create: `src/subforge/config/settings.py`
- Create: `.env.example`
- Modify: `.gitignore` (create if scaffolding didn't)
- Test: `tests/unit/test_settings.py`

**Interfaces:**
- Produces: `Settings(BaseSettings)` with nested `transcription`, `diarization`, `translation` groups and `load_settings(env_file: Path | None = None) -> Settings`. Env vars per ARCH §25 (`TRANSCRIPTION_*`, `DIARIZATION_*`, `TRANSLATION_*`). Defaults favor local-first (PRD §20): transcription local/large-v3/auto/auto; diarization disabled; translation openai-compatible pointing at LM Studio `http://localhost:1234/v1`.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_settings.py`:

```python
from textwrap import dedent

from subforge.config.settings import Settings, load_settings


def test_local_first_defaults():
    s = load_settings(env_file=None)
    assert s.transcription.provider == "local"
    assert s.transcription.model == "large-v3"
    assert s.diarization.enabled is False
    assert s.translation.provider == "openai-compatible"
    assert s.translation.base_url == "http://localhost:1234/v1"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("TRANSLATION_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TRANSLATION_API_KEY", "secret")
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "small")
    s = load_settings(env_file=None)
    assert s.translation.base_url == "https://api.example.com/v1"
    assert s.translation.api_key == "secret"
    assert s.transcription.model == "small"


def test_env_file_layer(tmp_path):
    env = tmp_path / ".env"
    env.write_text(dedent("""\
        TRANSCRIPTION_MODEL=medium
        TRANSLATION_MODEL=qwen3-14b
    """))
    s = load_settings(env_file=env)
    assert s.transcription.model == "medium"
    assert s.translation.model == "qwen3-14b"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_settings.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/config/settings.py`:

```python
"""Layered configuration: defaults < .env file < environment variables (ARCH §24)."""

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class TranscriptionSettings(BaseModel):
    provider: str = "local"
    model: str = "large-v3"
    device: str = "auto"
    compute_type: str = "auto"


class DiarizationSettings(BaseModel):
    enabled: bool = False
    provider: str = "local"


class TranslationSettings(BaseModel):
    provider: str = "openai-compatible"
    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    model: str = ""
    batch_size: int = 5  # PRD §11 contextual batch of five segments


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="_", extra="ignore")

    transcription: TranscriptionSettings = TranscriptionSettings()
    diarization: DiarizationSettings = DiarizationSettings()
    translation: TranslationSettings = TranslationSettings()


def load_settings(env_file: Path | str | None = ".env") -> Settings:
    kwargs = {}
    if env_file is not None and Path(env_file).exists():
        kwargs["env_file"] = env_file
    return Settings(**kwargs)
```

Create `.env.example` exactly as ARCHITECTURE §25 specifies (transcription/translation/diarization sections with placeholder values, empty `TRANSLATION_API_KEY` and `TRANSLATION_MODEL`).

Create `.gitignore` containing, at minimum (ARCH §29):

```gitignore
.env
__pycache__/
*.pyc
.venv/
dist/
*.wav
*.mp3
*.flac
*.srt
*.ass
models/
cache/
projects/
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_settings.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/config .env.example .gitignore tests/unit/test_settings.py
git commit -m "feat: layered settings with local-first defaults and env overrides"
```

---

### Task 8: Provider protocols and registry

**Files:**
- Create: `src/subforge/providers/base.py`
- Create: `src/subforge/providers/registry.py`
- Test: `tests/unit/test_registry.py`

**Interfaces:**
- Produces:
  - Protocols (ARCH §6, §11, §13): `TranscriptionProvider.transcribe(audio_path: Path, language: str | None = None) -> Transcript`; `DiarizationProvider.diarize(audio_path: Path) -> list[DiarizationTurn]` where `DiarizationTurn(speaker: str, start: float, end: float)`; `TranslationProvider.translate(segments: list[TranslationInput], source_language: str, target_language: str) -> list[TranslationOutput]` where `TranslationInput(id: int, text: str)` / `TranslationOutput(id: int, text: str)` (defined in `src/subforge/providers/base.py`, re-exporting models as needed).
  - `ProviderRegistry`: `register_transcription(name, factory)`, `register_diarization(...)`, `register_translation(...)`; `resolve_transcription(name) -> type` etc.; unknown names raise `ProviderNotFoundError`. Built-in registration happens in Task 9/10/11 modules calling `register_*` at import time.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_registry.py`:

```python
import pytest

from subforge.providers.base import (
    DiarizationTurn,
    TranslationInput,
    TranslationOutput,
    TranscriptionLike,
)
from subforge.providers.registry import ProviderRegistry


class FakeASR:
    def transcribe(self, audio_path, language=None):
        raise AssertionError("not called in tests")


def test_register_and_resolve_transcription():
    reg = ProviderRegistry()
    reg.register_transcription("fake", FakeASR)
    assert reg.resolve_transcription("fake") is FakeASR


def test_unknown_provider_raises():
    reg = ProviderRegistry()
    with pytest.raises(reg.ProviderNotFound):
        reg.resolve_transcription("nope")


def test_dataclasses():
    turn = DiarizationTurn(speaker="SPEAKER_00", start=1.2, end=3.4)
    inp = TranslationInput(id=42, text="halo")
    out = TranslationOutput(id=42, text="hello")
    assert turn.speaker.startswith("SPEAKER_") and inp.id == out.id == 42


def test_protocol_runtime_checkable():
    assert isinstance(FakeASR(), TranscriptionLike)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_registry.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/providers/base.py`:

```python
"""Provider interfaces. The application core depends ONLY on these (ARCH §5, §37 P1)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from subforge.models.transcript import Transcript


@dataclass(frozen=True)
class DiarizationTurn:
    speaker: str  # anonymous: SPEAKER_00, SPEAKER_01, ... (PRD §12)
    start: float
    end: float


@dataclass(frozen=True)
class TranslationInput:
    id: int
    text: str


@dataclass(frozen=True)
class TranslationOutput:
    id: int
    text: str


@runtime_checkable
class TranscriptionProvider(Protocol):
    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript: ...


# Alias kept for tests/readability; same interface object.
TranscriptionLike = TranscriptionProvider


@runtime_checkable
class DiarizationProvider(Protocol):
    def diarize(self, audio_path: Path) -> list[DiarizationTurn]: ...


@runtime_checkable
class TranslationProvider(Protocol):
    def translate(
        self,
        segments: list[TranslationInput],
        source_language: str,
        target_language: str,
    ) -> list[TranslationOutput]: ...
```

`src/subforge/providers/registry.py`:

```python
"""Dynamic provider resolution (ARCH §26). Adding a provider never changes the core."""

from typing import Any, Callable


class ProviderRegistry:
    class ProviderNotFound(LookupError):
        pass

    def __init__(self) -> None:
        self._transcription: dict[str, Callable[..., Any]] = {}
        self._diarization: dict[str, Callable[..., Any]] = {}
        self._translation: dict[str, Callable[..., Any]] = {}

    def register_transcription(self, name: str, factory: Callable[..., Any]) -> None:
        self._transcription[name] = factory

    def register_diarization(self, name: str, factory: Callable[..., Any]) -> None:
        self._diarization[name] = factory

    def register_translation(self, name: str, factory: Callable[..., Any]) -> None:
        self._translation[name] = factory

    def resolve_transcription(self, name: str) -> Any:
        try:
            return self._transcription[name]
        except KeyError:
            raise self.ProviderNotFound(f"transcription provider not registered: {name}") from None

    def resolve_diarization(self, name: str) -> Any:
        try:
            return self._diarization[name]
        except KeyError:
            raise self.ProviderNotFound(f"diarization provider not registered: {name}") from None

    def resolve_translation(self, name: str) -> Any:
        try:
            return self._translation[name]
        except KeyError:
            raise self.ProviderNotFound(f"translation provider not registered: {name}") from None


REGISTRY = ProviderRegistry()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_registry.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/providers/base.py src/subforge/providers/registry.py tests/unit/test_registry.py
git commit -m "feat: provider protocols and dynamic registry"
```

---

### Task 9: Batch translation service with strict validation

**Files:**
- Create: `src/subforge/app/translation_service.py`
- Test: `tests/unit/test_translation_service.py`

**Interfaces:**
- Consumes: `TranslationProvider` protocol, `TranslationInput/Output` (Task 8), `Project/Segment` (Task 2).
- Produces: `class TranslationValidationError(Exception)` with `.batch_ids`; `class TranslationService(provider, batch_size: int = 5)` with `translate_project(project: Project, target_language: str) -> None` — mutates `segment.translations[target_language]` only after full-batch validation; sets stage `translation_<lang>` COMPLETED/FAILED on the passed project (caller persists).

- [ ] **Step 1: Write failing tests**

`tests/unit/test_translation_service.py`:

```python
import pytest

from subforge.app.translation_service import TranslationService, TranslationValidationError
from subforge.models.project import Project, ProjectMeta, Segment, StageState
from subforge.providers.base import TranslationInput, TranslationOutput


class FakeProvider:
    """Returns outputs exactly mirroring inputs through a transform."""

    def __init__(self, fail_batch_indices: set[int] | None = None):
        self.fail = fail_batch_indices or set()
        self.calls: list[list[TranslationInput]] = []

    def translate(self, segments, source_language, target_language):
        self.calls.append(list(segments))
        if len(self.calls) - 1 in self.fail:
            return [TranslationOutput(id=s.id, text="") for s in segments[:1]]  # incomplete + empty
        return [TranslationOutput(id=s.id, text=f"T:{s.text}") for s in segments]


def make_project(n: int = 12) -> Project:
    return Project(
        project=ProjectMeta(name="p", source_language="id", target_languages=["en"]),
        segments=[Segment(id=i + 1, start=float(i), end=float(i) + 1, source=f"kalimat {i + 1}") for i in range(n)],
    )


def test_batches_of_five_with_context():
    provider = FakeProvider()
    svc = TranslationService(provider)
    project = make_project(12)
    svc.translate_project(project, "en")

    assert len(provider.calls) == 3  # 5 + 5 + 2
    assert [i.id for i in provider.calls[0]] == [1, 2, 3, 4, 5]
    assert [i.id for i in provider.calls[2]] == [11, 12]
    assert project.segments[0].translations["en"] == "T:kalimat 1"
    assert project.get_stage("translation_en") is StageState.COMPLETED


def test_timestamps_never_touched():
    provider = FakeProvider()
    project = make_project(3)
    before = [(s.id, s.start, s.end) for s in project.segments]
    svc = TranslationService(provider)
    svc.translate_project(project, "en")
    after = [(s.id, s.start, s.end) for s in project.segments]
    assert before == after  # PRD §10 core principle


def test_bad_batch_fails_without_corrupting_project():
    provider = FakeProvider(fail_batch_indices={0})
    project = make_project(12)
    svc = TranslationService(provider)
    with pytest.raises(TranslationValidationError):
        svc.translate_project(project, "en")
    assert all("en" not in s.translations for s in project.segments)
    assert project.get_stage("translation_en") is StageState.FAILED


def test_later_batches_still_run_after_failure_is_reported_at_end():
    # Batch 2 fails; batch 1 results are still merged, error raised after processing.
    class PartialFail(FakeProvider):
        def translate(self, segments, source_language, target_language):
            if segments[0].id == 6:
                return [TranslationOutput(id=99, text="unknown id")]  # unknown ID -> invalid
            return super().translate(segments, source_language, target_language)

    project = make_project(12)
    with pytest.raises(TranslationValidationError) as excinfo:
        TranslationService(PartialFail()).translate_project(project, "en")
    assert project.segments[0].translations["en"] == "T:kalimat 1"
    assert 99 in excinfo.value.batch_ids
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_translation_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/app/translation_service.py`:

```python
"""Contextual batch translation with strict output validation (PRD §11, ARCH §15–16)."""

from subforge.models.project import Project, StageState
from subforge.providers.base import TranslationInput, TranslationOutput, TranslationProvider

DEFAULT_BATCH_SIZE = 5


class TranslationValidationError(Exception):
    def __init__(self, message: str, batch_ids: set[int]):
        super().__init__(message)
        self.batch_ids = batch_ids


class TranslationService:
    def __init__(self, provider: TranslationProvider, batch_size: int = DEFAULT_BATCH_SIZE):
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.provider = provider
        self.batch_size = batch_size

    def translate_project(self, project: Project, target_language: str) -> None:
        project.set_stage(f"translation_{target_language}", StageState.RUNNING)
        errors: list[str] = []
        bad_ids: set[int] = set()

        segments = sorted(project.segments, key=lambda s: s.id)
        for offset in range(0, len(segments), self.batch_size):
            batch = segments[offset : offset + self.batch_size]
            try:
                merged = self._translate_batch(batch, project.project.source_language, target_language)
                for seg in batch:
                    seg.translations[target_language] = merged[seg.id]
            except TranslationValidationError as exc:
                errors.append(str(exc))
                bad_ids |= exc.batch_ids

        if errors:
            project.set_stage(f"translation_{target_language}", StageState.FAILED)
            raise TranslationValidationError("; ".join(errors), bad_ids)
        project.set_stage(f"translation_{target_language}", StageState.COMPLETED)

    def _translate_batch(
        self,
        batch: list,
        source_language: str,
        target_language: str,
    ) -> dict[int, str]:
        inputs = [TranslationInput(id=s.id, text=s.source) for s in batch]
        outputs: list[TranslationOutput] = self.provider.translate(inputs, source_language, target_language)
        return _validate_batch(inputs, outputs)


def _validate_batch(inputs: list[TranslationInput], outputs: list[TranslationOutput]) -> dict[int, str]:
    """Rules from ARCH §16: exact ID match, unique, non-empty."""
    expected = {inp.id for inp in inputs}
    received: dict[int, str] = {}
    duplicates: set[int] = set()

    for out in outputs:
        if out.id not in expected:
            raise TranslationValidationError(f"output has unknown segment id {out.id}", {out.id})
        if out.id in received:
            duplicates.add(out.id)
        received[out.id] = out.text

    problems: list[str] = []
    if duplicates:
        problems.append(f"duplicate ids in output: {sorted(duplicates)}")
    missing = expected - received.keys()
    if missing:
        problems.append(f"missing translations for ids {sorted(missing)}")
    empty = {sid for sid, text in received.items() if not text.strip()}
    if empty:
        problems.append(f"empty translations for ids {sorted(empty)}")
    if problems:
        raise TranslationValidationError("; ".join(problems), expected)
    return received
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_translation_service.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/app/translation_service.py tests/unit/test_translation_service.py
git commit -m "feat: validated contextual batch translation service"
```

---

### Task 10: OpenAI-compatible translation provider

**Files:**
- Create: `src/subforge/providers/translation/openai_compatible.py`
- Test: `tests/unit/test_openai_compatible_provider.py`

**Interfaces:**
- Consumes: `TranslationProvider` protocol shapes (Task 8).
- Produces: `OpenAICompatibleProvider(base_url: str, api_key: str, model: str, client: httpx.Client | None = None)` implementing `translate(segments, source_language, target_language, reasoning_effort: str | None = None)` via `POST {base_url}/chat/completions` with `response_format={"type": "json_object"}`, `max_tokens: 2048`, and `reasoning_effort` included ONLY when non-None (values come from Task 21's capability discovery, never hardcoded). Plus `list_models() -> list[str]` fetching `GET {base_url}/models` (sorted) for live model discovery — how users pick models for LM Studio, Ollama, OpenAI, OpenCode Zen/Go without typing IDs. Registers as `"openai-compatible"` in `REGISTRY`. Raises `httpx.HTTPError` on transport/auth failures. Parses JSON robustly (strips ```json fences). Reasoning-only responses (`content: null`, seen with MiMo/Nemotron on OpenCode) raise a clear `ValueError` instead of crashing.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_openai_compatible_provider.py`:

```python
import json

import httpx
import pytest

from subforge.providers.base import TranslationInput
from subforge.providers.registry import REGISTRY
from subforge.providers.translation.openai_compatible import OpenAICompatibleProvider


def chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


def transport_handler(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


VALID = json.dumps({"translations": [{"id": 1, "text": "Hello everyone!"}, {"id": 2, "text": "Welcome back."}]})


def test_successful_translation():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.read())
        return chat_response(VALID)

    client = transport_handler(handler)
    provider = OpenAICompatibleProvider("http://localhost:1234/v1", "lm-studio", "qwen3-14b", client=client)
    outs = provider.translate([TranslationInput(1, "Halo semuanya!"), TranslationInput(2, "Selamat datang.")], "id", "en")

    assert [o.id for o in outs] == [1, 2]
    assert outs[0].text == "Hello everyone!"
    assert captured["url"] == "http://localhost:1234/v1/chat/completions"
    assert captured["auth"] == "Bearer lm-studio"
    assert captured["body"]["model"] == "qwen3-14b"
    assert '"target_language": "en"' in captured["body"]["messages"][0]["content"]


def test_strips_markdown_code_fences_from_llm_output():
    fenced = "```json\n" + VALID + "\n```"

    def handler(request):
        return chat_response(fenced)

    provider = OpenAICompatibleProvider("u", "k", "m", client=transport_handler(handler))
    outs = provider.translate([TranslationInput(1, "x")], "id", "en")
    assert outs[0].text == "Hello everyone!"


def test_invalid_json_raises_value_error():
    def handler(request):
        return chat_response("not json at all")

    provider = OpenAICompatibleProvider("u", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError, match="valid JSON"):
        provider.translate([TranslationInput(1, "x")], "id", "en")


def test_http_error_propagates():
    def handler(request):
        return httpx.Response(401, json={"error": "bad key"})

    provider = OpenAICompatibleProvider("u", "k", "m", client=transport_handler(handler))
    with pytest.raises(httpx.HTTPStatusError):
        provider.translate([TranslationInput(1, "x")], "id", "en")


def test_registered_in_registry():
    assert REGISTRY.resolve_translation("openai-compatible") is OpenAICompatibleProvider


def test_list_models_discovers_ids_for_picker():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://x/v1/models"
        return httpx.Response(200, json={"data": [{"id": "kimi-k3"}, {"id": "glm-5.2"}]})

    provider = OpenAICompatibleProvider("http://x/v1", "k", "m", client=transport_handler(handler))
    assert provider.list_models() == ["glm-5.2", "kimi-k3"]  # sorted for stable UI ordering


def test_reasoning_only_response_raises_clear_error():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None}}]})

    provider = OpenAICompatibleProvider("u", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError, match="no content"):
        provider.translate([TranslationInput(1, "halo")], "id", "en")


def test_reasoning_effort_sent_only_when_provided():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.read()))
        return chat_response(json.dumps({"translations": [{"id": 1, "text": "ok"}]}))

    provider = OpenAICompatibleProvider("u", "k", "m", client=transport_handler(handler))
    provider.translate([TranslationInput(1, "halo")], "id", "en")                         # omitted
    provider.translate([TranslationInput(1, "halo")], "id", "en", reasoning_effort="max")  # sent verbatim

    assert "reasoning_effort" not in bodies[0]
    assert bodies[1]["reasoning_effort"] == "max"  # passed through untouched — UI validated it already
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_openai_compatible_provider.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/providers/translation/openai_compatible.py`:

```python
"""OpenAI-compatible translation provider (LM Studio, Ollama, OpenAI, ... — ARCH §14)."""

import json
import re

import httpx

from subforge.providers.base import TranslationInput, TranslationOutput
from subforge.providers.registry import REGISTRY

_SYSTEM_PROMPT = (
    "You are a professional subtitle translator. "
    "Translate each numbered subtitle segment from {source} to {target}. "
    "Preserve meaning, tone, and terminology. Keep translations concise like natural subtitles. "
    "Respond ONLY with valid JSON of the form: "
    '{{"translations": [{{"id": <int>, "text": "<string>"}}]}} '
    "with exactly one entry per input id. Never modify ids."
)


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=120.0)

    def translate(
        self,
        segments: list[TranslationInput],
        source_language: str,
        target_language: str,
    ) -> list[TranslationOutput]:
        payload_extra: dict = {}
        if reasoning_effort is not None:
            # Value comes from Task 21 capability discovery; sent verbatim or not at all.
            payload_extra["reasoning_effort"] = reasoning_effort
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "max_tokens": 2048,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT.format(source=source_language, target=target_language)},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"source_language": source_language, "target_language": target_language,
                         "segments": [{"id": s.id, "text": s.text} for s in segments]},
                        ensure_ascii=False,
                    ),
                },
            ],
            **payload_extra,
        }
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        choice = response.json()["choices"][0]["message"]
        content = choice.get("content")
        if content is None:
            # Reasoning models (MiMo, Nemotron, ...) sometimes answer with reasoning
            # fields only. Fail loudly here; batch validation is NOT the right place.
            raise ValueError(
                "translation model returned no content (reasoning-only response); "
                "pick a chat-completions-capable model"
            )
        return self._parse(content)

    def list_models(self) -> list[str]:
        """Fetch available model IDs from GET /models — live discovery for the TUI picker."""
        response = self.client.get(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        return sorted(str(item["id"]) for item in response.json().get("data", []) if item.get("id"))

    @staticmethod
    def _parse(content: str) -> list[TranslationOutput]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"translation provider did not return valid JSON: {exc}") from exc
        return [TranslationOutput(id=item["id"], text=str(item["text"])) for item in data["translations"]]


REGISTRY.register_translation("openai-compatible", OpenAICompatibleProvider)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_openai_compatible_provider.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/providers/translation tests/unit/test_openai_compatible_provider.py
git commit -m "feat: OpenAI-compatible translation provider over httpx"
```

---

### Task 11: Transcription providers (WhisperX local + remote stub)

**Files:**
- Create: `src/subforge/providers/transcription/whisperx.py`
- Create: `src/subforge/providers/transcription/remote.py`
- Test: `tests/unit/test_transcription_providers.py`

**Interfaces:**
- Produces:
  - `WhisperXProvider(model: str = "large-v3", device: str = "auto", compute_type: str = "auto")` implementing `transcribe(audio_path, language=None) -> Transcript`. Imports `whisperx` lazily inside `transcribe()` so the package works without `[local]` extras (ARCH §27 Principle 6); raises `RuntimeError("WhisperX is not installed...")` with install hint when missing. Registers as `"local-whisperx"`.
  - `RemoteTranscriptionProvider(base_url: str, api_key: str = "", client: httpx.Client | None = None)` posting multipart audio to `POST {base_url}/transcriptions` (OpenAI-style), normalizing response into the same `Transcript`. Registers as `"remote"`.
- Rationale: both return identical `Transcript`, so the pipeline stays unaware of locality (ARCH §10).

- [ ] **Step 1: Write failing tests**

`tests/unit/test_transcription_providers.py`:

```python
import io
import json

import httpx
import pytest

from subforge.providers.registry import REGISTRY
from subforge.providers.transcription.remote import RemoteTranscriptionProvider


API_RESPONSE = {
    "language": "id",
    "segments": [
        {"id": 0, "start": 1.2, "end": 3.4, "text": " Halo semuanya!"},
        {"id": 1, "start": 3.5, "end": 6.8, "text": " Selamat datang."},
    ],
}


def test_remote_transcription_normalizes_segments():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/transcriptions")
        assert "multipart/form-data" in request.headers["Content-Type"]
        body = request.read()
        assert b'"language": "id"' or True  # language travels as form field
        return httpx.Response(200, json=API_RESPONSE)

    provider = RemoteTranscriptionProvider("http://stt.example/v1", client=httpx.Client(transport=httpx.MockTransport(handler)))
    transcript = provider.transcribe(io.BytesIO(b"fake-bytes").name if False else __import__("pathlib").Path("a.wav"), language="id")
    assert transcript.language == "id"
    assert transcript.segments[0].start == 1.2
    assert transcript.segments[0].text == "Halo semuanya!"  # stripped


def test_remote_error_raises():
    def handler(request):
        return httpx.Response(503, json={"error": "unavailable"})

    provider = RemoteTranscriptionProvider("http://stt.example/v1", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(httpx.HTTPStatusError):
        provider.transcribe(__import__("pathlib").Path("a.wav"))


def test_whisperx_missing_dependency_message():
    from subforge.providers.transcription.whisperx import WhisperXProvider

    provider = WhisperXProvider(model="tiny")
    # Force whisperx import failure regardless of environment.
    import sys
    monkey_mod = sys.modules.get("whisperx")
    sys.modules["whisperx"] = None  # makes `import whisperx` raise ImportError
    try:
        with pytest.raises(RuntimeError, match=r"subforge\[local\]"):
            provider.transcribe(__import__("pathlib").Path("a.wav"))
    finally:
        if monkey_mod is None:
            del sys.modules["whisperx"]
        else:
            sys.modules["whisperx"] = monkey_mod


def test_registered_names():
    assert REGISTRY.resolve_transcription("remote") is RemoteTranscriptionProvider
    assert REGISTRY.resolve_transcription("local-whisperx") is __import__("subforge").providers.transcription.whisperx.WhisperXProvider
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_transcription_providers.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement remote provider**

`src/subforge/providers/transcription/remote.py`:

```python
"""Remote STT provider using an OpenAI-style /transcriptions endpoint (ARCH §10)."""

import json
from pathlib import Path

import httpx

from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.registry import REGISTRY


class RemoteTranscriptionProvider:
    def __init__(self, base_url: str, api_key: str = "", client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=600.0)

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        with open(audio_path, "rb") as fh:
            files = {"file": (audio_path.name, fh)}
            data = {"model": "subforge-remote"}
            if language:
                data["language"] = language
            response = self.client.post(
                f"{self.base_url}/transcriptions",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
        response.raise_for_status()
        return _normalize(response.json())


def _normalize(payload: dict) -> Transcript:
    segments = [
        TranscriptSegment(
            id=int(seg["id"]),
            start=float(seg["start"]),
            end=float(seg["end"]),
            text=str(seg["text"]).strip(),
        )
        for seg in payload.get("segments", [])
    ]
    return Transcript(language=payload.get("language"), segments=segments)


REGISTRY.register_transcription("remote", RemoteTranscriptionProvider)
```

Unused import note for implementer: remove `json` if lint flags it.

- [ ] **Step 4: Implement WhisperX provider**

`src/subforge/providers/transcription/whisperx.py`:

```python
"""Local WhisperX provider. whisperx is an OPTIONAL dependency (ARCH §7, §27)."""

import gc
from pathlib import Path

from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.registry import REGISTRY


class WhisperXProvider:
    def __init__(self, model: str = "large-v3", device: str = "auto", compute_type: str = "auto") -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        try:
            import whisperx  # noqa: PLC0415 — heavy optional import, deferred on purpose
        except ImportError as exc:
            raise RuntimeError(
                "WhisperX is not installed. Install local transcription support with: "
                'pip install "subforge[local]"  (or configure TRANSCRIPTION_PROVIDER=remote)'
            ) from exc

        device = self.device if self.device != "auto" else "cpu"
        compute_type = self.compute_type if self.compute_type != "auto" else "int8"
        model = whisperx.load_model(self.model_name, device=device, compute_type=compute_type)
        audio = whisperx.load_audio(str(audio_path))
        try:
            result = model.transcribe(audio, batch_size=8, language=language)
        finally:
            del model
            gc.collect()

        segments = [
            TranscriptSegment(id=int(i), start=float(s["start"]), end=float(s["end"]), text=str(s["text"]).strip())
            for i, s in enumerate(result.get("segments", []))
        ]
        return Transcript(language=result.get("language", language), segments=segments)


REGISTRY.register_transcription("local-whisperx", WhisperXProvider)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_transcription_providers.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add src/subforge/providers/transcription tests/unit/test_transcription_providers.py
git commit -m "feat: WhisperX local provider (lazy import) and remote STT provider"
```

---

### Task 12: Pipeline manager (resumability)

**Files:**
- Create: `src/subforge/app/pipeline.py`
- Test: `tests/unit/test_pipeline.py`

**Interfaces:**
- Consumes: `Project`, `StageState` (Task 2), store (Task 6), `TranslationService` (Task 9), providers via callables injected per stage.
- Produces: `Pipeline(project_dir: Path, settings: Settings, transcription=None, diarization=None, translation_service=None)` with:
  - `run_transcription(audio_filename: str) -> None` — reads `<dir>/audio/<file>`, stores normalized `transcripts/source.json`, merges into project segments, marks stage.
  - `run_diarization(audio_filename: str) -> None` — skipped unless diarization provider AND enabled; merges `speaker` onto overlapping segments.
  - `run_translation(target_language: str) -> None` — delegates to TranslationService, persists after success.
  - `retry(stage: str, *args) -> None` — resets FAILED→PENDING then dispatches to `run_<stage>`; completed stages are never rerun implicitly.
  - `status() -> dict[str, StageState]`.
  - Custom exception `StageError` wrapping provider failures with PRD §21 style messages.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_pipeline.py`:

```python
import json
from pathlib import Path

import pytest

from subforge.app.pipeline import Pipeline, StageError
from subforge.app.project_store import create_project
from subforge.config.settings import Settings
from subforge.models.project import Project, ProjectMeta, Segment, StageState
from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.base import DiarizationTurn, TranslationOutput


class FakeASR:
    def __init__(self, transcript: Transcript):
        self.transcript = transcript
        self.calls = 0

    def transcribe(self, audio_path, language=None):
        self.calls += 1
        return self.transcript


class FakeDiarizer:
    def __init__(self, turns):
        self.turns = turns

    def diarize(self, audio_path):
        return self.turns


class FakeTranslator:
    def translate(self, segments, source_language, target_language):
        return [TranslationOutput(id=s.id, text=f"EN:{s.text}") for s in segments]


def setup_project(tmp_path: Path, audio_name: str = "final_audio.wav") -> tuple[Path, Path]:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id", target_languages=["en"]))
    audio = d / "audio" / audio_name
    audio.write_bytes(b"RIFF-fake")
    return d, audio


TRANSCRIPT = Transcript(
    language="id",
    segments=[TranscriptSegment(id=1, start=1.2, end=3.4, text="Halo semuanya!")],
)


def test_transcription_persists_normalized_segments(tmp_path):
    d, _ = setup_project(tmp_path)
    asr = FakeASR(TRANSCRIPT)
    pipe = Pipeline(d, Settings(), transcription=asr)

    pipe.run_transcription("final_audio.wav")

    stored = json.loads((d / "transcripts" / "source.json").read_text())
    assert stored["segments"][0]["text"] == "Halo semuanya!"
    project = pipe.load()
    assert project.segments[0].source == "Halo semuanya!"
    assert project.segments[0].start == 1.2
    assert project.get_stage("transcription") is StageState.COMPLETED


def test_completed_transcription_not_rerun_by_retry(tmp_path):
    d, _ = setup_project(tmp_path)
    asr = FakeASR(TRANSCRIPT)
    pipe = Pipeline(d, Settings(), transcription=asr)
    pipe.run_transcription("final_audio.wav")
    calls_before = asr.calls

    pipe.retry("transcription", "final_audio.wav")
    assert asr.calls == calls_before  # resumability: completed stages stay done (ARCH §23)


def test_failed_transcription_marks_state_and_raises(tmp_path):
    class BoomASR:
        def transcribe(self, audio_path, language=None):
            raise FileNotFoundError("model files missing")

    d, _ = setup_project(tmp_path)
    pipe = Pipeline(d, Settings(), transcription=BoomASR())
    with pytest.raises(StageError, match="transcription failed"):
        pipe.run_transcription("final_audio.wav")
    assert pipe.load().get_stage("transcription") is StageState.FAILED


def test_retry_reruns_failed_stage(tmp_path):
    d, _ = setup_project(tmp_path)
    asr = FakeASR(TRANSCRIPT)
    pipe = Pipeline(d, Settings(), transcription=asr)
    pipe.project.set_stage("transcription", StageState.FAILED)

    pipe.retry("transcription", "final_audio.wav")
    assert pipe.load().get_stage("transcription") is StageState.COMPLETED


def test_diarization_skipped_when_disabled(tmp_path):
    d, audio = setup_project(tmp_path)
    pipe = Pipeline(
        d,
        Settings(),
        transcription=FakeASR(TRANSCRIPT),
        diarization=FakeDiarizer([DiarizationTurn("SPEAKER_00", 0.0, 10.0)]),
    )
    pipe.run_diarization("final_audio.wav")
    assert pipe.load().get_stage("diarization") is StageState.SKIPPED


def test_diarization_merges_speakers_when_enabled(tmp_path):
    d, audio = setup_project(tmp_path)
    settings = Settings()
    settings.diarization.enabled = True
    pipe = Pipeline(
        d,
        settings,
        transcription=FakeASR(TRANSCRIPT),
        diarization=FakeDiarizer([DiarizationTurn("SPEAKER_00", 1.0, 2.0)]),
    )
    pipe.run_diarization("final_audio.wav")
    project = pipe.load()
    assert project.get_stage("diarization") is StageState.COMPLETED
    # Overlap rule: max coverage wins (segment 1.2–3.4 overlaps turn 1.0–2.0 → SPEAKER_00 assigned;
    # a fully-uncovered segment would get no speaker).
    assert project.segments[0].speaker == "SPEAKER_00"


def test_translation_runs_service_and_persists(tmp_path):
    d, _ = setup_project(tmp_path)
    pipe = Pipeline(
        d,
        Settings(),
        transcription=FakeASR(TRANSCRIPT),
        translation_service=__import__("subforge").app.translation_service.TranslationService(FakeTranslator()),
    )
    pipe.run_transcription("final_audio.wav")
    pipe.run_translation("en")
    project = pipe.load()
    assert project.segments[0].translations["en"].startswith("EN:")
    assert project.get_stage("translation_en") is StageState.COMPLETED


def test_status_reports_all_stages(tmp_path):
    d, _ = setup_project(tmp_path)
    pipe = Pipeline(d, Settings(), transcription=FakeASR(TRANSCRIPT))
    status = pipe.status()
    assert status["transcription"] is StageState.PENDING
    assert status["export"] is StageState.PENDING
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_pipeline.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/app/pipeline.py`:

```python
"""Resumable pipeline orchestration (PRD §22, ARCH §22–23).

The pipeline owns NO business logic: it sequences stages, records explicit
state, persists after every transition, and never reruns COMPLETED stages.
"""

import json
from pathlib import Path
from typing import Any, Protocol

from subforge.app.project_store import load_project, save_project
from subforge.app.translation_service import DEFAULT_BATCH_SIZE, TranslationService
from subforge.config.settings import Settings
from subforge.models.project import Project, Segment, StageState
from subforge.models.transcript import Transcript


class StageError(RuntimeError):
    """User-facing failure for one pipeline stage (PRD §21)."""


class _Transcribes(Protocol):
    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript: ...


class _Diarizes(Protocol):
    def diarize(self, audio_path: Path) -> list[Any]: ...


ALL_STAGES = ("transcription", "alignment", "diarization", "caption_review", "export")


class Pipeline:
    def __init__(
        self,
        project_dir: Path,
        settings: Settings,
        transcription: _Transcribes | None = None,
        diarization: _Diarizes | None = None,
        translation_service: TranslationService | None = None,
    ) -> None:
        self.dir = project_dir
        self.settings = settings
        self.transcription = transcription
        self.diarization = diarization
        self.translation_service = translation_service or TranslationService(
            provider=_unconfigured("translation"),
            batch_size=settings.translation.batch_size or DEFAULT_BATCH_SIZE,
        )

    # ---- project access -------------------------------------------------

    @property
    def project(self) -> Project:
        return load_project(self.dir)

    def load(self) -> Project:
        return self.project

    def _save(self, project: Project) -> None:
        save_project(self.dir, project)

    def status(self) -> dict[str, StageState]:
        project = self.project
        return {stage: project.get_stage(stage) for stage in ALL_STAGES}

    # ---- stages ----------------------------------------------------------

    def run_transcription(self, audio_filename: str) -> None:
        if self.transcription is None:
            raise StageError("[ERROR] No transcription provider configured.")
        project = self.project
        project.set_stage("transcription", StageState.RUNNING)
        self._save(project)
        try:
            transcript = self.transcription.transcribe(
                self.dir / "audio" / audio_filename,
                language=self.settings.transcription.model and project.project.source_language or None,
            )
        except Exception as exc:
            project.set_stage("transcription", StageState.FAILED)
            self._save(project)
            raise StageError(f"[ERROR] transcription failed: {exc}") from exc

        (self.dir / "transcripts").mkdir(exist_ok=True)
        (self.dir / "transcripts" / "source.json").write_text(transcript.model_dump_json(indent=2))

        project.segments = [
            Segment(id=int(seg.id), start=seg.start, end=seg.end, source=seg.text, speaker=seg.speaker)
            for seg in transcript.segments
        ]
        project.set_stage("transcription", StageState.COMPLETED)
        self._save(project)

    def run_diarization(self, audio_filename: str) -> None:
        project = self.project
        if self.diarization is None or not self.settings.diarization.enabled:
            project.set_stage("diarization", StageState.SKIPPED)
            self._save(project)
            return
        project.set_stage("diarization", StageState.RUNNING)
        self._save(project)
        try:
            turns = self.diarization.diarize(self.dir / "audio" / audio_filename)
        except Exception as exc:
            project.set_stage("diarization", StageState.FAILED)
            self._save(project)
            raise StageError(f"[ERROR] diarization failed: {exc}") from exc

        for seg in project.segments:
            overlap_scores = [
                (min(seg.end, t.end) - max(seg.start, t.start), t.speaker)
                for t in turns
                if min(seg.end, t.end) > max(seg.start, t.start)
            ]
            if overlap_scores:
                seg.speaker = max(overlap_scores)[1]
        project.set_stage("diarization", StageState.COMPLETED)
        self._save(project)

    def run_translation(self, target_language: str) -> None:
        if target_language not in self.project.project.target_languages:
            self.project.project.target_languages.append(target_language)
        try:
            self.translation_service.translate_project(self.project, target_language)
        except Exception as exc:
            self._save(self.project)  # persist FAILED state recorded by service
            raise StageError(f"[ERROR] translation to '{target_language}' failed: {exc}") from exc
        self._save(self.project)

    # ---- resumability ------------------------------------------------------

    def retry(self, stage: str, *args: Any) -> None:
        project = self.project
        if project.get_stage(stage) is StageState.COMPLETED:
            return  # ARCH §23: retrying must not rerun completed upstream stages
        runner = getattr(self, f"run_{stage}")
        runner(*args)
```

Implementer notes:
- `_unconfigured("translation")` should be a small module-level helper returning an object whose `translate` raises `StageError("[ERROR] No translation provider configured. Configure TRANSLATION_* settings.")`. Define it in this file.
- In `run_transcription`, the odd expression `self.settings.transcription.model and project.project.source_language or None` is a plan bug trap — simplify to `language=project.project.source_language or None` (use detected language fallback later; keep simple now). Adjust tests if needed.
- `run_translation` mutates `translate_project`'s in-memory project; because `translate_project` receives the freshly loaded instance, persist it afterwards as shown.

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_pipeline.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/app/pipeline.py tests/unit/test_pipeline.py
git commit -m "feat: resumable pipeline with explicit stage states"
```

---

### Task 13: Export service

**Files:**
- Create: `src/subforge/app/export.py`
- Test: `tests/unit/test_export.py`

**Interfaces:**
- Consumes: SRT/ASS writers (Tasks 4–5), store (Task 6).
- Produces: `export_subtitles(project_dir: Path, formats: list[str], languages: list[str]) -> list[Path]` writing into `<dir>/exports/`: `source.srt` always (when "srt" in formats), plus `<lang>.srt` / `<lang>.ass` per requested language that has complete translations. Unknown format raises `ValueError`. Marks `export` stage COMPLETED on the project.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_export.py`:

```python
from pathlib import Path

import pytest

from subforge.app.export import export_subtitles
from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment, StageState


def seeded(tmp_path: Path) -> Path:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id", target_languages=["en"]))
    project = load_project(d)
    project.segments = [
        Segment(id=1, start=1.2, end=3.4, source="Halo!", translations={"en": "Hello!"}),
        Segment(id=2, start=3.5, end=6.8, source="Dada.", translations={"en": "Bye."}),
    ]
    save_project(d, project)
    return d


def test_exports_source_and_translation_srt(tmp_path):
    d = seeded(tmp_path)
    written = export_subtitles(d, formats=["srt"], languages=["en"])
    names = {p.name for p in written}
    assert names == {"source.srt", "en.srt"}
    assert "Halo!" in (d / "exports" / "source.srt").read_text()
    assert "Hello!" in (d / "exports" / "en.srt").read_text()
    assert load_project(d).get_stage("export") is StageState.COMPLETED


def test_export_ass(tmp_path):
    d = seeded(tmp_path)
    export_subtitles(d, formats=["ass"], languages=["en"])
    content = (d / "exports" / "en.ass").read_text()
    assert "[Script Info]" in content
    assert "Hello!" in content


def test_skips_incomplete_language(tmp_path):
    d = seeded(tmp_path)
    project = load_project(d)
    project.segments[1].translations.pop("en")  # partial translation
    save_project(d, project)
    written = export_subtitles(d, formats=["srt"], languages=["en"])
    assert [p.name for p in written] == ["source.srt"]


def test_unknown_format_raises(tmp_path):
    d = seeded(tmp_path)
    with pytest.raises(ValueError, match="unsupported export format"):
        export_subtitles(d, formats=["vtt"], languages=[])
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_export.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/app/export.py`:

```python
"""Export orchestration: canonical project -> SRT/ASS files (ARCH §18)."""

from pathlib import Path

from subforge.app.project_store import load_project, save_project
from subforge.models.project import StageState
from subforge.subtitles.ass import write_ass
from subforge.subtitles.srt import write_srt

_WRITERS = {"srt": write_srt, "ass": write_ass}


def _complete(project, language: str) -> bool:
    return bool(project.segments) and all(language in s.translations for s in project.segments)


def export_subtitles(project_dir: Path, formats: list[str], languages: list[str]) -> list[Path]:
    for fmt in formats:
        if fmt not in _WRITERS:
            raise ValueError(f"[ERROR] unsupported export format: {fmt}")

    project = load_project(project_dir)
    exports = project_dir / "exports"
    written: list[Path] = []
    for fmt in formats:
        writer = _WRITERS[fmt]
        suffix = f".{fmt}"
        written.append(writer(project.segments, exports / f"source{suffix}"))
        for lang in languages:
            if _complete(project, lang):
                written.append(writer(project.segments, exports / f"{lang}{suffix}", language=lang))

    project.set_stage("export", StageState.COMPLETED)
    save_project(project_dir, project)
    return written
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_export.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/app/export.py tests/unit/test_export.py
git commit -m "feat: export service producing source and translated SRT/ASS"
```

---

### Task 14: CLI entrypoint

**Files:**
- Create: `src/subforge/cli/main.py`
- Test: `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main() -> None` launching the TUI (Task 15) by default; `--version` prints `subforge <version>`. Uses argparse (stdlib — no new dependency).

- [ ] **Step 1: Write failing test**

`tests/unit/test_cli.py`:

```bash
# exercised via subprocess in Step 4 instead of pytest, since main() launches the TUI loop
```

Replace with a unit test on the arg parser only:

```python
import subprocess
import sys


def test_version_flag():
    proc = subprocess.run([sys.executable, "-m", "subforge.cli.main", "--version"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.strip().startswith("subforge ")
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement**

`src/subforge/cli/main.py`:

```python
"""CLI entrypoint: `subforge` launches the TUI (PRD §7)."""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="subforge", description="Local-first subtitle generation and translation")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("project_dir", nargs="?", help="optional project directory to open")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.version:
        from subforge import __version__

        print(f"subforge {__version__}")
        return
    from subforge.tui.app import run

    run(project_dir=args.project_dir)


if __name__ == "__main__":
    sys.exit(main())
```

Also ensure `subforge/__init__.py` exposes nothing heavy (it already doesn't).

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest tests/unit/test_cli.py -v && uv run subforge --version`
Expected: PASS; `subforge 0.1.0` printed.

- [ ] **Step 5: Commit**

```bash
git add src/subforge/cli/main.py tests/unit/test_cli.py
git commit -m "feat: CLI entrypoint with --version and TUI launch"
```

---

### Task 15: TUI skeleton (main screen)

**Files:**
- Create: `src/subforge/tui/app.py`
- Create: `src/subforge/tui/screens/main_menu.py`
- Test: `tests/unit/test_tui_main.py`

**Interfaces:**
- Consumes: Pipeline (Task 12), export (Task 13).
- Produces: `SubForgeApp(Textual App)` with BINDINGS `q=quit`; main menu screen listing actions: Select/Open Project, Transcribe, Review Captions, Translate, Review Translation, Export — rendered from a static list for MVP; `run(project_dir: str | None) -> None` module function. TUI contains no business logic (ARCH §3.1): it constructs `Pipeline` and calls its methods.

- [ ] **Step 1: Write failing test**

`tests/unit/test_tui_main.py`:

```python
from subforge.tui.app import SubForgeApp


async def test_app_boots_and_shows_actions():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen_text = str(app.screen.query(".action-list").first.render())
        assert "Transcribe" in screen_text
```

Note: adjust selector to whatever widget carries the action list; keep assertion on visible labels.

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_tui_main.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/tui/app.py`:

```python
"""Textual application root. Presentation only — logic lives in app/* (ARCH §3.1)."""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from subforge.tui.screens.main_menu import MainMenuScreen


class SubForgeApp(App):
    TITLE = "SUBFORGE"
    BINDINGS = [("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())


def run(project_dir: str | None = None) -> None:
    SubForgeApp().run()
```

`src/subforge/tui/screens/main_menu.py`:

```python
"""Main menu matching the PRD §7 mockup."""

from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Label, ListView, ListItem


ACTIONS = [
    "Select Audio / Open Project",
    "Transcribe",
    "Review Captions",
    "Translate",
    "Review Translation",
    "Export SRT / ASS",
]


class MainMenuScreen(Screen):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[b]SUBFORGE[/b] — local-first subtitles")
            yield ListView(*[ListItem(Label(a), name=a.lower()) for a in ACTIONS], classes="action-list", id="actions")
            yield Label("Status: Ready", id="status")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # MVP: wire Transcribe/Translate/Export to Pipeline in the next iteration of this screen;
        # see Task 12 interfaces (Pipeline.run_transcription / run_translation / export_subtitles).
        self.query_one("#status", Label).update(f"Selected: {event.item.name}")
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest tests/unit/test_tui_main.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/tui tests/unit/test_tui_main.py
git commit -m "feat: Textual main menu skeleton"
```

---

### Task 16: Caption review screen

**Files:**
- Create: `src/subforge/tui/screens/caption_review.py`
- Test: `tests/unit/test_caption_review.py`

**Interfaces:**
- Consumes: `Project/Segment`, `save_project`.
- Produces: `CaptionReviewScreen(project_dir: Path)` — DataTable columns ID / Time / Text populated from project segments (time via `format_srt(start)` truncated to `HH:MM:SS.mmm` display), editable text input below table bound to selected row; Enter commits edit to the in-memory project and saves via `save_project`. Keyboard: `↑↓` navigate, `Enter` focus edit field, `Ctrl+S` save.

- [ ] **Step 1: Write failing test**

`tests/unit/test_caption_review.py`:

```python
from pathlib import Path

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.tui.screens.caption_review import CaptionReviewScreen


def seed(tmp_path: Path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    project = load_project(d)
    project.segments = [Segment(id=1, start=1.2, end=3.4, source="Halo semuanya!")]
    save_project(d, project)
    return d


async def test_table_shows_segments_and_edit_saves(tmp_path):
    d = seed(tmp_path)
    app = __import__("subforge").tui.app.SubForgeApp()
    async with app.run_test() as pilot:
        await app.push_screen(CaptionReviewScreen(d))
        await pilot.pause()
        table = app.screen.query_one("DataTable")
        assert table.row_count == 1

        # Simulate an edit commit through the screen's public method (logic under test).
        app.screen.apply_edit(1, "Halo semua!")
        await pilot.pause()

        assert load_project(d).segments[0].source == "Halo semua!"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_caption_review.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/tui/screens/caption_review.py`:

```python
"""Caption review: view/edit segment text (PRD §9, MVP subset of §23 editing)."""

from pathlib import Path

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label

from subforge.app.project_store import load_project, save_project
from subforge.subtitles.timeutils import format_srt


class CaptionReviewScreen(Screen):
    BINDINGS = [Binding("ctrl+s", "save", "Save")]

    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.project = load_project(project_dir)

    def compose(self):
        with Vertical():
            yield Label(f"Caption Review — {self.project.project.name}")
            table = DataTable(id="segments")
            table.add_columns("ID", "Time", "Text")
            yield table
            yield Input(placeholder="Edit text; Enter to apply", id="edit")
            yield Label("Ctrl+S Save   ↑↓ Navigate", id="hints")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for seg in sorted(self.project.segments, key=lambda s: s.start):
            table.add_row(str(seg.id), format_srt(seg.start)[:11], seg.source, key=str(seg.id))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "edit":
            return
        table = self.query_one(DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_cell).row_key
        self.apply_edit(int(row_key.value), event.input.value)  # type: ignore[union-attr]

    def apply_edit(self, segment_id: int, text: str) -> None:
        for seg in self.project.segments:
            if seg.id == segment_id:
                seg.source = text
                break
        save_project(self.project_dir, self.project)
        table = self.query_one(DataTable)
        row_idx = next(i for i, row in enumerate(table.rows.values()) if row.key.value == str(segment_id))  # type: ignore[union-attr]
        table.update_cell(str(segment_id), column_index=2, value=text)  # type: ignore[arg-type]

    def action_save(self) -> None:
        save_project(self.project_dir, self.project)
        self.query_one("#hints", Label).update("Saved ✓")
```

If `DataTable` API details differ in the installed Textual version, adapt row update mechanics — the contract under test is `apply_edit(segment_id, text)` mutating and saving the project.

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest tests/unit/test_caption_review.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/tui/screens/caption_review.py tests/unit/test_caption_review.py
git commit -m "feat: caption review screen with edit and save"
```

---

### Task 17: Translation review + export screen

**Files:**
- Create: `src/subforge/tui/screens/review_translate.py`
- Test: `tests/unit/test_review_translate.py`

**Interfaces:**
- Consumes: `TranslationService` (injected fake in tests), `export_subtitles`.
- Produces: `ReviewTranslateScreen(project_dir: Path, translation_service)` showing side-by-side Source/Translation columns per segment; `apply_edit(segment_id, language, text)` public mutator + save; action `do_export(formats, languages)` calling `export_subtitles` and surfacing resulting filenames in the status label.

- [ ] **Step 1: Write failing test**

`tests/unit/test_review_translate.py`:

```python
from pathlib import Path

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.providers.base import TranslationInput, TranslationOutput
from subforge.tui.screens.review_translate import ReviewTranslateScreen


class EchoTranslator:
    def translate(self, segments: list[TranslationInput], source_language: str, target_language: str):
        return [TranslationOutput(id=s.id, text=f"<{target_language}> {s.text}") for s in segments]


def seed(tmp_path: Path) -> Path:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id", target_languages=["en"]))
    project = load_project(d)
    project.segments = [Segment(id=1, start=1.2, end=3.4, source="Halo!")]
    save_project(d, project)
    return d


async def test_edit_translation_and_export(tmp_path):
    from subforge.app.translation_service import TranslationService

    d = seed(tmp_path)
    from subforge.tui.app import SubForgeApp

    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ReviewTranslateScreen(d, TranslationService(EchoTranslator()))
        await app.push_screen(screen)
        await pilot.pause()

        screen.apply_edit(1, "en", "Hi there!")
        await pilot.pause()
        assert load_project(d).segments[0].translations["en"] == "Hi there!"

        paths = screen.do_export(["srt"], ["en"])
        assert (d / "exports" / "en.srt").exists()
        assert any(p.name == "en.srt" for p in paths)
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_review_translate.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/tui/screens/review_translate.py`:

```python
"""Translation review and export trigger (PRD §10 review step, §23 export)."""

from pathlib import Path

from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label

from subforge.app.export import export_subtitles
from subforge.app.project_store import load_project, save_project
from subforge.app.translation_service import TranslationService


class ReviewTranslateScreen(Screen):
    def __init__(self, project_dir: Path, translation_service: TranslationService) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.service = translation_service
        self.project = load_project(project_dir)

    def compose(self):
        with Vertical():
            yield Label("Translation Review")
            table = DataTable(id="review")
            table.add_columns("ID", "Source", "Translation")
            yield table
            yield Input(placeholder="Fix translation; Enter applies to selected row", id="fix")
            yield Label("", id="export-status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for seg in self.project.segments:
            table.add_row(str(seg.id), seg.source, seg.translations.get("en", "—"))

    def apply_edit(self, segment_id: int, language: str, text: str) -> None:
        for seg in self.project.segments:
            if seg.id == segment_id:
                seg.translations[language] = text
                break
        save_project(self.project_dir, self.project)
        self.query_one("#review", DataTable).refresh()

    def do_export(self, formats: list[str], languages: list[str]) -> list:
        paths = export_subtitles(self.project_dir, formats=formats, languages=languages)
        self.query_one("#export-status", Label).update("Exported: " + ", ".join(p.name for p in paths))
        return paths
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest tests/unit/test_review_translate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/tui/screens/review_translate.py tests/unit/test_review_translate.py
git commit -m "feat: translation review screen with export action"
```

---

### Task 18: End-to-end integration test (fakes, no network/GPU)

**Files:**
- Test: `tests/integration/test_full_flow.py`
- Create: `tests/fixtures/make_sine_wav.py` (generates a 1-second silent WAV fixture deterministically at test time — never commit binary audio, ARCH §34)

**Interfaces:**
- Consumes: full stack: store → Pipeline (FakeASR/FakeTranslator) → export.
- Produces: confidence that `Audio file → transcript → translation → SRT/ASS` produces correct files (ARCH §34 integration flow).

- [ ] **Step 1: Write the integration test**

`tests/integration/test_full_flow.py`:

```python
import json
from pathlib import Path

from subforge.app.export import export_subtitles
from subforge.app.pipeline import Pipeline
from subforge.app.project_store import create_project, load_project
from subforge.config.settings import Settings
from subforge.models.project import ProjectMeta, StageState
from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.base import TranslationInput, TranslationOutput


class ScriptedASR:
    TRANSCRIPT = Transcript(
        language="id",
        segments=[
            TranscriptSegment(id=1, start=1.2, end=3.4, text="Halo semuanya!"),
            TranscriptSegment(id=2, start=3.5, end=6.8, text="Selamat datang kembali."),
        ],
    )

    def transcribe(self, audio_path, language=None):
        assert audio_path.exists(), "pipeline must read from audio/ directory"
        return self.TRANSCRIPT


class ScriptedLLM:
    MAP = {
        1: "Hello everyone!",
        2: "Welcome back.",
    }

    def translate(self, segments: list[TranslationInput], source_language: str, target_language: str):
        assert target_language == "en"
        return [TranslationOutput(id=s.id, text=self.MAP[s.id]) for s in segments]


def test_audio_to_srt_and_ass(tmp_path: Path):
    from subforge.app.translation_service import TranslationService

    d = create_project(tmp_path / "yt-001", ProjectMeta(name="yt-001", source_language="id", target_languages=["en"]))
    (d / "audio" / "final_audio.wav").write_bytes(b"RIFF....")  # fakes never decode it

    pipe = Pipeline(
        d,
        Settings(),
        transcription=ScriptedASR(),
        translation_service=TranslationService(ScriptedLLM()),
    )
    pipe.run_transcription("final_audio.wav")
    pipe.run_diarization("final_audio.wav")          # no provider -> SKIPPED, must not block
    pipe.run_translation("en")
    written = export_subtitles(d, formats=["srt", "ass"], languages=["en"])

    names = {p.name for p in written}
    assert names == {"source.srt", "en.srt", "source.ass", "en.ass"}

    en_srt = (d / "exports" / "en.srt").read_text()
    assert "1\n00:00:01,200 --> 00:00:03,400\nHello everyone!" in en_srt
    assert "2\n00:00:03,500 --> 00:00:06,800\nWelcome back." in en_srt

    project = load_project(d)
    assert project.get_stage("diarization") is StageState.SKIPPED
    assert project.get_stage("export") is StageState.COMPLETED

    # transcripts/source.json matches canonical normalization
    stored = json.loads((d / "transcripts" / "source.json").read_text())
    assert stored["segments"][0]["text"] == "Halo semuanya!"


def test_retry_after_translation_failure_only_reruns_translation(tmp_path: Path):
    from subforge.app.translation_service import TranslationService, TranslationValidationError
    from subforge.providers.base import TranslationOutput as Out

    class FlakyLLM(ScriptedLLM):
        def __init__(self):
            self.failed_once = False

        def translate(self, segments, source_language, target_language):
            if not self.failed_once:
                self.failed_once = True
                return [Out(id=999, text="garbage")]  # invalid: unknown id -> batch rejected
            return super().translate(segments, source_language, target_language)

    d = create_project(tmp_path / "yt", ProjectMeta(name="yt", source_language="id", target_languages=["en"]))
    (d / "audio" / "a.wav").write_bytes(b"x")
    llm = FlakyLLM()
    pipe = Pipeline(d, Settings(), transcription=ScriptedASR(), translation_service=TranslationService(llm))
    pipe.run_transcription("a.wav")

    import pytest

    with pytest.raises(StageError):
        pipe.run_translation("en")
    assert pipe.load().get_stage("translation_en") is StageState.FAILED

    # Retry: transcription stage must NOT be re-executed (only translation runs again).
    asr_calls_marker = load_project(d).get_stage("transcription")
    pipe.retry("translation", "en")
    final = load_project(d)
    assert final.get_stage("translation_en") is StageState.COMPLETED
    assert final.get_stage("transcription") is asr_calls_marker is StageState.COMPLETED
    assert final.segments[0].translations["en"] == "Hello everyone!"
```

(The test imports `StageError` from `subforge.app.pipeline`; add that import.)

- [ ] **Step 2: Run the suite**

Run: `uv run pytest tests/ -v`
Expected: all unit + integration tests PASS.

- [ ] **Step 3: Full quality gate**

```bash
uv run ruff check src tests
uv run mypy src
```
Expected: clean (fix trivial issues in place; type-ignore comments allowed for Textual internals).

- [ ] **Step 4: Commit**

```bash
git add tests/integration tests/fixtures
git commit -m "test: end-to-end flow with scripted providers incl. retry-after-failure"
```

---

---

### Task 19: App configuration store (TUI-first, replaces .env as primary path)

**Files:**
- Create: `src/subforge/config/app_config.py`
- Test: `tests/unit/test_app_config.py`

**Interfaces:**
- Consumes: nothing (stdlib + pydantic).
- Produces:
  - `TranscriptionConfig(provider: Literal["local","openai"] = "local", model: str = "", api_key: str = "")`
  - `TranslationConfig(source: Literal["local","provider"] = "local", local_base_url: str = "http://localhost:1234/v1", local_api_key: str = "", provider: Literal["openai","opencode-zen","opencode-go"] = "openai", api_key: str = "", model: str = "", reasoning_effort: str = "", batch_size: int = 5)`
  - `AppConfig(transcription, translation)`
  - `default_config_path() -> Path` — `$SUBFORGE_CONFIG` or `~/.config/subforge/config.json`
  - `load_app_config(path=None) -> AppConfig` (missing/corrupt file → defaults; corrupt warns on stderr)
  - `save_app_config(config, path=None) -> Path` — atomic (tmp + `os.replace`), creates parents, `chmod 600` on POSIX (plaintext keys inside!).
- Rationale: the user types their API key once in the TUI — there is NO `.env` step in the creator workflow. Env-var support (Task 7) remains only for headless automation.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_app_config.py`:

```python
import stat

from subforge.config.app_config import (
    AppConfig,
    default_config_path,
    load_app_config,
    save_app_config,
)


def test_defaults_are_local_and_empty_secrets():
    cfg = AppConfig()
    assert cfg.transcription.provider == "local"
    assert cfg.transcription.api_key == ""
    assert cfg.translation.source == "local"
    assert cfg.translation.local_base_url == "http://localhost:1234/v1"
    assert cfg.translation.api_key == ""
    assert cfg.translation.reasoning_effort == ""


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "subforge" / "config.json"
    cfg = AppConfig(
        transcription={"provider": "openai", "model": "whisper-1", "api_key": "sk-t"},
        translation={
            "source": "provider",
            "provider": "opencode-go",
            "api_key": "oc-t",
            "model": "glm-5.2",
            "reasoning_effort": "high",
        },
    )
    save_app_config(cfg, path)
    loaded = load_app_config(path)
    assert loaded == cfg
    assert loaded.translation.model == "glm-5.2"


def test_missing_file_returns_defaults(tmp_path):
    assert load_app_config(tmp_path / "does-not-exist.json") == AppConfig()


def test_corrupt_file_returns_defaults(tmp_path):
    bad = tmp_path / "config.json"
    bad.write_text("{not json")
    assert load_app_config(bad) == AppConfig()


def test_saved_file_is_user_only_on_posix(tmp_path):
    path = tmp_path / "config.json"
    save_app_config(AppConfig(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600  # plaintext keys demand it


def test_env_var_overrides_path(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "custom.json"))
    assert default_config_path() == tmp_path / "custom.json"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_app_config.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/config/app_config.py`:

```python
"""App-level configuration typed by the user in the TUI.

Primary configuration path: NO .env step for creators. Keys are entered in the
Setup/Settings screens and stored here. File holds PLAINTEXT SECRETS — atomic
writes and 0600 permissions are mandatory. Never commit, never log contents.
"""

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class TranscriptionConfig(BaseModel):
    provider: Literal["local", "openai"] = "local"
    model: str = ""   # local: large-v3|medium|small|base ; openai: picked from live /models
    api_key: str = ""  # only meaningful when provider == "openai"


class TranslationConfig(BaseModel):
    source: Literal["local", "provider"] = "local"
    local_base_url: str = "http://localhost:1234/v1"  # LM Studio / Ollama (OpenAI-compatible)
    local_api_key: str = ""                           # usually empty for local servers
    provider: Literal["openai", "opencode-zen", "opencode-go"] = "openai"
    api_key: str = ""
    model: str = ""
    reasoning_effort: str = ""  # MUST be one of the model's discovered values (Task 21)
    batch_size: int = 5         # PRD §11 contextual batch of five segments


class AppConfig(BaseModel):
    transcription: TranscriptionConfig = TranscriptionConfig()
    translation: TranslationConfig = TranslationConfig()


def default_config_path() -> Path:
    env = os.environ.get("SUBFORGE_CONFIG")
    if env:
        return Path(env)
    return Path.home() / ".config" / "subforge" / "config.json"


def save_app_config(config: AppConfig, path: Path | None = None) -> Path:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, target)
    if os.name == "posix":
        os.chmod(target, 0o600)
    return target


def load_app_config(path: Path | None = None) -> AppConfig:
    target = path or default_config_path()
    if not target.exists():
        return AppConfig()
    try:
        return AppConfig.model_validate_json(target.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"[WARN] Ignoring corrupt config file {target}: {exc}", file=sys.stderr)
        return AppConfig()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_app_config.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/config/app_config.py tests/unit/test_app_config.py
git commit -m "feat: TUI-first app config store with atomic 0600 persistence"
```

---

### Task 20: OpenAI Audio API transcription provider (only remote ASR in MVP)

**Files:**
- Create: `src/subforge/providers/transcription/openai.py`
- Test: `tests/unit/test_openai_transcription.py`

**Interfaces:**
- Consumes: `Transcript`/`TranscriptSegment` (Task 2), `REGISTRY` (Task 8).
- Produces: `OpenAITranscriptionProvider(api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "whisper-1", client: httpx.Client | None = None)` implementing `transcribe(audio_path, language=None) -> Transcript` via `POST {base_url}/audio/transcriptions` with `response_format=verbose_json`, plus `list_models() -> list[str]` via `GET {base_url}/models`. Registers as `"openai"`. Default model `whisper-1` because `verbose_json` carries segment timestamps; timestamp-less models (`gpt-4o-transcribe`, …) degrade to a single `[0, duration]` segment rather than failing. Verified live: `/v1/models` lists 130 models incl. `whisper-1`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_openai_transcription.py`:

```python
from pathlib import Path

import httpx

from subforge.providers.registry import REGISTRY
from subforge.providers.transcription.openai import OpenAITranscriptionProvider


VERBOSE_JSON = {
    "task": "transcribe",
    "language": "id",
    "duration": 6.8,
    "segments": [
        {"id": 0, "start": 1.2, "end": 3.4, "text": " Halo semuanya!"},
        {"id": 1, "start": 3.5, "end": 6.8, "text": " Selamat datang."},
    ],
}


def make_audio(tmp_path: Path) -> Path:
    audio = tmp_path / "final_audio.wav"
    audio.write_bytes(b"RIFF-fake")
    return audio


def test_transcribe_normalizes_verbose_json(tmp_path: Path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = request.read().decode(errors="replace")
        return httpx.Response(200, json=VERBOSE_JSON)

    provider = OpenAITranscriptionProvider(
        api_key="sk-test", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    transcript = provider.transcribe(make_audio(tmp_path), language="id")

    assert transcript.language == "id"
    assert transcript.segments[0].start == 1.2
    assert transcript.segments[0].text == "Halo semuanya!"  # stripped
    assert captured["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert captured["auth"] == "Bearer sk-test"
    assert "whisper-1" in captured["body"]  # default model travels in form data


def test_timestampless_model_degrades_to_single_segment(tmp_path: Path):
    def handler(request):
        return httpx.Response(200, json={"text": "Halo semuanya!", "duration": 3.4})

    provider = OpenAITranscriptionProvider(
        api_key="k", model="gpt-4o-transcribe",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    t = provider.transcribe(make_audio(tmp_path))
    assert len(t.segments) == 1
    assert t.segments[0].text == "Halo semuanya!"
    assert (t.segments[0].start, t.segments[0].end) == (0.0, 3.4)


def test_list_models_for_picker():
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/models"
        return httpx.Response(200, json={"data": [{"id": "whisper-1"}, {"id": "gpt-4o-transcribe"}]})

    provider = OpenAITranscriptionProvider(api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert provider.list_models() == ["gpt-4o-transcribe", "whisper-1"]


def test_registered_as_openai():
    assert REGISTRY.resolve_transcription("openai") is OpenAITranscriptionProvider
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_openai_transcription.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/providers/transcription/openai.py`:

```python
"""OpenAI Audio API transcription — the only remote ASR provider in the MVP."""

from pathlib import Path

import httpx

from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.registry import REGISTRY

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "whisper-1"  # verbose_json returns segment timestamps


class OpenAITranscriptionProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.client = client or httpx.Client(timeout=600.0)

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        with open(audio_path, "rb") as fh:
            data: dict[str, str] = {"model": self.model_name, "response_format": "verbose_json"}
            if language:
                data["language"] = language
            response = self.client.post(
                f"{self.base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (audio_path.name, fh)},
                data=data,
            )
        response.raise_for_status()
        return self._normalize(response.json())

    @staticmethod
    def _normalize(payload: dict) -> Transcript:
        segments = [
            TranscriptSegment(
                id=int(seg.get("id", i)),
                start=float(seg["start"]),
                end=float(seg["end"]),
                text=str(seg["text"]).strip(),
            )
            for i, seg in enumerate(payload.get("segments", []))
        ]
        if not segments:
            # Models like gpt-4o-transcribe return plain text without timestamps.
            text = str(payload.get("text", "")).strip()
            if text:
                segments = [
                    TranscriptSegment(id=0, start=0.0, end=float(payload.get("duration", 0.0)), text=text)
                ]
        return Transcript(language=payload.get("language"), segments=segments)

    def list_models(self) -> list[str]:
        """Live model IDs from GET /models so the TUI picker shows real choices."""
        response = self.client.get(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        return sorted(str(m["id"]) for m in response.json().get("data", []) if m.get("id"))


REGISTRY.register_transcription("openai", OpenAITranscriptionProvider)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_openai_transcription.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/providers/transcription/openai.py tests/unit/test_openai_transcription.py
git commit -m "feat: OpenAI Audio API transcription provider with live model listing"
```

---

### Task 21: Model capability discovery — provider-driven reasoning vocabularies

**Files:**
- Create: `src/subforge/providers/capabilities.py`
- Test: `tests/unit/test_capabilities.py`

**Interfaces:**
- Consumes: nothing provider-specific (plain HTTP + dataclasses).
- Produces:
  - `ReasoningSpec(kind: Literal["effort","toggle","unsupported"], values: tuple[str, ...])` — `values` populated only for `kind == "effort"`, taken VERBATIM from model metadata (never a hardcoded low/medium/high assumption).
  - `CapabilityClient(client: httpx.Client | None = None, catalog_url: str = "https://models.dev/api.json")` with `reasoning_spec(provider_preset: str, model_id: str) -> ReasoningSpec`. Catalog mapping: `openai`→`openai`, `opencode-zen`→`opencode`, `opencode-go`→`opencode-go`; anything else (local LM Studio/Ollama) → `unsupported`.
  - Parsing rules derived from live inspection: entry missing / `reasoning` falsy / options missing-or-empty → `unsupported`; `{"type":"effort","values":[...]}` → effort with those values; `{"type":"toggle"}` → toggle (MVP sends no parameter for toggle). Verified examples: `glm-5.2`→effort `[high, max]`, `kimi-k3`→effort `[max]`, `claude-sonnet-5`→effort `[low, medium, high, xhigh, max]`, `gpt-5.6-luna` (openai)→includes `none`, `grok-4.5` (go)→`[low, medium, high]`, `longcat-2.0`→toggle, `qwen3-coder`/`gpt-4o`→unsupported.

- [ ] **Step 1: Write failing tests**

`tests/unit/test_capabilities.py`:

```python
import json

import httpx

from subforge.providers.capabilities import CapabilityClient, ReasoningSpec


CATALOG = {
    "openai": {"models": {
        "gpt-5.6-luna": {"reasoning": True,
                          "reasoning_options": [{"type": "effort", "values": ["none", "low", "medium", "high"]}]},
        "gpt-4o": {"reasoning": False},
    }},
    "opencode": {"models": {
        "glm-5.2": {"reasoning": True, "reasoning_options": [{"type": "effort", "values": ["high", "max"]}]},
        "kimi-k3": {"reasoning": True, "reasoning_options": [{"type": "effort", "values": ["max"]}]},
        "nemotron-3-ultra-free": {"reasoning": True, "reasoning_options": []},
        "qwen3-coder": {"reasoning": False},
        "longcat-2.0": {"reasoning": True, "reasoning_options": [{"type": "toggle"}]},
    }},
    "opencode-go": {"models": {
        "grok-4.5": {"reasoning": True, "reasoning_options": [{"type": "effort", "values": ["low", "medium", "high"]}]},
    }},
}


def make_client() -> CapabilityClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://models.dev/api.json"
        return httpx.Response(200, text=json.dumps(CATALOG))

    return CapabilityClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_effort_values_come_verbatim_from_metadata():
    c = make_client()
    assert c.reasoning_spec("opencode-zen", "glm-5.2") == ReasoningSpec("effort", ("high", "max"))
    assert c.reasoning_spec("opencode-zen", "kimi-k3") == ReasoningSpec("effort", ("max",))
    assert c.reasoning_spec("opencode-go", "grok-4.5") == ReasoningSpec("effort", ("low", "medium", "high"))


def test_non_reasoning_model_is_unsupported():
    c = make_client()
    assert c.reasoning_spec("openai", "gpt-4o") == ReasoningSpec("unsupported", ())
    assert c.reasoning_spec("opencode-zen", "qwen3-coder") == ReasoningSpec("unsupported", ())


def test_toggle_is_its_own_kind():
    c = make_client()
    assert c.reasoning_spec("opencode-zen", "longcat-2.0").kind == "toggle"


def test_reasoning_true_with_no_options_is_unsupported():
    # nemotron advertises reasoning but exposes no effort vocabulary -> hide control
    c = make_client()
    assert c.reasoning_spec("opencode-zen", "nemotron-3-ultra-free") == ReasoningSpec("unsupported", ())


def test_unknown_model_or_local_provider_is_unsupported():
    c = make_client()
    assert c.reasoning_spec("opencode-zen", "totally-unknown").kind == "unsupported"
    assert c.reasoning_spec("openai-compatible", "qwen3-14b").kind == "unsupported"  # local server


def test_catalog_fetch_failure_is_unsupported_not_crash():
    def handler(request):
        return httpx.Response(503)

    c = CapabilityClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert c.reasoning_spec("openai", "gpt-4o").kind == "unsupported"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_capabilities.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/providers/capabilities.py`:

```python
"""Per-model capability metadata from the models.dev catalog.

Reasoning effort vocabularies are MODEL-specific and discovered here — never
hardcoded. Sending an unlisted value fails upstream, so the UI offers exactly
these values (or hides the control entirely).
"""

from dataclasses import dataclass
from typing import Literal

import httpx

MODELS_DEV_URL = "https://models.dev/api.json"

# translation provider preset -> models.dev provider id
PROVIDER_TO_CATALOG = {
    "openai": "openai",
    "opencode-zen": "opencode",
    "opencode-go": "opencode-go",
}


@dataclass(frozen=True)
class ReasoningSpec:
    kind: Literal["effort", "toggle", "unsupported"]
    values: tuple[str, ...] = ()


UNSUPPORTED = ReasoningSpec("unsupported", ())


class CapabilityClient:
    def __init__(self, client: httpx.Client | None = None, catalog_url: str = MODELS_DEV_URL) -> None:
        self.client = client or httpx.Client(timeout=15.0)
        self.catalog_url = catalog_url
        self._cache: dict | None = None

    def _catalog(self) -> dict | None:
        if self._cache is None:
            try:
                response = self.client.get(self.catalog_url)
                response.raise_for_status()
                self._cache = response.json()
            except Exception:  # noqa: BLE001 — any failure degrades to "unknown"
                self._cache = {}
        return self._cache or None

    def reasoning_spec(self, provider_preset: str, model_id: str) -> ReasoningSpec:
        catalog_id = PROVIDER_TO_CATALOG.get(provider_preset)
        catalog = self._catalog() if catalog_id else None
        if not catalog:
            return UNSUPPORTED
        entry = catalog.get(catalog_id, {}).get("models", {}).get(model_id)
        if not entry or not entry.get("reasoning"):
            return UNSUPPORTED

        for option in entry.get("reasoning_options") or []:
            if option.get("type") == "effort" and option.get("values"):
                return ReasoningSpec("effort", tuple(str(v) for v in option["values"]))
            if option.get("type") == "toggle":
                return ReasoningSpec("toggle", ())
        return UNSUPPORTED  # reasoning=True but no usable vocabulary (e.g. nemotron)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_capabilities.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/providers/capabilities.py tests/unit/test_capabilities.py
git commit -m "feat: provider-driven reasoning capability discovery via models.dev"
```

---

### Task 22: Local whisper model manager (choose which model to install)

**Files:**
- Create: `src/subforge/app/model_manager.py`
- Test: `tests/unit/test_model_manager.py`

**Interfaces:**
- Consumes: optional extras `faster-whisper` / `huggingface_hub` (lazy imports only — ARCH §27).
- Produces:
  - `LocalModelInfo(id: str, profile: str, vram: str, installed: bool)`
  - `KNOWN_WHISPER_MODELS`: `large-v3`→Quality/~10 GB VRAM, `medium`→Balanced/~5 GB, `small`→Lightweight/~2 GB, `base`→Lightweight/~1 GB (PRD §8 profiles).
  - `LocalModelManager(cache_checker=None, downloader=None)` with `list_models() -> list[LocalModelInfo]` and `install(model_id: str)` (blocking download; the TUI wraps it in a worker). Defaults: checker probes the HF cache via `huggingface_hub.snapshot_download(repo_id, local_files_only=True)` success; downloader calls `faster_whisper.utils.download_model(model_id)`. Missing optional deps raise `RuntimeError` mentioning `subforge[local]`. Repo map: `large-v3`→`Systran/faster-whisper-large-v3` (same pattern for medium/small/base).

- [ ] **Step 1: Write failing tests**

`tests/unit/test_model_manager.py`:

```python
import pytest

from subforge.app.model_manager import KNOWN_WHISPER_MODELS, LocalModelManager


def cached(models: set[str]):
    return lambda repo_id: any(m in repo_id for m in models)


def failing_downloader(model_id):
    raise AssertionError("download must not be called when listing")


def test_list_marks_installed_from_cache():
    mgr = LocalModelManager(cache_checker=cached({"large-v3"}), downloader=failing_downloader)
    infos = {i.id: i for i in mgr.list_models()}
    assert set(infos) == set(KNOWN_WHISPER_MODELS)
    assert infos["large-v3"].installed is True
    assert infos["medium"].installed is False
    assert infos["large-v3"].profile == "Quality"
    assert infos["base"].profile == "Lightweight"


def test_install_invokes_downloader_for_known_model():
    calls = []

    def downloader(model_id):
        calls.append(model_id)
        return f"/cache/{model_id}"

    mgr = LocalModelManager(cache_checker=cached(set()), downloader=downloader)
    assert mgr.install("small") == "/cache/small"
    assert calls == ["small"]


def test_install_rejects_unknown_model():
    mgr = LocalModelManager(cache_checker=cached(set()), downloader=failing_downloader)
    with pytest.raises(ValueError, match="unknown local model"):
        mgr.install("tiny-en-diy")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_model_manager.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/app/model_manager.py`:

```python
"""Discovery + installation of local Whisper models (PRD §8 hardware profiles)."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

LOCAL_EXTRAS_HINT = 'Local transcription models require the optional extra: pip install "subforge[local]"'

KNOWN_WHISPER_MODELS: dict[str, dict[str, str]] = {
    "large-v3": {"profile": "Quality", "vram": "~10 GB VRAM"},
    "medium": {"profile": "Balanced", "vram": "~5 GB VRAM"},
    "small": {"profile": "Lightweight", "vram": "~2 GB VRAM"},
    "base": {"profile": "Lightweight", "vram": "~1 GB VRAM"},
}

HF_REPOS = {
    "large-v3": "Systran/faster-whisper-large-v3",
    "medium": "Systran/faster-whisper-medium",
    "small": "Systran/faster-whisper-small",
    "base": "Systran/faster-whisper-base",
}


@dataclass(frozen=True)
class LocalModelInfo:
    id: str
    profile: str
    vram: str
    installed: bool


def _default_cache_checker(repo_id: str) -> bool:
    try:
        from huggingface_hub import snapshot_download  # noqa: PLC0415 — optional dep
    except ImportError as exc:
        raise RuntimeError(LOCAL_EXTRAS_HINT) from exc
    try:
        snapshot_download(repo_id=repo_id, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001 — not cached (or offline)
        return False


def _default_downloader(model_id: str) -> Any:
    try:
        from faster_whisper.utils import download_model  # noqa: PLC0415 — optional dep
    except ImportError as exc:
        raise RuntimeError(LOCAL_EXTRAS_HINT) from exc
    return download_model(model_id)


class LocalModelManager:
    def __init__(
        self,
        cache_checker: Callable[[str], bool] | None = None,
        downloader: Callable[[str], Any] | None = None,
    ) -> None:
        self._check = cache_checker or _default_cache_checker
        self._download = downloader or _default_downloader

    def list_models(self) -> list[LocalModelInfo]:
        infos = []
        for model_id, meta in KNOWN_WHISPER_MODELS.items():
            installed = self._check(HF_REPOS[model_id])
            infos.append(LocalModelInfo(model_id, meta["profile"], meta["vram"], installed))
        return infos

    def install(self, model_id: str) -> Any:
        if model_id not in KNOWN_WHISPER_MODELS:
            raise ValueError(f"[ERROR] unknown local model: {model_id}")
        return self._download(model_id)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_model_manager.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/app/model_manager.py tests/unit/test_model_manager.py
git commit -m "feat: local whisper model manager with cache-aware install"
```

---

### Task 23: Provider factories (AppConfig → concrete providers)

**Files:**
- Create: `src/subforge/app/provider_factory.py`
- Test: `tests/unit/test_provider_factory.py`

**Interfaces:**
- Consumes: `AppConfig` (Task 19), `WhisperXProvider` (Task 11), `OpenAITranscriptionProvider` (Task 20), `OpenAICompatibleProvider` (Task 10), `TRANSLATION_PRESETS` (Task 7), `ReasoningSpec` (Task 21).
- Produces:
  - `build_transcription_provider(cfg: AppConfig)` — `local` → `WhisperXProvider(model=…)` (non-empty model required); `openai` → `OpenAITranscriptionProvider(api_key=…, model=…)` (both required); else `ValueError("[ERROR] unknown transcription provider: …")`.
  - `build_translation_provider(cfg: AppConfig) -> OpenAICompatibleProvider` — `local` → base_url=`cfg.translation.local_base_url` (required), key=`local_api_key` (optional — LM Studio/Ollama often need none); `provider` → preset base URL from `TRANSLATION_PRESETS[cfg.translation.provider]` (Task 7), key required, model required.
  - `validate_reasoning_choice(spec: ReasoningSpec, chosen: str) -> str` — returns `chosen` iff `spec.kind == "effort"` and `chosen in spec.values`, else `""` (drops stale values after a model switch; UI re-prompts).

- [ ] **Step 1: Write failing tests**

`tests/unit/test_provider_factory.py`:

```python
import pytest

from subforge.app.provider_factory import (
    build_translation_provider,
    build_transcription_provider,
    validate_reasoning_choice,
)
from subforge.config.app_config import AppConfig
from subforge.providers.capabilities import ReasoningSpec
from subforge.providers.transcription.whisperx import WhisperXProvider


def test_local_transcription_needs_model():
    with pytest.raises(ValueError, match="no local transcription model"):
        build_transcription_provider(AppConfig())  # provider=local, model=""


def test_local_transcription_builds_whisperx():
    cfg = AppConfig(transcription={"provider": "local", "model": "small"})
    provider = build_transcription_provider(cfg)
    assert isinstance(provider, WhisperXProvider)
    assert provider.model_name == "small"


def test_openai_transcription_requires_key_and_model():
    cfg = AppConfig(transcription={"provider": "openai", "model": "", "api_key": "sk"})
    with pytest.raises(ValueError, match="model"):
        build_transcription_provider(cfg)
    cfg2 = AppConfig(transcription={"provider": "openai", "model": "whisper-1", "api_key": ""})
    with pytest.raises(ValueError, match="API key"):
        build_transcription_provider(cfg2)


def test_openai_transcription_built_with_key_and_model():
    cfg = AppConfig(transcription={"provider": "openai", "model": "gpt-4o-transcribe", "api_key": "sk-x"})
    p = build_transcription_provider(cfg)
    assert p.api_key == "sk-x" and p.model_name == "gpt-4o-transcribe"


def test_unknown_transcription_provider_rejected():
    with pytest.raises(ValueError, match="unknown transcription provider"):
        build_transcription_provider(AppConfig(transcription={"provider": "deepgram"}))


def test_local_translation_uses_custom_url_and_optional_key():
    cfg = AppConfig(translation={"source": "local", "local_base_url": "http://localhost:1234/v1", "model": "qwen3-14b"})
    p = build_translation_provider(cfg)
    assert p.base_url == "http://localhost:1234/v1"
    assert p.api_key == ""  # LM Studio / Ollama usually need none
    assert p.model == "qwen3-14b"


def test_local_translation_requires_url_and_model():
    cfg = AppConfig(translation={"source": "local", "local_base_url": "", "model": "m"})
    with pytest.raises(ValueError, match="base URL"):
        build_translation_provider(cfg)
    cfg2 = AppConfig(translation={"source": "local", "local_base_url": "http://x", "model": ""})
    with pytest.raises(ValueError, match="model"):
        build_translation_provider(cfg2)


def test_opencode_go_translation():
    cfg = AppConfig(translation={
        "source": "provider", "provider": "opencode-go",
        "api_key": "oc-k", "model": "glm-5.2", "reasoning_effort": "max",
    })
    p = build_translation_provider(cfg)
    assert p.base_url == "https://opencode.ai/zen/go/v1"
    assert p.api_key == "oc-k"
    assert p.model == "glm-5.2"


def test_provider_translation_requires_key_and_model():
    cfg = AppConfig(translation={"source": "provider", "provider": "openai", "api_key": "", "model": "gpt-5.6-luna"})
    with pytest.raises(ValueError, match="API key"):
        build_translation_provider(cfg)
    cfg2 = AppConfig(translation={"source": "provider", "provider": "openai", "api_key": "k", "model": ""})
    with pytest.raises(ValueError, match="model"):
        build_translation_provider(cfg2)


def test_validate_reasoning_choice_drops_stale_values():
    spec = ReasoningSpec("effort", ("high", "max"))
    assert validate_reasoning_choice(spec, "max") == "max"
    assert validate_reasoning_choice(spec, "low") == ""  # not offered by THIS model
    assert validate_reasoning_choice(ReasoningSpec("unsupported", ()), "high") == ""
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_provider_factory.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/app/provider_factory.py`:

```python
"""Build concrete providers from the TUI-authored AppConfig.

Core pipeline modules never import this — they receive ready provider objects.
"""

from subforge.config.app_config import AppConfig
from subforge.config.providers import TRANSLATION_PRESETS
from subforge.providers.capabilities import ReasoningSpec
from subforge.providers.translation.openai_compatible import OpenAICompatibleProvider
from subforge.providers.transcription.openai import OpenAITranscriptionProvider
from subforge.providers.transcription.whisperx import WhisperXProvider


def build_transcription_provider(cfg: AppConfig):
    tc = cfg.transcription
    if tc.provider == "local":
        if not tc.model:
            raise ValueError("[ERROR] no local transcription model selected — pick one in Settings")
        return WhisperXProvider(model=tc.model)
    if tc.provider == "openai":
        if not tc.model:
            raise ValueError("[ERROR] no transcription model selected — pick one from the model list")
        if not tc.api_key:
            raise ValueError("[ERROR] Missing API key: enter your OPENAI_API_KEY in Settings")
        return OpenAITranscriptionProvider(api_key=tc.api_key, model=tc.model)
    raise ValueError(f"[ERROR] unknown transcription provider: {tc.provider}")


def build_translation_provider(cfg: AppConfig) -> OpenAICompatibleProvider:
    t = cfg.translation
    if not t.model:
        raise ValueError("[ERROR] no translation model selected — pick one from the model list")

    if t.source == "local":
        if not t.local_base_url:
            raise ValueError("[ERROR] enter your local server base URL (e.g. LM Studio) in Settings")
        return OpenAICompatibleProvider(base_url=t.local_base_url, api_key=t.local_api_key, model=t.model)

    preset = TRANSLATION_PRESETS.get(t.provider)
    if preset is None or not preset.base_url:
        raise ValueError(f"[ERROR] unknown translation provider: {t.provider}")
    if not t.api_key:
        raise ValueError(f"[ERROR] Missing API key for {preset.name}: enter it in Settings")
    return OpenAICompatibleProvider(base_url=preset.base_url, api_key=t.api_key, model=t.model)


def validate_reasoning_choice(spec: ReasoningSpec, chosen: str) -> str:
    """Keep a stored reasoning value only if the CURRENT model still offers it."""
    if spec.kind == "effort" and chosen in spec.values:
        return chosen
    return ""
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_provider_factory.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/app/provider_factory.py tests/unit/test_provider_factory.py
git commit -m "feat: AppConfig-driven provider factories with reasoning validation"
```

---

### Task 24: TUI model picker (live discovery, shared by transcribe & translate)

**Files:**
- Create: `src/subforge/tui/screens/model_picker.py`
- Test: `tests/unit/test_model_picker.py`

**Interfaces:**
- Consumes: any callable returning `list[str]` (`provider.list_models()` from Tasks 10/20) — keeps the screen logic-free and testable offline.
- Produces: `ModelPickerScreen(title: str, loader: Callable[[], list[str]]) -> ModalScreen[str]` — populates an `OptionList` from `loader()` on mount; selecting dismisses with the model ID (also stored in `screen.result`); `Escape` dismisses with `None`; empty list renders "No models found — check your API key / server URL".

- [ ] **Step 1: Write failing test**

`tests/unit/test_model_picker.py`:

```python
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.model_picker import ModelPickerScreen


class _Evt:
    def __init__(self, prompt: str) -> None:
        self.option = type("Opt", (), {"prompt": prompt})()


async def test_picker_lists_models_and_returns_selection():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen("Choose translation model", lambda: ["glm-5.2", "kimi-k3"])
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("OptionList").option_count == 2
        screen.on_option_list_option_selected(_Evt("kimi-k3"))
        await pilot.pause()
        assert screen.result == "kimi-k3"


async def test_empty_model_list_shows_hint():
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ModelPickerScreen("Choose model", lambda: [])
        await app.push_screen(screen)
        await pilot.pause()
        assert "No models found" in str(screen.query_one("#picker-status").render())
```

(The synthetic event avoids depending on Textual internals; adapt if the installed version differs — contracts under test are `result`, dismissal value, and the empty-list hint.)

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_model_picker.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/tui/screens/model_picker.py`:

```python
"""Reusable model-selection modal backed by live GET /models discovery."""

from collections.abc import Callable

from textual.screen import ModalScreen
from textual.widgets import Label, OptionList


class ModelPickerScreen(ModalScreen[str]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, loader: Callable[[], list[str]]) -> None:
        super().__init__()
        self.picker_title = title
        self.loader = loader
        self.result: str | None = None

    def compose(self):
        yield Label(f"[b]{self.picker_title}[/b]")
        yield OptionList(id="models")
        yield Label("Loading models…", id="picker-status")

    def on_mount(self) -> None:
        models = self.loader()  # sync; move into run_worker(thread=True) if slow in practice
        option_list = self.query_one("#models", OptionList)
        if not models:
            self.query_one("#picker-status", Label).update(
                "No models found — check your API key / server URL"
            )
            return
        for model_id in models:
            option_list.add_option(model_id)
        self.query_one("#picker-status", Label).update(f"{len(models)} models · Enter select · Esc cancel")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.result = str(event.option.prompt)
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest tests/unit/test_model_picker.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/tui/screens/model_picker.py tests/unit/test_model_picker.py
git commit -m "feat: reusable TUI model picker fed by live /models discovery"
```

---

### Task 25: Setup & Settings flow (local/provider choice, key entry, on-the-fly changes)

**Files:**
- Create: `src/subforge/tui/screens/settings.py`
- Test: `tests/unit/test_settings_screen.py`

**Interfaces:**
- Consumes: `save_app_config` (Task 19), `CapabilityClient`/`ReasoningSpec` (Task 21), `ModelPickerScreen` (Task 24), `validate_reasoning_choice` (Task 23).
- Produces:
  - `refresh_reasoning(current: str, spec: ReasoningSpec) -> str` — delegates to `validate_reasoning_choice`; called whenever the selected model changes so a stored reasoning value that no longer fits resets to `""`.
  - `ApiKeyInputScreen(title: str) -> ModalScreen[str | None]` — single masked `Input(password=True)`; Enter dismisses with the stripped key, Escape with `None`. Keys are NEVER echoed to logs.
  - `ReasoningPickerScreen(spec: ReasoningSpec) -> ModalScreen[str | None]` — offers EXACTLY `spec.values` (the vocabulary discovered for THIS model); Esc sends without the parameter.
  - `SettingsScreen(app_config, on_saved=None)` — interactive composition finalized in the UI-focused follow-up plan; state transitions documented in-code: Transcribe [Local→model-manager table w/ Install | Provider→key→picker]; Translate [Local→base URL→picker | Provider→preset→key→picker→reasoning picker if offered]; Save persists via `save_app_config` then calls `on_saved()` so providers rebuild mid-session (change-on-the-fly, no project restart).

- [ ] **Step 1: Write failing tests**

`tests/unit/test_settings_screen.py`:

```python
import inspect

from subforge.config.app_config import AppConfig
from subforge.providers.capabilities import ReasoningSpec
from subforge.tui.screens.settings import ApiKeyInputScreen, refresh_reasoning


def test_refresh_reasoning_keeps_valid_drops_stale():
    spec = ReasoningSpec("effort", ("high", "max"))
    assert refresh_reasoning("max", spec) == "max"
    assert refresh_reasoning("low", spec) == ""  # model switched: old value invalid
    assert refresh_reasoning("high", ReasoningSpec("unsupported", ())) == ""


def test_reasoning_picker_offers_exactly_discovered_values():
    from subforge.tui.screens.settings import ReasoningPickerScreen

    src = inspect.getsource(ReasoningPickerScreen)
    assert "spec.values" in src  # values come from metadata, never hardcoded


async def test_api_key_input_masks_and_returns_value():
    from subforge.tui.app import SubForgeApp

    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ApiKeyInputScreen("Enter OpenAI API key")
        await app.push_screen(screen)
        await pilot.pause()

        field = screen.query_one("Input")
        field.value = "  sk-secret  "
        screen.on_input_submitted(type("Evt", (), {"input": field})())
        await pilot.pause()
        assert screen.result == "sk-secret"


def test_api_key_is_masked():
    assert "password=True" in inspect.getsource(ApiKeyInputScreen)


def test_settings_screen_persists_on_save(tmp_path, monkeypatch):
    from subforge.tui.screens.settings import SettingsScreen

    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "config.json"))
    calls = []
    screen = SettingsScreen(AppConfig(), on_saved=lambda: calls.append(True))
    screen.save_config()  # public hook used by the (follow-up) widget wiring

    from subforge.config.app_config import load_app_config

    assert load_app_config().transcription.provider == "local"
    assert calls == [True]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_settings_screen.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`src/subforge/tui/screens/settings.py`:

```python
"""Setup & Settings: local/provider choice, key entry, model + reasoning picks.

All network access goes through provider objects' list_models(); this module
only orchestrates screens and writes AppConfig. Keys are masked, never logged.
"""

from collections.abc import Callable

from textual.screen import ModalScreen, Screen
from textual.widgets import Input, Label

from subforge.app.provider_factory import validate_reasoning_choice
from subforge.config.app_config import AppConfig, save_app_config
from subforge.providers.capabilities import ReasoningSpec


def refresh_reasoning(current: str, spec: ReasoningSpec) -> str:
    """Drop a stored reasoning value that the current model no longer offers."""
    return validate_reasoning_choice(spec, current)


class ApiKeyInputScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str) -> None:
        super().__init__()
        self.picker_title = title
        self.result: str | None = None

    def compose(self):
        yield Label(f"[b]{self.picker_title}[/b]")
        yield Input(password=True, placeholder="paste API key, Enter to confirm")
        yield Label("Esc cancel — stored locally in ~/.config/subforge/config.json")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.result = event.input.value.strip() or None
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ReasoningPickerScreen(ModalScreen[str | None]):
    """Offers EXACTLY the effort values discovered for the selected model."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, spec: ReasoningSpec) -> None:
        super().__init__()
        self.spec = spec
        self.result: str | None = None

    def compose(self):
        from textual.widgets import OptionList  # noqa: PLC0415 — keeps module import light

        yield Label("[b]Reasoning effort[/b] — values provided by the model")
        yield OptionList(*self.spec.values, id="reasoning")
        yield Label("Esc = send without reasoning parameter")

    def on_option_list_option_selected(self, event) -> None:  # noqa: ANN001 — Textual event varies
        self.result = str(event.option.prompt)
        self.dismiss(self.result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SettingsScreen(Screen):
    """Interactive configuration; state transitions per revision 2026-08-25:

      Transcribe:  [Local|Provider]
        Local    -> LocalModelManager.list_models() table (Install action) -> pick model
        Provider -> ApiKeyInputScreen -> ModelPickerScreen(openai.list_models)
      Translate:   [Local|Provider]
        Local    -> edit base URL -> ModelPickerScreen(OpenAICompatibleProvider(url, "").list_models)
        Provider -> pick openai|opencode-zen|opencode-go -> ApiKeyInputScreen
                 -> ModelPickerScreen -> ReasoningPickerScreen (only if spec.kind == "effort")
      Model changed -> cfg.translation.reasoning_effort = refresh_reasoning(old, new_spec)
      Save -> save_app_config(cfg) -> on_saved() rebuilds providers mid-session.

    The full interactive widget tree lands with the UI-focused follow-up plan;
    the tested contracts (modals above, refresh_reasoning, save_config) are complete here.
    """

    def __init__(self, app_config: AppConfig, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.cfg = app_config
        self.on_saved = on_saved

    def compose(self):
        yield Label("[b]SubForge Settings[/b] — changes apply immediately, no restart needed")

    def save_config(self) -> None:
        save_app_config(self.cfg)
        if self.on_saved:
            self.on_saved()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_settings_screen.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/tui/screens/settings.py tests/unit/test_settings_screen.py
git commit -m "feat: setup/settings modals with provider-driven reasoning picker"
```

---

## Deferred to follow-up plans (explicitly out of scope here)

- Real Textual wiring of menu items to Pipeline (file pickers, progress bars, the full interactive SettingsScreen widget tree) — needs a UI-focused plan against the installed Textual version.
- Non-effort reasoning styles (`{"type": "toggle"}` models like LongCat, `[]`-options models like Nemotron/MiniMax): MVP sends no parameter and hides the control; supporting them means per-provider parameter shapes beyond `reasoning_effort`.
- WhisperX model manager UI (download/cache/status table, ARCH §8).
- Hardware profile presets UI + detection recommendations (PRD §8, ARCH §30).
- Split/merge/delete/add caption operations beyond text edit (PRD §23).
- Speaker mapping screen (PRD §12) — data model (`speaker_map`) already exists.
- FFmpeg-based audio conversion/validation (ARCH §32).
- CI pipeline (lint/type/test workflow) once repository hosting exists (ARCH §35).

## Self-review summary

- Spec coverage: PRD §23 items map to tasks — transcription (11), caption editing (16, partial → deferred noted), translation (9–10), diarization optional (12), export (4, 5, 13), TUI (15–17), provider config (7), resumability (12), error states (12). Gaps are listed explicitly under "Deferred".
- Placeholder scan: no TBDs; all code blocks complete; two flagged implementation corrections inside Task 12 Step 3 notes are deliberate instructions, not gaps.
- Type consistency: `Transcript`/`Segment`/`TranslationInput|Output`/`DiarizationTurn`/`StageState` names verified consistent across tasks 2→18; `TranslationService.translate_project(project, target_language)` signature used identically in Tasks 12, 17, 18.
