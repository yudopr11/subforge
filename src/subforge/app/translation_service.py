"""Contextual batch translation with strict output validation (PRD §11, ARCH §15–16)."""

from subforge.models.project import Project, Segment, StageState
from subforge.providers.base import TranslationInput, TranslationOutput, TranslationProvider

DEFAULT_BATCH_SIZE = 5


class TranslationValidationError(Exception):
    def __init__(self, message: str, batch_ids: set[int]):
        super().__init__(message)
        self.batch_ids = batch_ids


class TranslationService:
    def __init__(
        self,
        provider: TranslationProvider,
        batch_size: int = DEFAULT_BATCH_SIZE,
        reasoning_effort: str | None = None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.provider = provider
        self.batch_size = batch_size
        self.reasoning_effort = reasoning_effort or None

    def translate_project(self, project: Project, target_language: str) -> None:
        project.set_stage(f"translation_{target_language}", StageState.RUNNING)
        errors: list[str] = []
        bad_ids: set[int] = set()

        segments = sorted(project.segments, key=lambda s: s.id)
        for offset in range(0, len(segments), self.batch_size):
            batch = segments[offset : offset + self.batch_size]
            try:
                merged = self._translate_batch(batch, project.project.source_language, target_language)
                for seg in batch:
                    seg.translations[target_language] = merged[seg.id]
            except TranslationValidationError as exc:
                errors.append(str(exc))
                bad_ids |= exc.batch_ids

        if errors:
            project.set_stage(f"translation_{target_language}", StageState.FAILED)
            raise TranslationValidationError("; ".join(errors), bad_ids)
        project.set_stage(f"translation_{target_language}", StageState.COMPLETED)

    def _translate_batch(
        self,
        batch: list[Segment],
        source_language: str,
        target_language: str,
    ) -> dict[int, str]:
        inputs = [TranslationInput(id=s.id, text=s.source) for s in batch]
        outputs: list[TranslationOutput] = self.provider.translate(
            inputs,
            source_language,
            target_language,
            reasoning_effort=self.reasoning_effort,
        )
        return _validate_batch(inputs, outputs)


def _validate_batch(inputs: list[TranslationInput], outputs: list[TranslationOutput]) -> dict[int, str]:
    """Rules from ARCH §16: exact ID match, unique, non-empty."""
    expected = {inp.id for inp in inputs}
    received: dict[int, str] = {}
    duplicates: set[int] = set()

    for out in outputs:
        if out.id not in expected:
            raise TranslationValidationError(f"output has unknown segment id {out.id}", {out.id})
        if out.id in received:
            duplicates.add(out.id)
        received[out.id] = out.text

    problems: list[str] = []
    if duplicates:
        problems.append(f"duplicate ids in output: {sorted(duplicates)}")
    missing = expected - received.keys()
    if missing:
        problems.append(f"missing translations for ids {sorted(missing)}")
    empty = {sid for sid, text in received.items() if not text.strip()}
    if empty:
        problems.append(f"empty translations for ids {sorted(empty)}")
    if problems:
        raise TranslationValidationError("; ".join(problems), expected)
    return received
