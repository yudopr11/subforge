"""Build concrete providers from the TUI-authored AppConfig.

Core pipeline modules never import this — they receive ready provider objects.
"""

from subforge.config.app_config import AppConfig
from subforge.config.providers import TRANSLATION_PRESETS
from subforge.providers.capabilities import ReasoningSpec
from subforge.providers.transcription.openai import OpenAITranscriptionProvider
from subforge.providers.transcription.whisperx import WhisperXProvider
from subforge.providers.translation.openai_compatible import OpenAICompatibleProvider


def build_transcription_provider(cfg: AppConfig) -> WhisperXProvider | OpenAITranscriptionProvider:
    tc = cfg.transcription
    if tc.provider == "local":
        if not tc.model:
            raise ValueError("[ERROR] no local transcription model selected — pick one in Settings")
        return WhisperXProvider(model=tc.model)
    if tc.provider == "openai":
        if not tc.model:
            raise ValueError("[ERROR] no transcription model selected — pick one from the model list")
        if not tc.api_key:
            raise ValueError("[ERROR] Missing API key: enter your OPENAI_API_KEY in Settings")
        return OpenAITranscriptionProvider(api_key=tc.api_key, model=tc.model)
    raise ValueError(f"[ERROR] unknown transcription provider: {tc.provider}")


def build_translation_provider(cfg: AppConfig) -> OpenAICompatibleProvider:
    t = cfg.translation
    if not t.model:
        raise ValueError("[ERROR] no translation model selected — pick one from the model list")

    if t.source == "local":
        if not t.local_base_url:
            raise ValueError("[ERROR] enter your local server base URL (e.g. LM Studio) in Settings")
        return OpenAICompatibleProvider(base_url=t.local_base_url, api_key=t.local_api_key, model=t.model)

    preset = TRANSLATION_PRESETS.get(t.provider)
    if preset is None or not preset.base_url:
        raise ValueError(f"[ERROR] unknown translation provider: {t.provider}")
    if not t.api_key:
        raise ValueError(f"[ERROR] Missing API key for {preset.name}: enter it in Settings")
    return OpenAICompatibleProvider(base_url=preset.base_url, api_key=t.api_key, model=t.model)


def validate_reasoning_choice(spec: ReasoningSpec, chosen: str) -> str:
    """Keep a stored reasoning value only if the CURRENT model still offers it."""
    if spec.kind == "effort" and chosen in spec.values:
        return chosen
    return ""
