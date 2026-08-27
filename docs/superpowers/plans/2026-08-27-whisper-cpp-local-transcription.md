# Always-Local `whisper.cpp` Transcription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition SubForge from WhisperX / Cloud OpenAI transcription to an always-local `whisper.cpp` transcription engine with automatic hardware detection and recommended model badges.

**Architecture:** A native `WhisperCppProvider` wraps `whisper-cli` with auto 16kHz audio conversion via `ffmpeg`, parsing JSON output into canonical `Transcript` objects. A lightweight `DeviceDetector` inspects RAM and CPU cores to compute model recommendations. `LocalModelManager` handles GGML model metadata and direct HTTP downloads. Setup Wizard and Settings screens are streamlined for always-local setup.

**Tech Stack:** Python 3.11+, Textual TUI, Pydantic, HTTPX, standard library (`subprocess`, `ctypes`, `os`, `shutil`, `urllib.request`).

**Spec:** `docs/superpowers/specs/2026-08-27-whisper-cpp-local-transcription-design.md`

## Global Constraints

- **Python Version:** Python >= 3.11, strict type hints (`mypy --strict` clean).
- **No Heavy ML Dependencies:** Zero PyTorch, CUDA, WhisperX, or Transformers packages in the Python environment.
- **Provider Protocol:** Concrete providers must adhere to `TranscriptionProvider` protocol in `src/subforge/providers/base.py` and register via `REGISTRY`.
- **Keyboard-First TUI:** Every screen and modal must be fully usable via keyboard bindings.
- **Non-blocking Testing:** All unit and integration tests must run without external network access, downloaded models, or GPU.

---

### Task 1: Hardware Detection & Recommendation Engine (`DeviceDetector`)

**Files:**
- Create: `src/subforge/app/device.py`
- Test: `tests/unit/test_device.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class DeviceSpecs:
      ram_gb: float
      cpu_cores: int

  class DeviceDetector:
      @staticmethod
      def get_specs() -> DeviceSpecs: ...
      @staticmethod
      def recommend_model(specs: DeviceSpecs) -> str: ...
  ```

- [ ] **Step 1: Write the failing unit tests for `DeviceDetector`**

`tests/unit/test_device.py`:
```python
from subforge.app.device import DeviceDetector, DeviceSpecs


def test_device_specs_dataclass():
    specs = DeviceSpecs(ram_gb=16.0, cpu_cores=8)
    assert specs.ram_gb == 16.0
    assert specs.cpu_cores == 8


def test_recommend_model_low_end():
    # Less than 6 GB RAM or <= 2 cores -> tiny
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=4.0, cpu_cores=2)) == "tiny"
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=5.5, cpu_cores=4)) == "tiny"


def test_recommend_model_budget():
    # 6 to 10 GB RAM -> base
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=8.0, cpu_cores=4)) == "base"
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=8.0, cpu_cores=2)) == "tiny"


def test_recommend_model_midrange():
    # 10 to 16 GB RAM with 4+ cores -> small
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=12.0, cpu_cores=6)) == "small"
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=16.0, cpu_cores=4)) == "small"


def test_recommend_model_highend():
    # >= 16 GB RAM with 6+ cores -> large-v3-turbo
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=16.0, cpu_cores=8)) == "large-v3-turbo"
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=32.0, cpu_cores=12)) == "large-v3-turbo"


def test_recommend_model_workstation():
    # > 32 GB RAM with >= 12 cores -> large-v3
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=64.0, cpu_cores=16)) == "large-v3"


def test_get_specs_returns_positive_numbers():
    specs = DeviceDetector.get_specs()
    assert specs.ram_gb > 0
    assert specs.cpu_cores > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_device.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'subforge.app.device'`

- [ ] **Step 3: Implement `DeviceDetector` in `src/subforge/app/device.py`**

