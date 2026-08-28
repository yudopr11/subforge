from subforge.models.project import Project, ProjectMeta, Segment, StageState


def make_project() -> Project:
    return Project(
        project=ProjectMeta(name="yt-001", source_language="id"),
        segments=[
            Segment(
                id=1,
                start=1.2,
                end=3.4,
                source="Halo semuanya!",
            ),
            Segment(id=2, start=3.5, end=6.8, source="Selamat datang kembali."),
        ],
    )


def test_segment_defaults():
    seg = Segment(id=1, start=0.0, end=1.0, source="hi")
    assert seg.source == "hi"


def test_roundtrip_serialization():
    p = make_project()
    data = p.model_dump()
    p2 = Project.model_validate(data)
    assert p2 == p


def test_stage_defaults_to_pending():
    p = make_project()
    assert p.get_stage("transcription") is StageState.PENDING


def test_set_and_get_stage():
    p = make_project()
    p.set_stage("export", StageState.COMPLETED)
    assert p.get_stage("export") is StageState.COMPLETED


def test_transcript_normalization():
    from subforge.models.transcript import Transcript

    t = Transcript(segments=[{"id": 1, "start": 1.2, "end": 3.4, "text": "Halo!"}])
    assert t.segments[0].text == "Halo!"


def test_stage_states_are_exact_set():
    # ARCH §22: exactly five states
    assert {s.value for s in StageState} == {"PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"}
