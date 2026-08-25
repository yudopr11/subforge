import pytest

from subforge.app.provider_factory import (
    build_transcription_provider,
    build_translation_provider,
    validate_reasoning_choice,
)
from subforge.config.app_config import AppConfig
from subforge.providers.capabilities import ReasoningSpec
from subforge.providers.transcription.whisperx import WhisperXProvider


def test_local_transcription_needs_model():
    with pytest.raises(ValueError, match="no local transcription model"):
        build_transcription_provider(AppConfig())  # provider=local, model=""


def test_local_transcription_builds_whisperx():
    cfg = AppConfig(transcription={"provider": "local", "model": "small"})
    provider = build_transcription_provider(cfg)
    assert isinstance(provider, WhisperXProvider)
    assert provider.model_name == "small"


def test_openai_transcription_requires_key_and_model():
    cfg = AppConfig(transcription={"provider": "openai", "model": "", "api_key": "sk"})
    with pytest.raises(ValueError, match="model"):
        build_transcription_provider(cfg)
    cfg2 = AppConfig(transcription={"provider": "openai", "model": "whisper-1", "api_key": ""})
    with pytest.raises(ValueError, match="API key"):
        build_transcription_provider(cfg2)


def test_openai_transcription_built_with_key_and_model():
    cfg = AppConfig(transcription={"provider": "openai", "model": "gpt-4o-transcribe", "api_key": "sk-x"})
    p = build_transcription_provider(cfg)
    assert p.api_key == "sk-x" and p.model_name == "gpt-4o-transcribe"


def test_unknown_transcription_provider_rejected():
    cfg = AppConfig()  # literal typing rejects unknowns at the config boundary;
    cfg.transcription.provider = "deepgram"  # this tests the factory's defensive branch
    with pytest.raises(ValueError, match="unknown transcription provider"):
        build_transcription_provider(cfg)


def test_local_translation_uses_custom_url_and_optional_key():
    cfg = AppConfig(
        translation={"source": "local", "local_base_url": "http://localhost:1234/v1", "model": "qwen3-14b"}
    )
    p = build_translation_provider(cfg)
    assert p.base_url == "http://localhost:1234/v1"
    assert p.api_key == ""  # LM Studio / Ollama usually need none
    assert p.model == "qwen3-14b"


def test_local_translation_requires_url_and_model():
    cfg = AppConfig(translation={"source": "local", "local_base_url": "", "model": "m"})
    with pytest.raises(ValueError, match="base URL"):
        build_translation_provider(cfg)
    cfg2 = AppConfig(translation={"source": "local", "local_base_url": "http://x", "model": ""})
    with pytest.raises(ValueError, match="model"):
        build_translation_provider(cfg2)


def test_opencode_go_translation():
    cfg = AppConfig(
        translation={
            "source": "provider",
            "provider": "opencode-go",
            "api_key": "oc-k",
            "model": "glm-5.2",
            "reasoning_effort": "max",
        }
    )
    p = build_translation_provider(cfg)
    assert p.base_url == "https://opencode.ai/zen/go/v1"
    assert p.api_key == "oc-k"
    assert p.model == "glm-5.2"


def test_provider_translation_requires_key_and_model():
    cfg = AppConfig(translation={"source": "provider", "provider": "openai", "api_key": "", "model": "gpt-5.6-luna"})
    with pytest.raises(ValueError, match="API key"):
        build_translation_provider(cfg)
    cfg2 = AppConfig(translation={"source": "provider", "provider": "openai", "api_key": "k", "model": ""})
    with pytest.raises(ValueError, match="model"):
        build_translation_provider(cfg2)


def test_validate_reasoning_choice_drops_stale_values():
    spec = ReasoningSpec("effort", ("high", "max"))
    assert validate_reasoning_choice(spec, "max") == "max"
    assert validate_reasoning_choice(spec, "low") == ""  # not offered by THIS model
    assert validate_reasoning_choice(ReasoningSpec("unsupported", ()), "high") == ""
