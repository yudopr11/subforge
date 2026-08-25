import stat

from subforge.config.app_config import (
    AppConfig,
    default_config_path,
    load_app_config,
    save_app_config,
)


def test_defaults_are_local_and_empty_secrets():
    cfg = AppConfig()
    assert cfg.transcription.provider == "local"
    assert cfg.transcription.api_key == ""
    assert cfg.translation.source == "local"
    assert cfg.translation.local_base_url == "http://localhost:1234/v1"
    assert cfg.translation.api_key == ""
    assert cfg.translation.reasoning_effort == ""


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "subforge" / "config.json"
    cfg = AppConfig(
        transcription={"provider": "openai", "model": "whisper-1", "api_key": "sk-t"},
        translation={
            "source": "provider",
            "provider": "opencode-go",
            "api_key": "oc-t",
            "model": "glm-5.2",
            "reasoning_effort": "high",
        },
    )
    save_app_config(cfg, path)
    loaded = load_app_config(path)
    assert loaded == cfg
    assert loaded.translation.model == "glm-5.2"


def test_missing_file_returns_defaults(tmp_path):
    assert load_app_config(tmp_path / "does-not-exist.json") == AppConfig()


def test_corrupt_file_returns_defaults(tmp_path):
    bad = tmp_path / "config.json"
    bad.write_text("{not json")
    assert load_app_config(bad) == AppConfig()


def test_saved_file_is_user_only_on_posix(tmp_path):
    path = tmp_path / "config.json"
    save_app_config(AppConfig(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600  # plaintext keys demand it


def test_env_var_overrides_path(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBFORGE_CONFIG", str(tmp_path / "custom.json"))
    assert default_config_path() == tmp_path / "custom.json"
