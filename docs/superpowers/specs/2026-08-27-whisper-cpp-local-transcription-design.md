# Design Spec: Always-Local Transcription via `whisper.cpp` & Hardware-Aware Model Recommendation

**Date:** 2026-08-27  
**Status:** Draft  
**Target:** SubForge v0.3.0  

---

## 1. Overview & Goals

SubForge is designed as a local-first subtitle generation and translation tool. Previously, the transcription architecture relied on heavy Python ML libraries (`whisperx`, `torch`, `torchaudio`, `transformers`, `huggingface-hub`), which introduced ~4–8 GB of dependency bloat, or cloud audio APIs (`openai`), which violated the offline-first privacy goal.

This architectural change:
1. Replaces `WhisperX` and cloud `OpenAI` transcription providers with a lightweight, native, always-local **`whisper.cpp`** execution engine.
2. Eliminates all heavy PyTorch and ML dependencies from `pyproject.toml`, keeping the core Python environment under 50 MB.
3. Automatically detects host hardware (system RAM, CPU cores) to recommend and badge the optimal Whisper GGML model (`tiny`, `base`, `small`, `medium`, `large-v3-turbo`, `large-v3`) during setup and settings.
4. Updates the TUI Setup Wizard and Settings screens to streamline always-local transcription setup.
5. Keeps translation functionality (local LM Studio / Ollama + cloud OpenAI / OpenCode) fully intact.

---

## 2. Architecture & Subsystems

```
┌─────────────────────────────────────────────────────────────┐
│                    SubForge TUI / CLI                       │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌─────────────────────────┐             ┌─────────────────────┐
│    DeviceDetector       │             │  LocalModelManager  │
│  (RAM / CPU profiling)  │             │  (GGML models, dl)  │
└───────────┬─────────────┘             └──────────┬──────────┘
            │ recommendations                      │ model path
            ▼                                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     Pipeline (app/pipeline.py)              │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │   Transcription Stage: WhisperCppProvider             │  │
│  │                                                       │  │
│  │   Input Audio ──► (ffmpeg decode to 16kHz WAV)        │  │
│  │               ──► whisper-cli --output-json-full      │  │
│  │               ──► Parse segments to Transcript        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │   Translation Stage: TranslationService               │  │
│  │   (OpenAI-Compatible: LM Studio / Ollama / Cloud)     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Provider Protocol Implementation (`WhisperCppProvider`)
- Implements `TranscriptionProvider` protocol from `src/subforge/providers/base.py`.
- Registered in `src/subforge/providers/registry.py` under `"local-whisper-cpp"` (and alias `"local"`).
- **Execution Flow**:
  1. Locates `whisper-cli` executable:
     - Configured path in `TranscriptionConfig.binary_path`, or
     - Standard app directory (`~/.local/share/subforge/bin/whisper-cli` / `%LOCALAPPDATA%\subforge\bin\whisper-cli.exe`), or
     - System `PATH` (`whisper-cli`, `whisper-cpp`, `whisper.cpp`, `main`).
  2. If the audio input is not a 16kHz 16-bit mono WAV, automatically converts it using `ffmpeg` (or `ffmpeg` on PATH) to a temporary WAV file.
  3. Executes `whisper-cli` with parameters:
     `-m <model_path> -f <wav_path> --output-json-full -of <output_prefix> [-l <language>]`
  4. Parses the generated JSON output containing timestamps (`start`, `end` in milliseconds or seconds) and text into canonical `TranscriptSegment` and `Transcript` objects.
  5. Cleans up temporary conversion files.

### 2.2 Hardware Detection & Recommendation Engine (`DeviceDetector`)
- Located in `src/subforge/app/device.py`.
- Detects:
  - System total RAM in gigabytes (cross-platform via `psutil` or `ctypes`/`sysinfo`/`os`).
  - CPU logical and physical core count (`os.cpu_count()`).
- Decision Matrix:
  | Detected Hardware | Recommended Model | Rationale |
  | :--- | :--- | :--- |
  | RAM < 6 GB or CPU cores ≤ 2 | `tiny` | Minimal memory footprint (~75 MB model, ~300 MB RAM) |
  | RAM 6–10 GB or CPU cores 4 | `base` | Fast CPU transcription (~140 MB model, ~1 GB RAM) |
  | RAM 10–16 GB or CPU cores 6–8 | `small` | Excellent balance of speed and accuracy (~460 MB model) |
  | RAM 16–32 GB or CPU cores ≥ 8 | `large-v3-turbo` | High accuracy with fast inference (~800 MB model) |
  | RAM > 32 GB or High-end Workstation | `large-v3` | Highest precision for multilingual / complex audio (~3.1 GB model) |

### 2.3 Model Management (`LocalModelManager`)
- Located in `src/subforge/app/model_manager.py`.
- Tracks supported GGML Whisper models:
  - `tiny`: `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin`
  - `base`: `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin`
  - `small`: `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin`
  - `medium`: `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin`
  - `large-v3-turbo`: `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin`
  - `large-v3`: `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin`
- Models are stored in `subforge` app data directory (`~/.local/share/subforge/models/` or `%LOCALAPPDATA%\subforge\models\`).
- Model download uses standard streaming HTTP requests with byte progress reporting without external heavy dependencies.

---

## 3. Configuration & Schema Changes

### 3.1 `TranscriptionConfig` in `src/subforge/config/app_config.py`
```python
class TranscriptionConfig(BaseModel):
    model: str = "large-v3-turbo"  # default or detected recommended model
    language: str = ""             # "": auto-detect
    binary_path: str = ""          # optional custom path to whisper-cli
    models_dir: str = ""           # optional custom models directory
