import json
from pathlib import Path

import pytest

from subforge.app.pipeline import Pipeline, StageError
from subforge.app.project_store import create_project
from subforge.config.settings import Settings
from subforge.models.project import ProjectMeta, StageState
from subforge.models.transcript import Transcript, TranscriptSegment


class FakeASR:
    def __init__(self, transcript: Transcript):
        self.transcript = transcript
        self.calls = 0

    def transcribe(self, audio_path, language=None):
        self.calls += 1
        return self.transcript


def setup_project(tmp_path: Path, audio_name: str = "final_audio.wav") -> tuple[Path, Path]:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    audio = d / "audio" / audio_name
    audio.write_bytes(b"RIFF-fake")
    return d, audio


TRANSCRIPT = Transcript(
    language="id",
    segments=[TranscriptSegment(id=1, start=1.2, end=3.4, text="Halo semuanya!")],
)


def test_transcription_persists_normalized_segments(tmp_path):
    d, _ = setup_project(tmp_path)
    asr = FakeASR(TRANSCRIPT)
    pipe = Pipeline(d, Settings(), transcription=asr)

    pipe.run_transcription("final_audio.wav")

    stored = json.loads((d / "transcripts" / "source.json").read_text())
    assert stored["segments"][0]["text"] == "Halo semuanya!"
    project = pipe.load()
    assert project.segments[0].source == "Halo semuanya!"
    assert project.segments[0].start == 1.2
    assert project.get_stage("transcription") is StageState.COMPLETED


def test_completed_transcription_not_rerun_by_retry(tmp_path):
    d, _ = setup_project(tmp_path)
    asr = FakeASR(TRANSCRIPT)
    pipe = Pipeline(d, Settings(), transcription=asr)
    pipe.run_transcription("final_audio.wav")
    calls_before = asr.calls

    pipe.retry("transcription", "final_audio.wav")
    assert asr.calls == calls_before  # resumability: completed stages stay done (ARCH §23)


def test_failed_transcription_marks_state_and_raises(tmp_path):
    class BoomASR:
        def transcribe(self, audio_path, language=None):
            raise FileNotFoundError("model files missing")

    d, _ = setup_project(tmp_path)
    pipe = Pipeline(d, Settings(), transcription=BoomASR())
    with pytest.raises(StageError, match="transcription failed"):
        pipe.run_transcription("final_audio.wav")
    assert pipe.load().get_stage("transcription") is StageState.FAILED


def test_retry_reruns_failed_stage(tmp_path):
    d, _ = setup_project(tmp_path)
    asr = FakeASR(TRANSCRIPT)
    pipe = Pipeline(d, Settings(), transcription=asr)
    project = pipe.load()
    project.set_stage("transcription", StageState.FAILED)
    from subforge.app.project_store import save_project

    save_project(d, project)

    pipe.retry("transcription", "final_audio.wav")
    assert pipe.load().get_stage("transcription") is StageState.COMPLETED