```python
"""Hardware detection and model recommendations for whisper.cpp."""

import ctypes
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceSpecs:
    ram_gb: float
    cpu_cores: int


def _get_total_ram_gb() -> float:
    # 1. Windows via GlobalMemoryStatusEx
    if sys.platform == "win32":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024**3), 1)
        except Exception:
            pass

    # 2. Linux via /proc/meminfo or sysconf
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024**2), 1)
        except Exception:
            pass

    # 3. macOS / Unix via sysconf
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round((pages * page_size) / (1024**3), 1)
    except Exception:
        pass

    return 8.0  # Safe fallback default


class DeviceDetector:
    @staticmethod
    def get_specs() -> DeviceSpecs:
        cores = os.cpu_count() or 4
        ram = _get_total_ram_gb()
        return DeviceSpecs(ram_gb=ram, cpu_cores=cores)

    @staticmethod
    def recommend_model(specs: DeviceSpecs) -> str:
        ram = specs.ram_gb
        cores = specs.cpu_cores

        if ram < 6.0 or cores <= 2:
            return "tiny"
        if ram < 10.0 or cores < 4:
            return "base"
        if ram < 16.0 or cores < 6:
            return "small"
        if ram <= 32.0 or cores < 12:
            return "large-v3-turbo"
        return "large-v3"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_device.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/app/device.py tests/unit/test_device.py
git commit -m "feat: add hardware detection and model recommendation engine"
```

---

### Task 2: Local GGML Model Management (`LocalModelManager`)

**Files:**
- Modify: `src/subforge/app/model_manager.py`
- Modify: `tests/unit/test_model_manager.py`

**Interfaces:**
- Consumes: `DeviceDetector` from `subforge.app.device`
- Produces:
  ```python
  GGML_WHISPER_MODELS: dict[str, dict[str, str]]
  @dataclass(frozen=True)
  class LocalModelInfo:
      id: str
      profile: str
      vram: str
      size: str
      installed: bool
      recommended: bool
  class LocalModelManager:
      def get_models_dir(self) -> Path: ...
      def get_model_path(self, model_id: str) -> Path: ...
      def list_models(self, specs: DeviceSpecs | None = None) -> list[LocalModelInfo]: ...
      def is_installed(self, model_id: str) -> bool: ...
      def download_url(self, model_id: str) -> str: ...
  ```

- [ ] **Step 1: Write failing tests for GGML `LocalModelManager`**

Update `tests/unit/test_model_manager.py`:
```python
from pathlib import Path
from subforge.app.device import DeviceSpecs
from subforge.app.model_manager import GGML_WHISPER_MODELS, LocalModelInfo, LocalModelManager


def test_ggml_whisper_models_metadata():
    assert "large-v3-turbo" in GGML_WHISPER_MODELS
    assert "small" in GGML_WHISPER_MODELS
    assert "base" in GGML_WHISPER_MODELS
    assert "tiny" in GGML_WHISPER_MODELS
    assert GGML_WHISPER_MODELS["large-v3-turbo"]["filename"] == "ggml-large-v3-turbo.bin"


def test_list_models_with_recommendation(tmp_path: Path):
    manager = LocalModelManager(models_dir=tmp_path)
    specs = DeviceSpecs(ram_gb=16.0, cpu_cores=8)
    models = manager.list_models(specs=specs)

    turbo = next(m for m in models if m.id == "large-v3-turbo")
    assert turbo.recommended is True
    assert turbo.installed is False

    small = next(m for m in models if m.id == "small")
    assert small.recommended is False


def test_is_installed_and_get_model_path(tmp_path: Path):
    manager = LocalModelManager(models_dir=tmp_path)
    assert not manager.is_installed("base")

    # Create dummy model file
    model_file = tmp_path / "ggml-base.bin"
    model_file.write_bytes(b"dummy model weights")

    assert manager.is_installed("base")
    assert manager.get_model_path("base") == model_file


def test_download_url():
    manager = LocalModelManager()
    url = manager.download_url("small")
    assert url == "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_model_manager.py -v`
