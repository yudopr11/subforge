import pytest

from subforge.providers.base import (
    DiarizationTurn,
    TranscriptionLike,
    TranslationInput,
    TranslationOutput,
)
from subforge.providers.registry import ProviderRegistry


class FakeASR:
    def transcribe(self, audio_path, language=None):
        raise AssertionError("not called in tests")


def test_register_and_resolve_transcription():
    reg = ProviderRegistry()
    reg.register_transcription("fake", FakeASR)
    assert reg.resolve_transcription("fake") is FakeASR


def test_unknown_provider_raises():
    reg = ProviderRegistry()
    with pytest.raises(reg.ProviderNotFound):
        reg.resolve_transcription("nope")


def test_dataclasses():
    turn = DiarizationTurn(speaker="SPEAKER_00", start=1.2, end=3.4)
    inp = TranslationInput(id=42, text="halo")
    out = TranslationOutput(id=42, text="hello")
    assert turn.speaker.startswith("SPEAKER_") and inp.id == out.id == 42


def test_protocol_runtime_checkable():
    assert isinstance(FakeASR(), TranscriptionLike)
