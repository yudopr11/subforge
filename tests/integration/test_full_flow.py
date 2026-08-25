import json
from pathlib import Path
from typing import ClassVar

import pytest

from subforge.app.export import export_subtitles
from subforge.app.pipeline import Pipeline, StageError
from subforge.app.project_store import create_project, load_project
from subforge.config.settings import Settings
from subforge.models.project import ProjectMeta, StageState
from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.base import TranslationInput, TranslationOutput


class ScriptedASR:
    TRANSCRIPT: ClassVar[Transcript] = Transcript(
        language="id",
        segments=[
            TranscriptSegment(id=1, start=1.2, end=3.4, text="Halo semuanya!"),
            TranscriptSegment(id=2, start=3.5, end=6.8, text="Selamat datang kembali."),
        ],
    )

    def transcribe(self, audio_path, language=None):
        assert audio_path.exists(), "pipeline must read from audio/ directory"
        return self.TRANSCRIPT


class ScriptedLLM:
    MAP: ClassVar[dict[int, str]] = {
        1: "Hello everyone!",
        2: "Welcome back.",
    }

    def translate(self, segments: list[TranslationInput], source_language: str, target_language: str):
        assert target_language == "en"
        return [TranslationOutput(id=s.id, text=self.MAP[s.id]) for s in segments]


def test_audio_to_srt_and_ass(tmp_path: Path):
    from subforge.app.translation_service import TranslationService

    d = create_project(
        tmp_path / "yt-001", ProjectMeta(name="yt-001", source_language="id", target_languages=["en"])
    )
    (d / "audio" / "final_audio.wav").write_bytes(b"RIFF....")  # fakes never decode it

    pipe = Pipeline(
        d,
        Settings(),
        transcription=ScriptedASR(),
        translation_service=TranslationService(ScriptedLLM()),
    )
    pipe.run_transcription("final_audio.wav")
    pipe.run_diarization("final_audio.wav")  # no provider -> SKIPPED, must not block
    pipe.run_translation("en")
    written = export_subtitles(d, formats=["srt", "ass"], languages=["en"])

    names = {p.name for p in written}
    assert names == {"source.srt", "en.srt", "source.ass", "en.ass"}

    en_srt = (d / "exports" / "en.srt").read_text()
    assert "1\n00:00:01,200 --> 00:00:03,400\nHello everyone!" in en_srt
    assert "2\n00:00:03,500 --> 00:00:06,800\nWelcome back." in en_srt

    project = load_project(d)
    assert project.get_stage("diarization") is StageState.SKIPPED
    assert project.get_stage("export") is StageState.COMPLETED

    # transcripts/source.json matches canonical normalization
    stored = json.loads((d / "transcripts" / "source.json").read_text())
    assert stored["segments"][0]["text"] == "Halo semuanya!"


def test_retry_after_translation_failure_only_reruns_translation(tmp_path: Path):
    from subforge.app.translation_service import TranslationService
    from subforge.providers.base import TranslationOutput as Out

    class FlakyLLM(ScriptedLLM):
        def __init__(self):
            self.failed_once = False

        def translate(self, segments, source_language, target_language):
            if not self.failed_once:
                self.failed_once = True
                return [Out(id=999, text="garbage")]  # invalid: unknown id -> batch rejected
            return super().translate(segments, source_language, target_language)

    d = create_project(
        tmp_path / "yt", ProjectMeta(name="yt", source_language="id", target_languages=["en"])
    )
    (d / "audio" / "a.wav").write_bytes(b"x")
    llm = FlakyLLM()
    pipe = Pipeline(d, Settings(), transcription=ScriptedASR(), translation_service=TranslationService(llm))
    pipe.run_transcription("a.wav")

    with pytest.raises(StageError):
        pipe.run_translation("en")
    assert pipe.load().get_stage("translation_en") is StageState.FAILED

    # Retry: transcription stage must NOT be re-executed (only translation runs again).
    asr_stage_before = load_project(d).get_stage("transcription")
    pipe.retry("translation", "en")
    final = load_project(d)
    assert final.get_stage("translation_en") is StageState.COMPLETED
    assert final.get_stage("transcription") is asr_stage_before is StageState.COMPLETED
    assert final.segments[0].translations["en"] == "Hello everyone!"