Expected: FAIL

- [ ] **Step 3: Update `src/subforge/app/model_manager.py`**

```python
"""Discovery and management of local GGML Whisper models for whisper.cpp."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from subforge.app.device import DeviceDetector, DeviceSpecs

GGML_WHISPER_MODELS: dict[str, dict[str, str]] = {
    "tiny": {
        "profile": "Ultra-light",
        "vram": "~500 MB RAM",
        "size": "~75 MB",
        "filename": "ggml-tiny.bin",
    },
    "base": {
        "profile": "Lightweight",
        "vram": "~1 GB RAM",
        "size": "~142 MB",
        "filename": "ggml-base.bin",
    },
    "small": {
        "profile": "Balanced",
        "vram": "~2 GB RAM",
        "size": "~466 MB",
        "filename": "ggml-small.bin",
    },
    "medium": {
        "profile": "High Quality",
        "vram": "~5 GB RAM",
        "size": "~1.5 GB",
        "filename": "ggml-medium.bin",
    },
    "large-v3-turbo": {
        "profile": "Optimal Quality",
        "vram": "~4 GB RAM",
        "size": "~800 MB",
        "filename": "ggml-large-v3-turbo.bin",
    },
    "large-v3": {
        "profile": "Maximum Quality",
        "vram": "~8 GB RAM",
        "size": "~3.1 GB",
        "filename": "ggml-large-v3.bin",
    },
}

# Compatibility alias for legacy tests
KNOWN_WHISPER_MODELS = GGML_WHISPER_MODELS

HUGGINGFACE_GGML_BASE_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"


@dataclass(frozen=True)
class LocalModelInfo:
    id: str
    profile: str
    vram: str
    size: str
    installed: bool
    recommended: bool = False


def default_models_dir() -> Path:
    env = os.environ.get("SUBFORGE_MODELS_DIR")
    if env:
        return Path(env)
    if os.name == "nt":
        app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(app_data) / "subforge" / "models"
    return Path.home() / ".local" / "share" / "subforge" / "models"


class LocalModelManager:
    def __init__(self, models_dir: Path | None = None) -> None:
        self.models_dir = models_dir or default_models_dir()

    def get_models_dir(self) -> Path:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        return self.models_dir

    def get_model_path(self, model_id: str) -> Path:
        meta = GGML_WHISPER_MODELS.get(model_id)
        if not meta:
            raise ValueError(f"[ERROR] unknown model ID: {model_id}")
        return self.models_dir / meta["filename"]

    def is_installed(self, model_id: str) -> bool:
        try:
            path = self.get_model_path(model_id)
            return path.exists() and path.stat().st_size > 0
        except ValueError:
            return False

    def download_url(self, model_id: str) -> str:
        meta = GGML_WHISPER_MODELS.get(model_id)
        if not meta:
            raise ValueError(f"[ERROR] unknown model ID: {model_id}")
        return f"{HUGGINGFACE_GGML_BASE_URL}/{meta['filename']}"

    def list_models(self, specs: DeviceSpecs | None = None) -> list[LocalModelInfo]:
        dev_specs = specs or DeviceDetector.get_specs()
        recommended_id = DeviceDetector.recommend_model(dev_specs)
        infos = []
        for model_id, meta in GGML_WHISPER_MODELS.items():
            installed = self.is_installed(model_id)
            is_rec = model_id == recommended_id
            infos.append(
                LocalModelInfo(
                    id=model_id,
                    profile=meta["profile"],
                    vram=meta["vram"],
                    size=meta["size"],
                    installed=installed,
                    recommended=is_rec,
                )
            )
        return infos
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_model_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/app/model_manager.py tests/unit/test_model_manager.py
git commit -m "feat: implement GGML LocalModelManager with device recommendation"
```

---

### Task 3: Native `WhisperCppProvider` Implementation

**Files:**
- Create: `src/subforge/providers/transcription/whisper_cpp.py`
- Test: `tests/unit/test_whisper_cpp_provider.py`

