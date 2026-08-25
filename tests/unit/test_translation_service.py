import pytest

from subforge.app.translation_service import TranslationService, TranslationValidationError
from subforge.models.project import Project, ProjectMeta, Segment, StageState
from subforge.providers.base import TranslationInput, TranslationOutput


class FakeProvider:
    """Returns outputs exactly mirroring inputs through a transform."""

    def __init__(self, fail_batch_indices: set[int] | None = None):
        self.fail = fail_batch_indices or set()
        self.calls: list[list[TranslationInput]] = []

    def translate(self, segments, source_language, target_language, reasoning_effort=None):
        self.calls.append(list(segments))
        if len(self.calls) - 1 in self.fail:
            return [TranslationOutput(id=s.id, text="") for s in segments[:1]]  # incomplete + empty
        return [TranslationOutput(id=s.id, text=f"T:{s.text}") for s in segments]


def make_project(n: int = 12) -> Project:
    return Project(
        project=ProjectMeta(name="p", source_language="id", target_languages=["en"]),
        segments=[
            Segment(id=i + 1, start=float(i), end=float(i) + 1, source=f"kalimat {i + 1}") for i in range(n)
        ],
    )


def test_batches_of_five_with_context():
    provider = FakeProvider()
    svc = TranslationService(provider)
    project = make_project(12)
    svc.translate_project(project, "en")

    assert len(provider.calls) == 3  # 5 + 5 + 2
    assert [i.id for i in provider.calls[0]] == [1, 2, 3, 4, 5]
    assert [i.id for i in provider.calls[2]] == [11, 12]
    assert project.segments[0].translations["en"] == "T:kalimat 1"
    assert project.get_stage("translation_en") is StageState.COMPLETED


def test_timestamps_never_touched():
    provider = FakeProvider()
    project = make_project(3)
    before = [(s.id, s.start, s.end) for s in project.segments]
    svc = TranslationService(provider)
    svc.translate_project(project, "en")
    after = [(s.id, s.start, s.end) for s in project.segments]
    assert before == after  # PRD §10 core principle


def test_bad_batch_fails_without_corrupting_project():
    provider = FakeProvider(fail_batch_indices={0})
    project = make_project(12)
    svc = TranslationService(provider)
    with pytest.raises(TranslationValidationError):
        svc.translate_project(project, "en")
    # ARCH §16: invalid output fails THAT batch — its segments stay untouched.
    assert all("en" not in s.translations for s in project.segments if s.id <= 5)
    assert project.get_stage("translation_en") is StageState.FAILED
    # ...and later successful batches still merged; error raised after processing.
    assert project.segments[5].translations["en"] == "T:kalimat 6"


def test_later_batches_still_run_after_failure_is_reported_at_end():
    # Batch 2 fails; batch 1 results are still merged, error raised after processing.
    class PartialFail(FakeProvider):
        def translate(self, segments, source_language, target_language, reasoning_effort=None):
            if segments[0].id == 6:
                return [TranslationOutput(id=99, text="unknown id")]  # unknown ID -> invalid
            return super().translate(segments, source_language, target_language)

    project = make_project(12)
    with pytest.raises(TranslationValidationError) as excinfo:
        TranslationService(PartialFail()).translate_project(project, "en")
    assert project.segments[0].translations["en"] == "T:kalimat 1"
    assert 99 in excinfo.value.batch_ids


def test_reasoning_effort_passed_through_to_provider():
    """Configured reasoning effort travels verbatim (PRD §15); default is None."""

    class Capturing(FakeProvider):
        def __init__(self):
            super().__init__()
            self.efforts: list[str | None] = []

        def translate(self, segments, source_language, target_language, reasoning_effort=None):
            self.efforts.append(reasoning_effort)
            return super().translate(segments, source_language, target_language, reasoning_effort)

    project = make_project(3)

    capturing = Capturing()
    TranslationService(capturing).translate_project(project, "en")
    assert capturing.efforts == [None]

    capturing = Capturing()
    TranslationService(capturing, reasoning_effort="max").translate_project(project, "en")
    assert capturing.efforts == ["max"]
