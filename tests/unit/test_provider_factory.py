import pytest

from subforge.app.provider_factory import (
    build_pipeline,
    build_transcription_provider,
    transcription_configured,
)
from subforge.config.app_config import AppConfig
from subforge.providers.transcription.whisper_cpp import WhisperCppProvider


def test_local_transcription_needs_model():
    with pytest.raises(ValueError, match="no local transcription model"):
        build_transcription_provider(AppConfig(transcription={"model": ""}))


def test_local_transcription_builds_whisper_cpp():
    cfg = AppConfig(transcription={"provider": "local", "model": "small", "binary_path": "whisper-cli"})
    provider = build_transcription_provider(cfg)
    assert isinstance(provider, WhisperCppProvider)
    assert provider.model_name == "small"
    assert provider.binary_path == "whisper-cli"


def test_build_pipeline_sets_transcription_when_configured(tmp_path):
    cfg = AppConfig(transcription={"provider": "local", "model": "small"})
    pipe = build_pipeline(tmp_path, cfg)
    assert isinstance(pipe.transcription, WhisperCppProvider)


def test_transcription_configured_helper():
    empty = AppConfig()
    ready = AppConfig(transcription={"provider": "local", "model": "small"})
    assert transcription_configured(empty) is False
    assert transcription_configured(ready) is True