**Interfaces:**
- Consumes: `Transcript`, `TranscriptSegment` from `subforge.models.transcript`, `LocalModelManager` from `subforge.app.model_manager`
- Produces:
  ```python
  class WhisperCppProvider:
      def __init__(self, model: str = "large-v3-turbo", binary_path: str = "", models_dir: Path | None = None) -> None: ...
      def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript: ...
  ```

- [ ] **Step 1: Write failing unit tests for `WhisperCppProvider`**

`tests/unit/test_whisper_cpp_provider.py`:
```python
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from subforge.models.transcript import Transcript
from subforge.providers.registry import REGISTRY
from subforge.providers.transcription.whisper_cpp import WhisperCppProvider


def test_provider_registration():
    provider_cls = REGISTRY.resolve_transcription("local-whisper-cpp")
    assert provider_cls is WhisperCppProvider
    default_cls = REGISTRY.resolve_transcription("local")
    assert default_cls is WhisperCppProvider


def test_missing_model_raises_error(tmp_path: Path):
    provider = WhisperCppProvider(model="small", models_dir=tmp_path)
    with pytest.raises(RuntimeError, match="Model file not found"):
        provider.transcribe(tmp_path / "audio.wav")


def test_transcribe_successful_parsing(tmp_path: Path):
    model_file = tmp_path / "ggml-small.bin"
    model_file.write_bytes(b"dummy")

    provider = WhisperCppProvider(model="small", models_dir=tmp_path, binary_path="whisper-cli")
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"RIFF....WAVE")

    mock_json_output = {
        "result": {"language": "en"},
        "transcription": [
            {
                "offsets": {"from": 0, "to": 2500},
                "text": "Hello world.",
            },
            {
                "offsets": {"from": 2500, "to": 5100},
                "text": "Testing whisper.cpp local transcription.",
            },
        ],
    }

    def fake_run(cmd, *args, **kwargs):
        # cmd: whisper-cli -m ... -of <prefix> --output-json-full
        if "--output-json-full" in cmd:
            of_idx = cmd.index("-of")
            out_prefix = cmd[of_idx + 1]
            out_json = Path(f"{out_prefix}.json")
            out_json.write_text(json.dumps(mock_json_output), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        transcript = provider.transcribe(audio_path, language="en")

    assert isinstance(transcript, Transcript)
    assert transcript.language == "en"
    assert len(transcript.segments) == 2
    assert transcript.segments[0].id == 0
    assert transcript.segments[0].start == 0.0
    assert transcript.segments[0].end == 2.5
    assert transcript.segments[0].text == "Hello world."
    assert transcript.segments[1].id == 1
    assert transcript.segments[1].start == 2.5
    assert transcript.segments[1].end == 5.1
    assert transcript.segments[1].text == "Testing whisper.cpp local transcription."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_whisper_cpp_provider.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `WhisperCppProvider` in `src/subforge/providers/transcription/whisper_cpp.py`**

```python
"""Local whisper.cpp transcription provider (PRD §8, ARCH §7)."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from subforge.app.model_manager import LocalModelManager
from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.registry import REGISTRY


def find_whisper_cli(custom_path: str = "") -> str:
    if custom_path and (Path(custom_path).exists() or shutil.which(custom_path)):
        return custom_path

    # Standard app bin directories
    candidates = []
    if os.name == "nt":
        app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        candidates.append(Path(app_data) / "subforge" / "bin" / "whisper-cli.exe")
        candidates.append(Path(app_data) / "subforge" / "bin" / "main.exe")
    else:
        candidates.append(Path.home() / ".local" / "share" / "subforge" / "bin" / "whisper-cli")
        candidates.append(Path.home() / ".local" / "share" / "subforge" / "bin" / "main")

    for c in candidates:
        if c.exists():
            return str(c)

    # PATH checks
    for name in ["whisper-cli", "whisper-cpp", "whisper.cpp", "main"]:
        which_path = shutil.which(name)
        if which_path:
            return which_path

    return "whisper-cli"


def ensure_16khz_wav(audio_path: Path, temp_dir: Path) -> Path:
    """Convert audio to 16kHz 16-bit mono WAV using ffmpeg if needed."""
    if audio_path.suffix.lower() == ".wav":
        # Check or convert anyway to ensure 16kHz mono
        pass
    out_wav = temp_dir / f"conv_{audio_path.stem}.wav"
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(audio_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(out_wav),
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if res.returncode == 0 and out_wav.exists():
            return out_wav
    except Exception:
        pass
    return audio_path  # fallback to original if ffmpeg is missing or failed


class WhisperCppProvider:
    def __init__(
        self,
        model: str = "large-v3-turbo",
        binary_path: str = "",
        models_dir: Path | None = None,
    ) -> None:
        self.model_name = model
        self.binary_path = binary_path
        self.model_manager = LocalModelManager(models_dir=models_dir)

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        if not self.model_manager.is_installed(self.model_name):
            raise RuntimeError(
                f"Model file not found for '{self.model_name}'. "
                "Download it first in Settings or the Setup Wizard."
            )

        model_file = self.model_manager.get_model_path(self.model_name)
        cli_bin = find_whisper_cli(self.binary_path)

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            wav_path = ensure_16khz_wav(audio_path, tmp_dir)
            out_prefix = tmp_dir / "transcript_out"

            cmd = [
                cli_bin,
                "-m",
                str(model_file),
                "-f",
                str(wav_path),
                "-of",
                str(out_prefix),
                "--output-json-full",
            ]
            if language:
                cmd.extend(["-l", language])

            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"whisper-cli executable not found at '{cli_bin}'. "
                    "Install whisper.cpp or set the binary path in Settings."
                ) from exc

            json_file = tmp_dir / f"{out_prefix.name}.json"
            if not json_file.exists():
                raise RuntimeError(
                    f"whisper-cli failed to produce JSON output (exit code {proc.returncode}): {proc.stderr}"
                )

            data = json.loads(json_file.read_text(encoding="utf-8"))

        detected_lang = data.get("result", {}).get("language", language or "")
        raw_segments = data.get("transcription", [])

        segments = []
        for i, item in enumerate(raw_segments):
            # offsets in whisper.cpp full json are in milliseconds
            offsets = item.get("offsets", {})
            start_sec = float(offsets.get("from", 0)) / 1000.0
            end_sec = float(offsets.get("to", 0)) / 1000.0
            text = str(item.get("text", "")).strip()
            segments.append(
                TranscriptSegment(
                    id=i,
                    start=start_sec,
                    end=end_sec,
                    text=text,
                )
            )

        return Transcript(language=detected_lang, segments=segments)


REGISTRY.register_transcription("local-whisper-cpp", WhisperCppProvider)
REGISTRY.register_transcription("local", WhisperCppProvider)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_whisper_cpp_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/providers/transcription/whisper_cpp.py tests/unit/test_whisper_cpp_provider.py
git commit -m "feat: implement WhisperCppProvider and register in REGISTRY"
```

---

### Task 4: Configuration & Provider Factory Updates

**Files:**
- Modify: `src/subforge/config/app_config.py`
- Modify: `src/subforge/app/provider_factory.py`
- Modify: `src/subforge/providers/transcription/__init__.py`
- Modify: `tests/unit/test_app_config.py`
- Modify: `tests/unit/test_provider_factory.py`
- Modify: `tests/unit/test_transcription_providers.py`
- Delete / Refactor: `src/subforge/providers/transcription/whisperx.py`, `src/subforge/providers/transcription/openai.py`, `tests/unit/test_openai_transcription.py`

- [ ] **Step 1: Update `TranscriptionConfig` in `src/subforge/config/app_config.py`**

```python
class TranscriptionConfig(BaseModel):
    provider: Literal["local"] = "local"
    model: str = "large-v3-turbo"
    language: str = ""  # audio source language ("": auto-detect)
    binary_path: str = ""  # optional custom path to whisper-cli
    models_dir: str = ""  # optional custom models dir
```

- [ ] **Step 2: Update `src/subforge/app/provider_factory.py`**

```python
from subforge.providers.transcription.whisper_cpp import WhisperCppProvider

def build_transcription_provider(cfg: AppConfig) -> WhisperCppProvider:
    tc = cfg.transcription
    if not tc.model:
        raise ValueError("[ERROR] no local transcription model selected — pick one in Settings")
    models_dir = Path(tc.models_dir) if tc.models_dir else None
    return WhisperCppProvider(model=tc.model, binary_path=tc.binary_path, models_dir=models_dir)
```

- [ ] **Step 3: Update `src/subforge/providers/transcription/__init__.py` to export `WhisperCppProvider`**

- [ ] **Step 4: Update test files `tests/unit/test_app_config.py`, `test_provider_factory.py`, `test_transcription_providers.py`**

- [ ] **Step 5: Run tests to verify all pass**

Run: `uv run pytest tests/unit/test_app_config.py tests/unit/test_provider_factory.py tests/unit/test_transcription_providers.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/subforge/config/app_config.py src/subforge/app/provider_factory.py src/subforge/providers/ tests/
git commit -m "refactor: update transcription config and provider factory to whisper.cpp"
```

---

### Task 5: Setup Wizard & Settings Screen Updates

**Files:**
- Modify: `src/subforge/tui/screens/setup_wizard.py`
- Modify: `src/subforge/tui/screens/settings.py`
- Modify: `tests/unit/test_setup_wizard.py`
- Modify: `tests/unit/test_settings_screen.py`

- [ ] **Step 1: Update `FirstRunSetupScreen` in `src/subforge/tui/screens/setup_wizard.py`**
  - In `begin_transcription_choice()`, directly show `ModelPickerScreen` loaded with GGML models containing recommendation badges (e.g. `large-v3-turbo · Optimal Quality (~800 MB) [RECOMMENDED]`).
  - Next, ask for source language via `LanguagePickerScreen`.
  - Next, transition to translation setup step 2.

- [ ] **Step 2: Update `SettingsScreen` in `src/subforge/tui/screens/settings.py`**
  - Transcribe section picks GGML models with `[RECOMMENDED]` badge.
  - Remove OpenAI transcription API key input.

- [ ] **Step 3: Update and fix unit tests in `tests/unit/test_setup_wizard.py` and `tests/unit/test_settings_screen.py`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_setup_wizard.py tests/unit/test_settings_screen.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/subforge/tui/screens/ tests/unit/test_setup_wizard.py tests/unit/test_settings_screen.py
git commit -m "feat: update setup wizard and settings screen for always-local whisper.cpp"
```

---

### Task 6: Dependencies, Cross-Platform Fixes, E2E Integration & Docs Sync

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/integration/test_full_flow.py`
- Modify: `docs/PRD.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Clean `pyproject.toml`**
  - Remove `[project.optional-dependencies] local = ["whisperx>=3.1"]`.

- [ ] **Step 2: Update `tests/integration/test_full_flow.py` and cross-platform test assertions**
  - Assert end-to-end flow with `WhisperCppProvider` mock and translation service.

- [ ] **Step 3: Update `docs/PRD.md` and `docs/ARCHITECTURE.md`**
  - Document `whisper.cpp` always-local architecture, hardware profiling, and removal of cloud audio transcription.

- [ ] **Step 4: Run full verification suite**

Run:
```bash
uv run pytest tests/ -v
uv run ruff check src tests
uv run mypy src
```
Expected: All gates PASS cleanly with 0 errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml docs/ tests/ src/
git commit -m "chore: finalize whisper.cpp transition, update docs and e2e tests"
```
