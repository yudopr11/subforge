"""Discovery + installation of local Whisper models (PRD §8 hardware profiles)."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

LOCAL_EXTRAS_HINT = 'Local transcription models require the optional extra: pip install "subforge[local]"'

KNOWN_WHISPER_MODELS: dict[str, dict[str, str]] = {
    "large-v3": {"profile": "Quality", "vram": "~10 GB VRAM"},
    "medium": {"profile": "Balanced", "vram": "~5 GB VRAM"},
    "small": {"profile": "Lightweight", "vram": "~2 GB VRAM"},
    "base": {"profile": "Lightweight", "vram": "~1 GB VRAM"},
}

HF_REPOS = {
    "large-v3": "Systran/faster-whisper-large-v3",
    "medium": "Systran/faster-whisper-medium",
    "small": "Systran/faster-whisper-small",
    "base": "Systran/faster-whisper-base",
}


@dataclass(frozen=True)
class LocalModelInfo:
    id: str
    profile: str
    vram: str
    installed: bool


def _default_cache_checker(repo_id: str) -> bool:
    try:
        from huggingface_hub import snapshot_download  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(LOCAL_EXTRAS_HINT) from exc
    try:
        snapshot_download(repo_id=repo_id, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001 — not cached (or offline)
        return False


def _default_downloader(model_id: str) -> Any:
    try:
        from faster_whisper.utils import download_model  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(LOCAL_EXTRAS_HINT) from exc
    return download_model(model_id)


class LocalModelManager:
    def __init__(
        self,
        cache_checker: Callable[[str], bool] | None = None,
        downloader: Callable[[str], Any] | None = None,
    ) -> None:
        self._check = cache_checker or _default_cache_checker
        self._download = downloader or _default_downloader

    def list_models(self) -> list[LocalModelInfo]:
        infos = []
        for model_id, meta in KNOWN_WHISPER_MODELS.items():
            installed = self._check(HF_REPOS[model_id])
            infos.append(LocalModelInfo(model_id, meta["profile"], meta["vram"], installed))
        return infos

    def install(self, model_id: str) -> Any:
        if model_id not in KNOWN_WHISPER_MODELS:
            raise ValueError(f"[ERROR] unknown local model: {model_id}")
        return self._download(model_id)
