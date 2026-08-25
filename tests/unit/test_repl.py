"""REPL shell tests: slash commands drive the full pipeline (PRD §7).

E2E per AGENTS.md "Testing Requirements": commands are executed against real
project state with scripted providers; assertions check transcript output,
persisted files, and project.json stage states.
"""

from pathlib import Path

from textual.widgets import Input, OptionList

from subforge.app.pipeline import Pipeline
from subforge.app.project_store import create_project, load_project
from subforge.config.app_config import AppConfig
from subforge.models.project import ProjectMeta, StageState
from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.base import TranslationInput, TranslationOutput
from subforge.tui.app import SubForgeApp
from subforge.tui.screens.repl import ReplScreen


class FakeASR:
    def transcribe(self, audio_path, language=None):
        return Transcript(
            language="id",
            segments=[TranscriptSegment(id=1, start=1.0, end=2.0, text="halo")],
        )


class FakeTranslator:
    def translate(
        self,
        segments: list[TranslationInput],
        source_language: str,
        target_language: str,
        reasoning_effort: str | None = None,
    ):
        return [TranslationOutput(id=s.id, text=f"EN:{s.text}") for s in segments]


def fake_pipeline_factory(tmp_path: Path) -> ReplScreen.pipeline_factory:  # type: ignore[valid-type]
    from subforge.app.translation_service import TranslationService
    from subforge.config.settings import Settings

    def factory(project_dir: Path) -> Pipeline:
        return Pipeline(
            project_dir,
            Settings(),
            transcription=FakeASR(),
            translation_service=TranslationService(FakeTranslator()),
        )

    return factory


def transcript_text(app: SubForgeApp) -> str:
    repl = app.repl
    log = repl.query_one("#transcript")
    lines = []
    for strip in log.lines:  # RichLog stores Strips
        lines.append("".join(seg.text for seg in strip))
    return "\n".join(lines)


async def boot_repl(tmp_path: Path, app_config: AppConfig | None = None) -> tuple[SubForgeApp, ReplScreen]:
    monkey_target = tmp_path / "projects"
    monkey_target.mkdir(exist_ok=True)
    app = SubForgeApp(app_config=app_config or AppConfig())
    return app, None  # placeholder to satisfy typing tools


async def open_repl(tmp_path: Path, **kwargs):
    import os

    os.environ.setdefault("SUBFORGE_PROJECTS_DIR", str(tmp_path / "projects"))
    (tmp_path / "projects").mkdir(exist_ok=True)
    app = SubForgeApp(**kwargs)
    async with app.run_test() as pilot:
        await pilot.pause()
        yield app, app.repl


# ---- basics ------------------------------------------------------------------


async def test_welcome_and_prompt_render(tmp_path):
    async for app, repl in open_repl(tmp_path):
        assert isinstance(repl, ReplScreen)
        text = transcript_text(app)
        assert "subforge" in text and "/new" in text
        assert repl.query_one("#prompt")


async def test_help_lists_all_commands(tmp_path):
    async for app, repl in open_repl(tmp_path):
        repl.run_command("/help")
        text = transcript_text(app)
        for cmd in ("/new", "/open", "/transcribe", "/review", "/translate",
                    "/export", "/settings", "/wizard", "/status", "/quit"):
            assert cmd in text, cmd


async def test_unknown_command_reports_error(tmp_path):
    async for app, repl in open_repl(tmp_path):
        repl.run_command("/frobnicate")
        assert "unknown command" in transcript_text(app)


async def test_bare_alias_works_without_slash(tmp_path):
    async for app, repl in open_repl(tmp_path):
        repl.run_command("status")
        # no project -> guidance error line instead of crash
        assert "No project open" in transcript_text(app)


# ---- full flow e2e ------------------------------------------------------------


async def test_new_transcribe_translate_export_e2e(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path / "projects"))
    audio = tmp_path / "episode.wav"
    audio.write_bytes(b"RIFF-fake")

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        repl.pipeline_factory = fake_pipeline_factory(tmp_path)

        repl.run_command(f"/new {audio}")
        await pilot.pause()
        assert "'episode'" in transcript_text(app)

        repl.run_command("/transcribe")
        await pilot.pause()
        assert "transcribed" in transcript_text(app)
        assert load_project(app.project_dir).get_stage("transcription") is StageState.COMPLETED

        repl.run_command("/translate en")
        await pilot.pause()
        assert "translated to 'en'" in transcript_text(app)
        project = load_project(app.project_dir)
        assert project.segments[0].translations["en"] == "EN:halo"
        assert project.get_stage("translation_en") is StageState.COMPLETED

        repl.run_command("/export")
        exports = {p.name for p in (app.project_dir / "exports").iterdir()}
        assert exports == {"source.srt", "source.ass", "en.srt", "en.ass"}
        assert load_project(app.project_dir).get_stage("export") is StageState.COMPLETED


