from pathlib import Path

import pytest

from subforge.providers.registry import REGISTRY
from subforge.providers.transcription.whisper_cpp import WhisperCppProvider


def test_whisper_cpp_missing_model_message(tmp_path: Path) -> None:
    provider = WhisperCppProvider(model="base", models_dir=tmp_path)
    with pytest.raises(RuntimeError, match="Model file not found"):
        provider.transcribe(Path("a.wav"))


def test_registered_names() -> None:
    assert REGISTRY.resolve_transcription("local-whisper-cpp") is WhisperCppProvider
    assert REGISTRY.resolve_transcription("local") is WhisperCppProvider