```
*Note: `provider` is eliminated or locked to `"local"` because transcription is always local. `api_key` is removed from transcription config.*

---

## 4. UI / UX Flow Changes

### 4.1 First-Run Setup Wizard (`FirstRunSetupScreen`)
- **Step 1: Transcription Setup**:
  - Automatically runs `DeviceDetector.get_specs()` and `DeviceDetector.recommend_model()`.
  - Directly shows the Model Picker listing GGML models with size and profile.
  - The recommended model displays a `[RECOMMENDED]` badge and is pre-selected.
  - Prompts for audio source language (default blank for auto-detect).
  - Checks if the selected model file exists locally; if not, prompts to download it immediately with progress bar.
- **Step 2: Translation Setup**:
  - Remains intact: Local (LM Studio / Ollama) or Cloud (OpenAI, OpenCode Zen, OpenCode Go).

### 4.2 Settings Screen (`SettingsScreen`)
- **Transcribe Section**:
  - Select active model with `[RECOMMENDED]` badge indicator.
  - Open Model Manager to download/delete GGML model files.
  - Set source language.
  - Set optional custom `whisper-cli` binary path.

---

## 5. Dependencies & Packaging Changes

- Remove from `pyproject.toml`:
  - `whisperx`
  - `[project.optional-dependencies] local = ["whisperx>=3.1"]`
- No heavy C++/CUDA/PyTorch packages required in Python environment.

---

## 6. Testing & Quality Strategy

1. **Unit Tests**:
   - `test_device_detector.py`: Tests hardware profiling and model recommendations across various RAM and CPU core combinations.
   - `test_whisper_cpp_provider.py`: Tests command-line assembly, subprocess invocation, ffmpeg audio conversion fallback, output JSON parsing into `TranscriptSegment` objects, and error handling when binary or model is missing.
   - `test_model_manager.py`: Tests GGML model metadata, download URL resolution, cache verification, and file download progress callbacks.
   - `test_setup_wizard.py`: Tests new first-run flow without cloud transcription choices and verifies recommendation badges.
   - `test_settings_screen.py`: Tests settings updates and model selection.
2. **Integration Tests**:
   - `test_full_flow.py`: Tests end-to-end pipeline transcription using a mock `whisper-cli` execution returning valid JSON timestamps and text, proceeding through translation to SRT and ASS subtitle exports.
3. **Quality Gates**:
   - `uv run pytest tests/`
   - `uv run ruff check src tests`
   - `uv run mypy src`
