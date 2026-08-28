"""Dynamic provider resolution (ARCH §26). Adding a provider never changes the core."""

from collections.abc import Callable
from typing import Any


class ProviderRegistry:
    class ProviderNotFound(LookupError):
        pass

    def __init__(self) -> None:
        self._transcription: dict[str, Callable[..., Any]] = {}

    def register_transcription(self, name: str, factory: Callable[..., Any]) -> None:
        self._transcription[name] = factory

    def resolve_transcription(self, name: str) -> Any:
        try:
            return self._transcription[name]
        except KeyError:
            raise self.ProviderNotFound(f"transcription provider not registered: {name}") from None


REGISTRY = ProviderRegistry()
