from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from subforge.app.device import DeviceSpecs
from subforge.app.model_manager import (
    GGML_WHISPER_MODELS,
    KNOWN_WHISPER_MODELS,
    LocalModelManager,
)


def test_ggml_whisper_models_metadata():
    assert "large-v3-turbo" in GGML_WHISPER_MODELS
    assert "small" in GGML_WHISPER_MODELS
    assert "base" in GGML_WHISPER_MODELS
    assert "tiny" in GGML_WHISPER_MODELS
    assert GGML_WHISPER_MODELS["large-v3-turbo"]["filename"] == "ggml-large-v3-turbo.bin"
    assert KNOWN_WHISPER_MODELS is GGML_WHISPER_MODELS


def test_list_models_with_recommendation(tmp_path: Path):
    manager = LocalModelManager(models_dir=tmp_path)
    specs = DeviceSpecs(ram_gb=16.0, cpu_cores=8)
    models = manager.list_models(specs=specs)

    turbo = next(m for m in models if m.id == "large-v3-turbo")
    assert turbo.recommended is True
    assert turbo.installed is False
    assert turbo.size == "~800 MB"

    small = next(m for m in models if m.id == "small")
    assert small.recommended is False


def test_is_installed_and_get_model_path(tmp_path: Path):
    manager = LocalModelManager(models_dir=tmp_path)
    assert not manager.is_installed("base")

    # Create dummy model file
    model_file = tmp_path / "ggml-base.bin"
    model_file.write_bytes(b"dummy model weights")

    assert manager.is_installed("base")
    assert manager.get_model_path("base") == model_file


def test_download_url():
    manager = LocalModelManager()
    url = manager.download_url("small")
    assert url == "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"


def test_install_custom_downloader():
    calls = []

    def downloader(model_id):
        calls.append(model_id)
        return f"/cache/{model_id}"

    mgr = LocalModelManager(downloader=downloader)
    assert mgr.install("small") == "/cache/small"
    assert calls == ["small"]


def test_install_rejects_unknown_model():
    mgr = LocalModelManager()
    with pytest.raises(ValueError, match="unknown local model"):
        mgr.install("nonexistent-model")


def test_install_http_download_mocked(tmp_path: Path):
    manager = LocalModelManager(models_dir=tmp_path)
    content = b"GGUF_MOCK_BYTES_DATA"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers={"Content-Length": str(len(content))})

    transport = httpx.MockTransport(handler)
    with patch(
        "httpx.stream",
        side_effect=lambda method, url, **kwargs: httpx.Client(transport=transport).stream(
            method, url
        ),
    ):
        progress_records: list[tuple[int, int]] = []
        res_path = manager.install(
            "tiny",
            progress_callback=lambda dl, tot: progress_records.append((dl, tot)),
        )

    assert res_path == tmp_path / "ggml-tiny.bin"
    assert res_path.exists()
    assert res_path.read_bytes() == content
    assert len(progress_records) > 0
    assert progress_records[-1] == (len(content), len(content))
