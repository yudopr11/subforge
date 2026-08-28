"""Provider interfaces. The application core depends ONLY on these (ARCH §5, §37 P1)."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from subforge.models.transcript import Transcript


@runtime_checkable
class TranscriptionProvider(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> Transcript: ...


# Alias kept for tests/readability; same interface object.
TranscriptionLike = TranscriptionProvider
