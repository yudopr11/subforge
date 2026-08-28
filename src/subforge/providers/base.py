"""Provider interfaces. The application core depends ONLY on these (ARCH §5, §37 P1)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from subforge.models.transcript import Transcript


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
    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        translate: bool = False,
    ) -> Transcript: ...


# Alias kept for tests/readability; same interface object.
TranscriptionLike = TranscriptionProvider


@runtime_checkable
class TranslationProvider(Protocol):
    def translate(
        self,
        segments: list[TranslationInput],
        source_language: str,
        target_language: str,
        reasoning_effort: str | None = None,
    ) -> list[TranslationOutput]: ...
