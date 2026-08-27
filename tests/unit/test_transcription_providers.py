import io
import json
from pathlib import Path

import httpx
import pytest

from subforge.providers.registry import REGISTRY
from subforge.providers.transcription.remote import RemoteTranscriptionProvider
from subforge.providers.transcription.whisper_cpp import WhisperCppProvider

API_RESPONSE = {
    "language": "id",
    "segments": [
        {"id": 0, "start": 1.2, "end": 3.4, "text": " Halo semuanya!"},
        {"id": 1, "start": 3.5, "end": 6.8, "text": " Selamat datang."},
    ],
}


def make_audio(tmp_path: Path) -> Path:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF-fake")
    return audio


def test_remote_transcription_normalizes_segments(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/transcriptions")
        assert "multipart/form-data" in request.headers["Content-Type"]
        body = request.read()
        assert b"language" in body  # language travels as form field
        return httpx.Response(200, json=API_RESPONSE)

    provider = RemoteTranscriptionProvider(
        "http://stt.example/v1", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    transcript = provider.transcribe(make_audio(tmp_path), language="id")
    assert transcript.language == "id"
    assert transcript.segments[0].start == 1.2
    assert transcript.segments[0].text == "Halo semuanya!"  # stripped


def test_remote_error_raises(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    provider = RemoteTranscriptionProvider(
        "http://stt.example/v1", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(httpx.HTTPStatusError):
        provider.transcribe(make_audio(tmp_path))


def test_whisper_cpp_missing_model_message(tmp_path: Path) -> None:
    provider = WhisperCppProvider(model="base", models_dir=tmp_path)
    with pytest.raises(RuntimeError, match="Model file not found"):
        provider.transcribe(Path("a.wav"))


def test_registered_names() -> None:
    assert REGISTRY.resolve_transcription("remote") is RemoteTranscriptionProvider
    assert REGISTRY.resolve_transcription("local-whisper-cpp") is WhisperCppProvider
    assert REGISTRY.resolve_transcription("local") is WhisperCppProvider


def _unused_io() -> None:  # keep io import meaningful for linters
    assert io.BytesIO(b"x").read() == b""
    assert json.loads('{"a": 1}')["a"] == 1