async def test_new_seeds_source_language_from_config(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path / "projects"))
    cfg = AppConfig(transcription={"provider": "local", "model": "small", "language": "id"})
    app = SubForgeApp(app_config=cfg)
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"x")
        repl.run_command(f"/new {audio}")
        assert load_project(app.project_dir).project.source_language == "id"


# ---- open / status / setup guidance ---------------------------------------------


async def test_open_lists_and_opens_by_index(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path / "projects"))
    import os

    from subforge.app.projects import create_project_from_audio

    root = tmp_path / "projects"
    a = tmp_path / "a.wav"
    a.write_bytes(b"x")
    d1 = create_project_from_audio(a, root)
    d2 = create_project_from_audio(a, root)
    # deterministic recency: d2 modified after d1
    os.utime(d1, (1000, 1000))
    os.utime(d2, (2000, 2000))

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl

        # bare /open -> searchable picker, recent-first, with +create-new row
        repl.run_command("/open")
        await pilot.pause()
        from subforge.tui.screens.project import ProjectPickerScreen

        picker = app.screen
        assert isinstance(picker, ProjectPickerScreen)
        options = [str(o.prompt) for o in picker.query_one("#projects").options]
        assert options[0].startswith("[+] Create new")
        assert "a-2" in options[1]  # recent-first: d2 before d1
        assert "a " in options[2] or "a   ·" in options[2]

        # type to search -> filters to a-2 -> Enter opens it
        search = picker.query_one("#project-search")
        search.value = "a-2"
        await pilot.pause()
        filtered = [str(o.prompt) for o in picker.query_one("#projects").options]
        assert len(filtered) == 1 and "a-2" in filtered[0]
        picker.on_input_submitted(type("Evt", (), {"input": search})())
        await pilot.pause()
        assert app.project_dir == d2

        # direct lookup still works: by number and by name
        repl.run_command("/open 1")
        assert app.project_dir == d2

        repl.run_command("/open a")
        assert app.project_dir == d1  # name substring match


