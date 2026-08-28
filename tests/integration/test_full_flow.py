import json
from pathlib import Path
from typing import ClassVar

from subforge.app.export import export_subtitles
from subforge.app.pipeline import Pipeline
from subforge.app.project_store import create_project, load_project
from subforge.config.settings import Settings
from subforge.models.project import ProjectMeta, StageState
from subforge.models.transcript import Transcript, TranscriptSegment


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


def test_audio_to_srt_and_ass(tmp_path: Path):
    d = create_project(
        tmp_path / "yt-001", ProjectMeta(name="yt-001", source_language="id")
    )
    (d / "audio" / "final_audio.wav").write_bytes(b"RIFF....")

    pipe = Pipeline(
        d,
        Settings(),
        transcription=ScriptedASR(),
    )
    pipe.run_transcription("final_audio.wav")
    written = export_subtitles(d, formats=["srt", "ass"])

    names = {p.name for p in written}
    assert names == {"source.srt", "source.ass"}

    source_srt = (d / "exports" / "source.srt").read_text()
    assert "1\n00:00:01,200 --> 00:00:03,400\nHalo semuanya!" in source_srt
    assert "2\n00:00:03,500 --> 00:00:06,800\nSelamat datang kembali." in source_srt

    project = load_project(d)
    assert project.get_stage("export") is StageState.COMPLETED

    # transcripts/source.json matches canonical normalization
    stored = json.loads((d / "transcripts" / "source.json").read_text())
    assert stored["segments"][0]["text"] == "Halo semuanya!"
