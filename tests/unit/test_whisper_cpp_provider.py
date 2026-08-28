import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from subforge.models.transcript import Transcript
from subforge.providers.registry import REGISTRY
from subforge.providers.transcription.whisper_cpp import (
    WhisperCppProvider,
    ensure_16khz_wav,
    find_whisper_cli,
)


def test_provider_registration() -> None:
    provider_cls = REGISTRY.resolve_transcription("local-whisper-cpp")
    assert provider_cls is WhisperCppProvider
    default_cls = REGISTRY.resolve_transcription("local")
    assert default_cls is WhisperCppProvider


def test_find_whisper_cli_custom(tmp_path: Path) -> None:
    custom_bin = tmp_path / "custom-whisper"
    custom_bin.write_text("fake binary")
    assert find_whisper_cli(str(custom_bin)) == str(custom_bin)


def test_find_whisper_cli_fallback() -> None:
    with (
        patch("subforge.providers.transcription.whisper_cpp.default_bin_dir", return_value=Path("/nonexistent/bin")),
        patch("shutil.which", return_value="/usr/local/bin/whisper-cli"),
    ):
        assert Path(find_whisper_cli(auto_install=False)) == Path("/usr/local/bin/whisper-cli")

    with (
        patch("subforge.providers.transcription.whisper_cpp.default_bin_dir", return_value=Path("/nonexistent/bin")),
        patch("shutil.which", return_value=None),
        patch("pathlib.Path.exists", return_value=False),
    ):
        assert find_whisper_cli(auto_install=False) == "whisper-cli"


def test_ensure_16khz_wav_conversion(tmp_path: Path) -> None:
    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"dummy mp3 data")
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()

    conv_target = temp_dir / "conv_sample.wav"

    def fake_ffmpeg(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        conv_target.write_bytes(b"RIFF dummy wav")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")

    with patch("subprocess.run", side_effect=fake_ffmpeg):
        out_wav = ensure_16khz_wav(audio_path, temp_dir)
        assert out_wav == conv_target
        assert out_wav.exists()


def test_ensure_16khz_wav_fallback_on_error(tmp_path: Path) -> None:
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"dummy wav data")
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()

    with patch("subprocess.run", side_effect=FileNotFoundError):
        out_wav = ensure_16khz_wav(audio_path, temp_dir)
        assert out_wav == audio_path


def test_missing_model_raises_error(tmp_path: Path) -> None:
    provider = WhisperCppProvider(model="small", models_dir=tmp_path)
    with pytest.raises(RuntimeError, match="Model file not found"):
        provider.transcribe(tmp_path / "audio.wav")


def test_missing_binary_raises_error(tmp_path: Path) -> None:
    model_file = tmp_path / "ggml-small.bin"
    model_file.write_bytes(b"dummy")

    provider = WhisperCppProvider(model="small", models_dir=tmp_path, binary_path="nonexistent-whisper")
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"RIFF....WAVE")

    with (
        patch("subprocess.run", side_effect=FileNotFoundError("not found")),
        pytest.raises(RuntimeError, match="whisper-cli executable not found"),
    ):
        provider.transcribe(audio_path)


def test_process_failure_raises_error(tmp_path: Path) -> None:
    model_file = tmp_path / "ggml-small.bin"
    model_file.write_bytes(b"dummy")

    provider = WhisperCppProvider(model="small", models_dir=tmp_path)
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"RIFF....WAVE")

    mock_proc = subprocess.CompletedProcess([], returncode=1, stdout="", stderr="Error: model crashed")
    with (
        patch("subprocess.run", return_value=mock_proc),
        pytest.raises(RuntimeError, match="whisper-cli failed to produce JSON output"),
    ):
        provider.transcribe(audio_path)


def test_transcribe_successful_parsing(tmp_path: Path) -> None:
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

    captured_cmds: list[list[str]] = []

    def fake_run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_cmds.append(cmd)
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


def test_transcribe_with_translate_flag(tmp_path: Path) -> None:
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
                "text": "Hello world in English.",
            }
        ],
    }

    captured_cmds: list[list[str]] = []

    def fake_run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_cmds.append(cmd)
        if "--output-json-full" in cmd:
            of_idx = cmd.index("-of")
            out_prefix = cmd[of_idx + 1]
            out_json = Path(f"{out_prefix}.json")
            out_json.write_text(json.dumps(mock_json_output), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        transcript = provider.transcribe(audio_path, language="id", translate=True)

    assert any("-tr" in cmd for cmd in captured_cmds)
    assert transcript.segments[0].text == "Hello world in English."
    assert transcript.segments[0].start == 0.0
    assert transcript.segments[0].end == 2.5
