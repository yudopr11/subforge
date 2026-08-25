"""OpenAI Audio API transcription — the only remote ASR provider in the MVP."""

from pathlib import Path
from typing import Any

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
    def _normalize(payload: dict[str, Any]) -> Transcript:
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
                segments = [TranscriptSegment(id=0, start=0.0, end=float(payload.get("duration", 0.0)), text=text)]
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
