from pathlib import Path

from subforge.app.project_store import create_project, load_project, save_project
from subforge.models.project import ProjectMeta, Segment
from subforge.providers.base import TranslationInput, TranslationOutput


class EchoTranslator:
    def translate(
        self,
        segments: list[TranslationInput],
        source_language: str,
        target_language: str,
        reasoning_effort: str | None = None,
    ):
        return [TranslationOutput(id=s.id, text=f"<{target_language}> {s.text}") for s in segments]


def seed(tmp_path: Path) -> Path:
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id", target_languages=["en"]))
    project = load_project(d)
    project.segments = [Segment(id=1, start=1.2, end=3.4, source="Halo!")]
    save_project(d, project)
    return d


async def test_edit_translation_and_export(tmp_path):
    from subforge.app.translation_service import TranslationService
    from subforge.tui.app import SubForgeApp
    from subforge.tui.screens.review_translate import ReviewTranslateScreen

    d = seed(tmp_path)

    app = SubForgeApp()
    async with app.run_test() as pilot:
        screen = ReviewTranslateScreen(d, TranslationService(EchoTranslator()))
        await app.push_screen(screen)
        await pilot.pause()

        screen.apply_edit(1, "en", "Hi there!")
        await pilot.pause()
        assert load_project(d).segments[0].translations["en"] == "Hi there!"

        paths = screen.do_export(["srt"], ["en"])
        assert (d / "exports" / "en.srt").exists()
        assert any(p.name == "en.srt" for p in paths)
