from textwrap import dedent

from subforge.config.settings import load_settings


def test_local_first_defaults():
    s = load_settings(env_file=None)
    assert s.transcription.provider == "local"
    assert s.transcription.model == "large-v3"
    assert s.diarization.enabled is False
    assert s.translation.provider == "openai-compatible"
    assert s.translation.base_url == "http://localhost:1234/v1"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("TRANSLATION_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TRANSLATION_API_KEY", "secret")
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "small")
    s = load_settings(env_file=None)
    assert s.translation.base_url == "https://api.example.com/v1"
    assert s.translation.api_key == "secret"
    assert s.transcription.model == "small"


def test_env_file_layer(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        dedent("""\
        TRANSCRIPTION_MODEL=medium
        TRANSLATION_MODEL=qwen3-14b
        """)
    )
    s = load_settings(env_file=env)
    assert s.transcription.model == "medium"
    assert s.translation.model == "qwen3-14b"
