"""Resumable pipeline orchestration (PRD §22, ARCH §22–23).

The pipeline owns NO business logic: it sequences stages, records explicit
state, persists after every transition, and never reruns COMPLETED stages.
"""

from pathlib import Path
from typing import Any, Protocol

from subforge.app.project_store import load_project, save_project
from subforge.app.translation_service import DEFAULT_BATCH_SIZE, TranslationService
from subforge.config.settings import Settings
from subforge.models.project import Project, Segment, StageState
from subforge.models.transcript import Transcript


class StageError(RuntimeError):
    """User-facing failure for one pipeline stage (PRD §21)."""


class _Transcribes(Protocol):
    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript: ...


ALL_STAGES = ("transcription", "alignment", "caption_review", "export")


class _Unconfigured:
    def __init__(self, message: str) -> None:
        self._message = message

    def translate(self, *args: Any, **kwargs: Any) -> Any:
        raise StageError(self._message)


def _unconfigured(what: str) -> _Unconfigured:
    return _Unconfigured(
        f"[ERROR] No {what} provider configured. Configure TRANSLATION_* settings or pick one in Settings."
    )


class Pipeline:
    def __init__(
        self,
        project_dir: Path,
        settings: Settings,
        transcription: _Transcribes | None = None,
        translation_service: TranslationService | None = None,
    ) -> None:
        self.dir = project_dir
        self.settings = settings
        self.transcription = transcription
        self.translation_service = translation_service or TranslationService(
            provider=_unconfigured("translation"),
            batch_size=settings.translation.batch_size or DEFAULT_BATCH_SIZE,
        )

    # ---- project access -------------------------------------------------

    @property
    def project(self) -> Project:
        return load_project(self.dir)

    def load(self) -> Project:
        return self.project

    def _save(self, project: Project) -> None:
        save_project(self.dir, project)

    def status(self) -> dict[str, StageState]:
        project = self.project
        return {stage: project.get_stage(stage) for stage in ALL_STAGES}

    # ---- stages ----------------------------------------------------------

    def run_transcription(self, audio_filename: str) -> None:
        if self.transcription is None:
            raise StageError("[ERROR] No transcription provider configured.")
        project = self.project
        if project.get_stage("transcription") is StageState.COMPLETED:
            return  # ARCH §23: completed stages are never rerun implicitly
        project.set_stage("transcription", StageState.RUNNING)
        self._save(project)
        try:
            transcript = self.transcription.transcribe(
                self.dir / "audio" / audio_filename,
                language=project.project.source_language or None,
            )
        except Exception as exc:
            project.set_stage("transcription", StageState.FAILED)
            self._save(project)
            raise StageError(f"[ERROR] transcription failed: {exc}") from exc

        (self.dir / "transcripts").mkdir(exist_ok=True)
        (self.dir / "transcripts" / "source.json").write_text(transcript.model_dump_json(indent=2))

        # PRD §7: "auto" language (empty meta) is filled from ASR-detected language.
        if not project.project.source_language and transcript.language:
            project.project.source_language = transcript.language

        project.segments = [
            Segment(id=int(seg.id), start=seg.start, end=seg.end, source=seg.text)
            for seg in transcript.segments
        ]
        project.set_stage("transcription", StageState.COMPLETED)
        self._save(project)

    def run_translation(self, target_language: str) -> None:
        project = self.project
        if not project.segments:
            raise StageError("[ERROR] No captions to translate — transcribe first.")
        if target_language not in project.project.target_languages:
            project.project.target_languages.append(target_language)
            self._save(project)
        try:
            self.translation_service.translate_project(project, target_language)
        except Exception as exc:
            self._save(project)  # persist FAILED state recorded by service
            raise StageError(f"[ERROR] translation to '{target_language}' failed: {exc}") from exc
        self._save(project)

    # ---- resumability ------------------------------------------------------

    def retry(self, stage: str, *args: Any) -> None:
        project = self.project
        if project.get_stage(stage) is StageState.COMPLETED:
            return  # ARCH §23: retrying must not rerun completed upstream stages
        runner = getattr(self, f"run_{stage}")
        runner(*args)
