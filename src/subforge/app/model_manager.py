"""Discovery and management of local GGML Whisper models for whisper.cpp."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from subforge.app.device import DeviceDetector, DeviceSpecs

GGML_WHISPER_MODELS: dict[str, dict[str, str]] = {
    "tiny": {
        "profile": "Ultra-light",
        "vram": "~500 MB RAM",
        "size": "~75 MB",
        "filename": "ggml-tiny.bin",
    },
    "base": {
        "profile": "Lightweight",
        "vram": "~1 GB RAM",
        "size": "~142 MB",
        "filename": "ggml-base.bin",
    },
    "small": {
        "profile": "Balanced",
        "vram": "~2 GB RAM",
        "size": "~466 MB",
        "filename": "ggml-small.bin",
    },
    "medium": {
        "profile": "High Quality",
        "vram": "~5 GB RAM",
        "size": "~1.5 GB",
        "filename": "ggml-medium.bin",
    },
    "large-v3-turbo": {
        "profile": "Optimal Quality",
        "vram": "~4 GB RAM",
        "size": "~800 MB",
        "filename": "ggml-large-v3-turbo.bin",
    },
    "large-v3": {
        "profile": "Maximum Quality",
        "vram": "~8 GB RAM",
        "size": "~3.1 GB",
        "filename": "ggml-large-v3.bin",
    },
}

KNOWN_WHISPER_MODELS = GGML_WHISPER_MODELS

HUGGINGFACE_GGML_BASE_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"


@dataclass(frozen=True)
class LocalModelInfo:
    id: str
    profile: str
    vram: str
    size: str
    installed: bool
    recommended: bool = False


def default_models_dir() -> Path:
    env = os.environ.get("SUBFORGE_MODELS_DIR")
    if env:
        return Path(env)
    if os.name == "nt":
        app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(app_data) / "subforge" / "models"
    return Path.home() / ".local" / "share" / "subforge" / "models"


class LocalModelManager:
    def __init__(
        self,
        models_dir: Path | None = None,
        cache_checker: Callable[[str], bool] | None = None,
        downloader: Callable[[str], Any] | None = None,
    ) -> None:
        self.models_dir = models_dir or default_models_dir()
        self._cache_checker = cache_checker
        self._downloader = downloader

    def get_models_dir(self) -> Path:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        return self.models_dir

    def get_model_path(self, model_id: str) -> Path:
        meta = GGML_WHISPER_MODELS.get(model_id)
        if not meta:
            raise ValueError(f"[ERROR] unknown local model: {model_id}")
        return self.models_dir / meta["filename"]

    def is_installed(self, model_id: str) -> bool:
        if self._cache_checker is not None:
            return self._cache_checker(model_id)
        try:
            path = self.get_model_path(model_id)
            return path.exists() and path.stat().st_size > 0
        except ValueError:
            return False

    def download_url(self, model_id: str) -> str:
        meta = GGML_WHISPER_MODELS.get(model_id)
        if not meta:
            raise ValueError(f"[ERROR] unknown local model: {model_id}")
        return f"{HUGGINGFACE_GGML_BASE_URL}/{meta['filename']}"

    def list_models(self, specs: DeviceSpecs | None = None) -> list[LocalModelInfo]:
        dev_specs = specs or DeviceDetector.get_specs()
        recommended_id = DeviceDetector.recommend_model(dev_specs)
        infos = []
        for model_id, meta in GGML_WHISPER_MODELS.items():
            installed = self.is_installed(model_id)
            is_rec = model_id == recommended_id
            infos.append(
                LocalModelInfo(
                    id=model_id,
                    profile=meta["profile"],
                    vram=meta["vram"],
                    size=meta["size"],
                    installed=installed,
                    recommended=is_rec,
                )
            )
        return infos

    def install(
        self,
        model_id: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Any:
        if model_id not in GGML_WHISPER_MODELS:
            raise ValueError(f"[ERROR] unknown local model: {model_id}")
        if self._downloader is not None:
            return self._downloader(model_id)

        url = self.download_url(model_id)
        target_path = self.get_model_path(model_id)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".bin.tmp")

        import httpx

        with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
            response.raise_for_status()
            total_bytes = int(response.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_bytes)

        if target_path.exists():
            target_path.unlink()
        tmp_path.rename(target_path)
        return target_path
