import httpx
import pytest

from subforge.app.provider_factory import (
    build_pipeline,
    build_transcription_provider,
    build_translation_provider,
    build_translation_service,
    resolve_reasoning_effort,
    validate_reasoning_choice,
)
from subforge.config.app_config import AppConfig
from subforge.providers.capabilities import ReasoningSpec
from subforge.providers.transcription.whisperx import WhisperXProvider
from subforge.providers.translation.openai_compatible import OpenAICompatibleProvider


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


# ---- pipeline/service builders (TUI seam) -------------------------------


class _FakeCapClient:
    def __init__(self, spec):
        self._spec = spec
        self.calls: list[tuple[str, str]] = []

    def reasoning_spec(self, provider_preset, model_id):
        self.calls.append((provider_preset, model_id))
        return self._spec


def _cfg(**translation_kwargs):
    return AppConfig(
        translation={
            "source": "provider",
            "provider": "opencode-zen",
            "api_key": "k",
            "model": "glm-5.2",
            **translation_kwargs,
        }
    )


def test_resolve_reasoning_keeps_valid_value():
    client = _FakeCapClient(ReasoningSpec("effort", ("high", "max")))
    assert resolve_reasoning_effort(_cfg(reasoning_effort="high"), client) == "high"
    assert client.calls == [("opencode", "glm-5.2")]  # preset mapped via catalog id


def test_resolve_reasoning_drops_stale_and_local():
    stale = _FakeCapClient(ReasoningSpec("effort", ("low",)))
    assert resolve_reasoning_effort(_cfg(reasoning_effort="max"), stale) == ""

    local = AppConfig(translation={"source": "local", "local_base_url": "http://x/v1", "model": "qwen3-14b"})
    assert resolve_reasoning_effort(local, _FakeCapClient(ReasoningSpec("effort", ("max",)))) == ""


def test_resolve_reasoning_survives_network_failure():
    class Boom:
        def reasoning_spec(self, *_):
            raise httpx.ConnectError("offline")

    assert resolve_reasoning_effort(_cfg(reasoning_effort="max"), Boom()) == ""


def test_build_translation_service_wires_batch_size_and_effort():
    cfg = _cfg(batch_size=7, reasoning_effort="high")
    svc = build_translation_service(cfg, capability_client=_FakeCapClient(ReasoningSpec("effort", ("high", "max"))))
    assert isinstance(svc.provider, OpenAICompatibleProvider)
    assert svc.batch_size == 7
    assert svc.reasoning_effort == "high"


def test_build_translation_service_unconfigured_model_raises():
    with pytest.raises(ValueError, match="no translation model"):
        build_translation_service(AppConfig())


def test_build_pipeline_wires_providers_or_leaves_unset(tmp_path):
    from subforge.app.pipeline import Pipeline

    full_cfg = AppConfig(
        transcription={"provider": "local", "model": "small"},
        translation={"source": "local", "local_base_url": "http://x/v1", "model": "m"},
    )
    pipe = build_pipeline(tmp_path / "p", full_cfg)
    assert isinstance(pipe, Pipeline)
    assert isinstance(pipe.transcription, WhisperXProvider)
    assert isinstance(pipe.translation_service.provider, OpenAICompatibleProvider)

    empty = build_pipeline(tmp_path / "q", AppConfig())  # nothing configured yet
    assert empty.transcription is None  # run_transcription will raise StageError
    # translation_service falls back to the pipeline's unconfigured placeholder


def test_build_pipeline_diarization_passthrough(tmp_path):
    class D:
        def diarize(self, audio_path):
            return []

    pipe = build_pipeline(tmp_path / "p", AppConfig(), diarization=D())
    assert pipe.diarization is not None
