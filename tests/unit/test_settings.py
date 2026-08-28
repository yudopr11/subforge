from textwrap import dedent

from subforge.config.settings import load_settings


def test_local_first_defaults():
    s = load_settings(env_file=None)
    assert s.transcription.provider == "local"
    assert s.transcription.model == "large-v3"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "small")
    s = load_settings(env_file=None)
    assert s.transcription.model == "small"


def test_env_file_layer(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        dedent("""\
        TRANSCRIPTION_MODEL=medium
        """)
    )
    s = load_settings(env_file=env)
    assert s.transcription.model == "medium"
