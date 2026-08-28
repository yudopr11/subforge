"""Build concrete providers from the TUI-authored AppConfig.

Core pipeline modules never import this — they receive ready provider objects.
"""

from pathlib import Path

from subforge.app.pipeline import Pipeline
from subforge.config.app_config import AppConfig
from subforge.config.settings import Settings
from subforge.providers.transcription.whisper_cpp import WhisperCppProvider


def build_transcription_provider(cfg: AppConfig) -> WhisperCppProvider:
    tc = cfg.transcription
    if not tc.model:
        raise ValueError("[ERROR] no local transcription model selected — pick one in Settings")
    models_dir = Path(tc.models_dir) if tc.models_dir else None
    return WhisperCppProvider(
        model=tc.model,
        binary_path=tc.binary_path,
        models_dir=models_dir,
    )


def build_pipeline(
    project_dir: Path,
    cfg: AppConfig,
) -> Pipeline:
    """Assemble a ready-to-run Pipeline; unconfigured stages stay unset so the
    pipeline reports its own '[ERROR] No transcription provider configured.' message."""
    transcription = None
    try:
        transcription = build_transcription_provider(cfg)
    except ValueError:
        pass
    return Pipeline(
        project_dir,
        _settings_for(cfg),
        transcription=transcription,
    )


def _settings_for(cfg: AppConfig) -> Settings:
    return Settings()


def transcription_configured(cfg: AppConfig) -> bool:
    """True when a Transcribe run would have a provider (PRD §21 loud guidance)."""
    try:
        build_transcription_provider(cfg)
        return True
    except ValueError:
        return False
