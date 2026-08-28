from pathlib import Path

from subforge.app.audio_player import SegmentPlayer, build_command, detect_player


def test_detect_player_prefers_ffplay_first():
    spec = detect_player(which=lambda b: "/usr/bin/ffplay" if b == "ffplay" else None)
    assert spec is not None
    assert spec[0] == "ffplay"


def test_detect_player_falls_back_to_mpv_then_none():
    spec = detect_player(which=lambda b: "/usr/bin/mpv" if b == "mpv" else None)
    assert spec is not None and spec[0] == "mpv"
    spec_ps = detect_player(which=lambda b: "powershell" if b == "powershell" else None)
    assert spec_ps is not None and spec_ps[0] == "powershell"
    assert detect_player(which=lambda b: None) is None


def test_build_command_powershell_style():
    cmd = build_command("powershell", Path("/a/b.mp3"), 1.0, 3.5, {})
    assert cmd[0] == "powershell"
    assert "SoundPlayer" in cmd[-1] or "MediaPlayer" in cmd[-1]
    assert "-ss 1.000" in cmd[-1]
    assert "-t 3.500" in cmd[-1]



def test_build_command_ffplay_style():
    cmd = build_command(
        "ffplay", Path("/a/b.wav"), 1.5, 2.25,
        {"lead": "-nodisp -autoexit -loglevel quiet", "start": "-ss", "length": "-t"},
    )
    assert cmd[0] == "ffplay"
    assert cmd[-1] == str(Path("/a/b.wav"))
    assert cmd[cmd.index("-ss") + 1] == "1.500"
    assert cmd[cmd.index("-t") + 1] == "2.250"


def test_build_command_mpv_equals_style():
    cmd = build_command("mpv", Path("a.wav"), 0.0, 3.0,
                        {"lead": "--really-quiet", "start": "--start=", "length": "--length="})
    assert "--start=0.000" in cmd and "--length=3.000" in cmd and cmd[-1] == "a.wav"


class FakeProc:
    def __init__(self):
        self.terminated = False
        self.cmd: list[str] = []

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


def test_player_plans_and_stops_process(tmp_path):
    audio = tmp_path / "a.wav"
    procs: list[FakeProc] = []

    def fake_popen(cmd, **kwargs):
        proc = FakeProc()
        proc.cmd = cmd
        procs.append(proc)
        return proc

    player = SegmentPlayer(audio, popen=fake_popen, which=lambda b: "/usr/bin/ffplay" if b == "ffplay" else None)
    status = player.play_segment(1.2, 3.4)
    assert "▶" in status and len(procs) == 1
    first = procs[0]
    assert first.cmd[first.cmd.index("-ss") + 1] == "1.200"

    # second start stops the first
    player.play_segment(0.0, 1.0)
    assert first.terminated is True

    stop_status = player.stop()
    assert "■" in stop_status


def test_player_unavailable_reports_install_hint(tmp_path):
    player = SegmentPlayer(tmp_path / "a.wav", which=lambda b: None)
    status = player.play_segment(0.0, 1.0)
    assert "[ERROR]" in status and "ffmpeg" in status