async def test_status_prints_stage_states(tmp_path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    app = SubForgeApp(project_dir=d)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.repl.run_command("/status")
        text = transcript_text(app)
        assert "transcription" in text and "export" in text


async def test_unconfigured_transcribe_prints_setup_guidance(tmp_path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    (d / "audio" / "a.wav").write_bytes(b"x")
    app = SubForgeApp(project_dir=d, app_config=AppConfig())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.repl.run_command("/transcribe")
        assert "[SETUP]" in transcript_text(app)


async def test_busy_guard_blocks_double_run(tmp_path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    app = SubForgeApp(project_dir=d)
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        repl._running_stages.add("transcription")
        repl.run_command("/transcribe")
        assert "already running" in transcript_text(app)


async def test_translate_busy_guard(tmp_path):
    d = create_project(tmp_path / "p", ProjectMeta(name="p", source_language="id"))
    app = SubForgeApp(project_dir=d)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.repl._running_stages.add("translation")
        app.repl.run_command("/translate en")
        assert "already running" in transcript_text(app)


# ---- /new interactive locate (@ browse) --------------------------------------


async def test_bare_new_enters_locate_mode_and_esc_cancels(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl

        repl.run_command("/new")
        await pilot.pause()
        assert repl.locate_mode == "new"
        prompt = repl.query_one("#prompt")
        assert "audio" in prompt.placeholder.lower()

        await pilot.press("escape")
        await pilot.pause()
        assert repl.locate_mode is None


async def test_locate_mode_path_submit_creates_project(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBFORGE_PROJECTS_DIR", str(tmp_path / "projects"))
    app = SubForgeApp(app_config=AppConfig(transcription={"provider": "local", "model": "small"}))
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        audio = tmp_path / "song.wav"
        audio.write_bytes(b"x")

        repl.run_command("/new")
        prompt = repl.query_one("#prompt")
        prompt.value = str(audio)
        repl._submit_prompt_value(str(audio))
        await pilot.pause()

        assert repl.locate_mode is None
        assert app.project_dir is not None and app.project_dir.name == "song"


async def test_at_opens_filtered_picker_and_picks_into_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "take01.wav").write_bytes(b"x")
    (tmp_path / "media" / "take02.flac").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("skip me")

    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        repl.run_command("/new")

        repl._submit_prompt_value("@take0")   # @query -> picker filtered to matches
        await pilot.pause()

        from subforge.tui.screens.audio_picker import AudioFilePickerScreen

        picker = app.screen
        assert isinstance(picker, AudioFilePickerScreen)
        names = [str(o.prompt) for o in picker.query_one("OptionList").options]
        assert len(names) == 2 and all("take0" in n for n in names)
        assert not any("notes" in n for n in names)

        # selecting take02 fills the prompt (confirmation still required)
        picker.on_option_list_option_selected(
            type("Evt", (), {"option": type("O", (), {"prompt": names[0]})()})()
        )
        await pilot.pause()
        prompt = repl.query_one("#prompt")
        assert prompt.value.endswith("take02.flac")  # newest first
        assert repl.locate_mode == "new"  # still confirming

        repl._submit_prompt_value(prompt.value)
        await pilot.pause()
        assert app.project_dir.name == "take02"


# ---- Pi-style slash-command autocomplete -----------------------------------


def _prompt(repl: ReplScreen) -> Input:
    return repl.query_one("#prompt", Input)


def _picker_visible(repl: ReplScreen) -> bool:
    return repl.query_one("#autocomplete-container").styles.display != "none"


def _options(repl: ReplScreen) -> list[str]:
    ol = repl.query_one("#autocomplete-list", OptionList)
    return [str(o.prompt) for o in ol.options]


def _submit(repl: ReplScreen, prompt: Input) -> None:
    """Drive the real Enter path with a value-carrying fake Input.Submitted."""
    repl.on_input_submitted(type("Evt", (), {"input": prompt, "value": prompt.value})())


async def test_slash_opens_filtered_autocomplete(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        _prompt(repl).value = "/tr"
        await pilot.pause()
        assert _picker_visible(repl)
        options = _options(repl)
        assert any("/transcribe" in o for o in options)
        assert any("/translate" in o for o in options)
        assert all("/transcribe" in o or "/translate" in o for o in options)


async def test_non_slash_input_hides_autocomplete(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        _prompt(repl).value = "transcribe"
        await pilot.pause()
        assert not _picker_visible(repl)


async def test_autocomplete_up_down_and_enter_fills_prompt(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        prompt = _prompt(repl)
        prompt.value = "/tr"
        await pilot.pause()

        # Enter without navigation selects the first match (highlighted = 0)
        _submit(repl, prompt)
        await pilot.pause()
        assert prompt.value.startswith("/transcribe")
        assert not _picker_visible(repl)

        # Re-open and navigate with arrows before filling
        prompt.value = "/tr"
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert repl.query_one("#autocomplete-list", OptionList).highlighted == 1
        repl._autocomplete_fill()
        assert prompt.value.startswith("/translate")


async def test_tab_fills_highlighted_command(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        prompt = _prompt(repl)
        prompt.value = "/se"
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        assert prompt.value.startswith("/settings")
        assert not _picker_visible(repl)


async def test_escape_hides_autocomplete_keeps_input(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        prompt = _prompt(repl)
        prompt.value = "/tr"
        await pilot.pause()
        assert _picker_visible(repl)
        await pilot.press("escape")
        await pilot.pause()
        assert not _picker_visible(repl)
        assert prompt.value == "/tr"  # input untouched


async def test_locate_mode_disables_autocomplete(tmp_path):
    app = SubForgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        repl.run_command("/new")
        await pilot.pause()
        _prompt(repl).value = "/home/me/audio.wav"  # starts with '/' but it's a path
        await pilot.pause()
        assert not _picker_visible(repl)


async def test_bare_q_routes_to_quit(tmp_path):
    app = SubForgeApp()
    quits: list[bool] = []
    app.exit = lambda: quits.append(True)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        prompt = _prompt(repl)
        prompt.value = "q"
        _submit(repl, prompt)
        assert quits == [True]


async def test_quit_alias_routes_to_quit(tmp_path):
    app = SubForgeApp()
    quits: list[bool] = []
    app.exit = lambda: quits.append(True)  # type: ignore[assignment]
    async with app.run_test() as pilot:
        await pilot.pause()
        repl = app.repl
        prompt = _prompt(repl)
        prompt.value = "quit"
        _submit(repl, prompt)
        assert quits == [True]
