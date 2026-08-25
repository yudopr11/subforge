"""Remote STT provider using an OpenAI-style /transcriptions endpoint (ARCH §10)."""

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
