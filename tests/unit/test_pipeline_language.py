from pathlib import Path

import pytest

from subforge.app.pipeline import Pipeline, StageError
from subforge.app.project_store import create_project, load_project
from subforge.config.settings import Settings
from subforge.models.project import ProjectMeta
from subforge.models.transcript import Transcript, TranscriptSegment


class FakeASR:
    def __init__(self, transcript: Transcript):
        self.transcript = transcript
        self.calls: list[str | None] = []

    def transcribe(self, audio_path, language=None):
        self.calls.append(language)
        return self.transcript


def make_transcript(language: str | None) -> Transcript:
    return Transcript(
        language=language,
        segments=[TranscriptSegment(id=1, start=1.0, end=2.0, text="halo")],
    )


def setup(tmp_path: Path, source_language: str = "id") -> Path:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language=source_language))
    (d / "audio" / "a.wav").write_bytes(b"RIFF")
    return d


def test_auto_language_filled_from_detected(tmp_path):
    """PRD §7 'auto' language: empty meta is filled from ASR-detected language."""
    d = setup(tmp_path, source_language="")  # "" == auto-detect
    asr = FakeASR(make_transcript("id"))
    Pipeline(d, Settings(), transcription=asr).run_transcription("a.wav")

    project = load_project(d)
    assert project.project.source_language == "id"
    # the detected-at-request-time language was still None when calling ASR
    assert asr.calls == [None]


def test_manual_language_is_sent_and_preserved(tmp_path):
    d = setup(tmp_path, source_language="id")
    asr = FakeASR(make_transcript("en"))  # provider disagrees; manual wins for meta
    Pipeline(d, Settings(), transcription=asr).run_transcription("a.wav")

    project = load_project(d)
    assert asr.calls == ["id"]
    assert project.project.source_language == "id"


def test_no_detected_language_leaves_meta_empty(tmp_path):
    d = setup(tmp_path, source_language="")
    asr = FakeASR(make_transcript(None))
    Pipeline(d, Settings(), transcription=asr).run_transcription("a.wav")
    assert load_project(d).project.source_language == ""


def test_translate_empty_project_fails_loudly(tmp_path):
    """Zero segments must not 'succeed' with 0 batches (PRD §21 loud failures)."""
    d = setup(tmp_path)
    from subforge.app.translation_service import TranslationService

    class Never:
        def translate(self, segments, s, t, reasoning_effort=None):
            raise AssertionError("provider must not be called")

    pipe = Pipeline(d, Settings(), transcription=None, translation_service=TranslationService(Never()))
    with pytest.raises(StageError, match="No captions to translate"):
        pipe.run_translation("en")
