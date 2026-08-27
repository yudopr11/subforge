"""Local whisper.cpp transcription provider (PRD §8, ARCH §7)."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from subforge.app.model_manager import LocalModelManager
from subforge.app.storage import get_bin_dir
from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.registry import REGISTRY


def default_bin_dir() -> Path:
    return get_bin_dir()


def install_whisper_cli_binaries(target_dir: Path | None = None) -> Path:
    """Download and install official pre-built whisper.cpp binaries (Windows x64)."""
    import io
    import zipfile

    import httpx

    dest_dir = target_dir or default_bin_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        url = "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-x64.zip"
        res = httpx.get(url, follow_redirects=True, timeout=60.0)
        res.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            for member in z.infolist():
                fn = member.filename.removeprefix("Release/")
                if fn and not fn.endswith("/"):
                    target_file = dest_dir / fn
                    target_file.write_bytes(z.read(member))
        cli_exe = dest_dir / "whisper-cli.exe"
        if cli_exe.exists():
            return cli_exe
    raise RuntimeError(
        "Auto-installation of whisper-cli is not supported on this platform. "
        "Please install whisper.cpp manually and add whisper-cli to your PATH."
    )


def find_whisper_cli(custom_path: str = "", auto_install: bool = True) -> str:
    if custom_path and (Path(custom_path).exists() or shutil.which(custom_path)):
        return custom_path

    # Standard app bin directories
    candidates: list[Path] = []
    bin_dir = default_bin_dir()
    if os.name == "nt":
        candidates.append(bin_dir / "whisper-cli.exe")
        candidates.append(bin_dir / "main.exe")
    else:
        candidates.append(bin_dir / "whisper-cli")
        candidates.append(bin_dir / "main")

    for c in candidates:
        if c.exists():
            return str(c)

    # PATH checks (avoid bare 'main' on Windows matching system32/main.cpl)
    names = (
        ["whisper-cli.exe", "whisper-cli", "whisper-cpp.exe", "whisper-cpp"]
        if os.name == "nt"
        else ["whisper-cli", "whisper-cpp", "whisper.cpp", "main"]
    )
    for name in names:
        which_path = shutil.which(name)
        if which_path and not which_path.lower().endswith((".cpl", ".dll")):
            return which_path

    # If missing on Windows, attempt auto-install if enabled
    if auto_install and os.name == "nt":
        try:
            return str(install_whisper_cli_binaries(bin_dir))
        except Exception:  # noqa: BLE001, S110
            pass

    return "whisper-cli"


def ensure_16khz_wav(audio_path: Path, temp_dir: Path) -> Path:
    """Convert audio to 16kHz 16-bit mono WAV using ffmpeg if needed."""
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
        res = subprocess.run(cmd, capture_output=True, check=False)
        if res.returncode == 0 and out_wav.exists():
            return out_wav
    except Exception:  # noqa: BLE001, S110
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
                    capture_output=True,
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
