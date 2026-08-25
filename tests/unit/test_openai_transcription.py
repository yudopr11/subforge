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
        api_key="k",
        model="gpt-4o-transcribe",
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

    provider = OpenAITranscriptionProvider(
        api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert provider.list_models() == ["gpt-4o-transcribe", "whisper-1"]


def test_registered_as_openai():
    assert REGISTRY.resolve_transcription("openai") is OpenAITranscriptionProvider
