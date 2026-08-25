from pathlib import Path

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.speaker_map import SpeakerMapScreen


def seed(tmp_path: Path) -> Path:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    project = load_project(d)
    project.segments = [
        Segment(id=1, start=0.0, end=2.0, source="a", speaker="SPEAKER_00"),
        Segment(id=2, start=2.0, end=4.0, source="b", speaker="SPEAKER_01"),
        Segment(id=3, start=4.0, end=6.0, source="c", speaker="SPEAKER_00"),
    ]
    save_project(d, project)
    return d


async def test_lists_distinct_speakers_and_applies_mapping(tmp_path):
    d = seed(tmp_path)
    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = SpeakerMapScreen(d)
        await app.push_screen(screen)
        await pilot.pause()

        table = screen.query_one("DataTable")
        assert table.row_count == 2  # SPEAKER_00, SPEAKER_01

        screen.apply_mapping("SPEAKER_00", "Adi")
        await pilot.pause()

        reloaded = load_project(d)
        assert reloaded.project.speaker_map == {"SPEAKER_00": "Adi"}
