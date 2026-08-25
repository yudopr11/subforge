import pytest

from subforge.app.model_manager import KNOWN_WHISPER_MODELS, LocalModelManager


def cached(models: set[str]):
    return lambda repo_id: any(m in repo_id for m in models)


def failing_downloader(model_id):
    raise AssertionError("download must not be called when listing")


def test_list_marks_installed_from_cache():
    mgr = LocalModelManager(cache_checker=cached({"large-v3"}), downloader=failing_downloader)
    infos = {i.id: i for i in mgr.list_models()}
    assert set(infos) == set(KNOWN_WHISPER_MODELS)
    assert infos["large-v3"].installed is True
    assert infos["medium"].installed is False
    assert infos["large-v3"].profile == "Quality"
    assert infos["base"].profile == "Lightweight"


def test_install_invokes_downloader_for_known_model():
    calls = []

    def downloader(model_id):
        calls.append(model_id)
        return f"/cache/{model_id}"

    mgr = LocalModelManager(cache_checker=cached(set()), downloader=downloader)
    assert mgr.install("small") == "/cache/small"
    assert calls == ["small"]


def test_install_rejects_unknown_model():
    mgr = LocalModelManager(cache_checker=cached(set()), downloader=failing_downloader)
    with pytest.raises(ValueError, match="unknown local model"):
        mgr.install("tiny-en-diy")
