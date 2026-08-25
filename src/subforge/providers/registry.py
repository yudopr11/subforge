"""Dynamic provider resolution (ARCH §26). Adding a provider never changes the core."""

from collections.abc import Callable
from typing import Any


class ProviderRegistry:
    class ProviderNotFound(LookupError):
        pass

    def __init__(self) -> None:
        self._transcription: dict[str, Callable[..., Any]] = {}
        self._diarization: dict[str, Callable[..., Any]] = {}
        self._translation: dict[str, Callable[..., Any]] = {}

    def register_transcription(self, name: str, factory: Callable[..., Any]) -> None:
        self._transcription[name] = factory

    def register_diarization(self, name: str, factory: Callable[..., Any]) -> None:
        self._diarization[name] = factory

    def register_translation(self, name: str, factory: Callable[..., Any]) -> None:
        self._translation[name] = factory

    def resolve_transcription(self, name: str) -> Any:
        try:
            return self._transcription[name]
        except KeyError:
            raise self.ProviderNotFound(f"transcription provider not registered: {name}") from None

    def resolve_diarization(self, name: str) -> Any:
        try:
            return self._diarization[name]
        except KeyError:
            raise self.ProviderNotFound(f"diarization provider not registered: {name}") from None

    def resolve_translation(self, name: str) -> Any:
        try:
            return self._translation[name]
        except KeyError:
            raise self.ProviderNotFound(f"translation provider not registered: {name}") from None


REGISTRY = ProviderRegistry()
