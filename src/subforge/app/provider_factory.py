"""Build concrete providers from the TUI-authored AppConfig.

Core pipeline modules never import this — they receive ready provider objects.
"""

from pathlib import Path

from subforge.app.pipeline import Pipeline
from subforge.app.translation_service import DEFAULT_BATCH_SIZE, TranslationService
from subforge.config.app_config import AppConfig
from subforge.config.providers import TRANSLATION_PRESETS
from subforge.config.settings import Settings
from subforge.providers.capabilities import PROVIDER_TO_CATALOG, CapabilityClient, ReasoningSpec
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


def resolve_reasoning_effort(cfg: AppConfig, client: object | None = None) -> str:
    """Validate the stored effort against the CURRENT model's discovered vocabulary.

    Local servers and any catalog/network failure degrade to "" (parameter omitted) —
    never crash the session (PRD §15).
    """
    t = cfg.translation
    if not (t.model and t.reasoning_effort):
        return ""
    preset_id = t.provider if t.source == "provider" else None
    if not preset_id:
        return ""  # local servers: unknown vocabulary -> omit parameter
    try:
        cap_client = client if client is not None else CapabilityClient()
        spec = cap_client.reasoning_spec(PROVIDER_TO_CATALOG[preset_id], t.model)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — offline/degraded catalog/unknown preset must not block translation
        return ""
    return validate_reasoning_choice(spec, t.reasoning_effort)


def build_translation_service(
    cfg: AppConfig,
    capability_client: object | None = None,
) -> TranslationService:
    provider = build_translation_provider(cfg)
    return TranslationService(
        provider,
        batch_size=cfg.translation.batch_size or DEFAULT_BATCH_SIZE,
        reasoning_effort=resolve_reasoning_effort(cfg, capability_client) or None,
    )


def build_pipeline(
    project_dir: Path,
    cfg: AppConfig,
    capability_client: object | None = None,
) -> Pipeline:
    """Assemble a ready-to-run Pipeline; unconfigured stages stay unset so the
    pipeline reports its own '[ERROR] No ... provider configured.' message."""
    transcription = None
    try:
        transcription = build_transcription_provider(cfg)
    except ValueError:
        pass
    translation_service: TranslationService | None
    try:
        translation_service = build_translation_service(cfg, capability_client)
    except ValueError:
        translation_service = None
    return Pipeline(
        project_dir,
        _settings_for(cfg),
        transcription=transcription,
        translation_service=translation_service,
    )


def _settings_for(cfg: AppConfig) -> Settings:
    from subforge.config.settings import (
        Settings,
    )

    settings = Settings()
    settings.translation.batch_size = cfg.translation.batch_size or settings.translation.batch_size
    return settings


def transcription_configured(cfg: AppConfig) -> bool:
    """True when a Transcribe run would have a provider (PRD §21 loud guidance)."""
    try:
        build_transcription_provider(cfg)
        return True
    except ValueError:
        return False


def translation_configured(cfg: AppConfig) -> bool:
    """True when a Translate run would have a provider."""
    try:
        build_translation_provider(cfg)
        return True
    except ValueError:
        return False
