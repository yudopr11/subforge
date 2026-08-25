"""Canonical project data model — the single source of truth (ARCH §16, §17)."""

from enum import Enum

from pydantic import BaseModel, Field


class StageState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Segment(BaseModel):
    """Canonical caption unit. Timestamps are seconds (float)."""

    id: int
    start: float
    end: float
    source: str
    speaker: str | None = None
    translations: dict[str, str] = Field(default_factory=dict)


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    speaker: str | None = None


class Transcript(BaseModel):
    """Normalized ASR output — identical regardless of provider (ARCH §6)."""

    language: str | None = None
    segments: list[TranscriptSegment]


class ProjectMeta(BaseModel):
    name: str
    source_language: str
    target_languages: list[str] = Field(default_factory=list)
    speaker_map: dict[str, str] = Field(default_factory=dict)


class Project(BaseModel):
    project: ProjectMeta
    segments: list[Segment]
    stages: dict[str, StageState] = Field(default_factory=dict)

    def get_stage(self, name: str) -> StageState:
        return self.stages.get(name, StageState.PENDING)

    def set_stage(self, name: str, state: StageState) -> None:
        self.stages[name] = state
