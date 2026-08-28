"""Audio preview playback for caption review (PRD §9 verify-what-you-edit).

Shells out to whatever CLI player exists on the system; no audio libraries are
added as dependencies. Playback is per-segment: start at ``start``, stop after
the segment duration.
"""

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlayerSpec:
    binary: str
    lead_args: tuple[str, ...]  # global flags before the file
    start_flag: str  # takes value via "=" e.g. "-ss" handled uniformly below
    length_flag: str


_SPECS: dict[str, dict[str, str]] = {
    "ffplay": {"lead": "-nodisp -autoexit -loglevel quiet", "start": "-ss", "length": "-t"},
    "mpv": {"lead": "--really-quiet --no-video", "start": "--start=", "length": "--length="},
    "cvlc": {"lead": "--intf dummy --play-and-exit", "start": "--start-time=", "length": "--stop-time="},
    "powershell": {"lead": "powershell-native", "start": "", "length": ""},
}


def detect_player(which: Callable[[str], str | None] | None = None) -> tuple[str, dict[str, str]] | None:
    from subforge.app.binaries import find_in_path_or_bin

    for binary, spec in _SPECS.items():
        if which is not None:
            if which(binary):
                return binary, spec
        else:
            found = find_in_path_or_bin(binary)
            if found:
                return str(found), spec
            if binary == "powershell" and shutil.which("powershell"):
                return "powershell", spec
    return None


def build_command(
    player_binary: str,
    audio_path: Path,
    start: float,
    duration: float,
    spec: dict[str, str],
) -> list[str]:
    """CLI args playing [start, start+duration) of the audio file."""
    if player_binary.lower().endswith("powershell") or player_binary == "powershell":
        from subforge.app.binaries import find_in_path_or_bin

        ffmpeg_bin = find_in_path_or_bin("ffmpeg")
        ffmpeg_cmd = f'& "{ffmpeg_bin}"' if ffmpeg_bin else "ffmpeg"
        abs_audio = str(audio_path.resolve())
        ms_wait = max(100, int(duration * 1000))
        ps_code = (
            f'$tmp = Join-Path $env:TEMP "subforge_preview_{abs(hash(str(audio_path))) % 10000}.wav"; '
            f'{ffmpeg_cmd} -y -ss {start:.3f} -t {duration:.3f} -i "{abs_audio}" -vn -acodec pcm_s16le -ar 44100 -ac 2 $tmp -loglevel quiet; '
            f'if (Test-Path $tmp) {{ (New-Object System.Media.SoundPlayer $tmp).PlaySync(); Remove-Item -Force $tmp -ErrorAction SilentlyContinue }} '
            f'else {{ Add-Type -AssemblyName presentationCore; $p = New-Object System.Windows.Media.MediaPlayer; $p.Open([System.Uri]"{audio_path.resolve().as_uri()}"); Start-Sleep -Milliseconds 200; $p.Position = [System.TimeSpan]::FromSeconds({start:.3f}); $p.Play(); Start-Sleep -Milliseconds {ms_wait}; $p.Stop(); $p.Close() }}'
        )
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_code]

    start_flag, length_flag = spec["start"], spec["length"]
    eq_start = start_flag.endswith("=")
    eq_len = length_flag.endswith("=")
    cmd = [player_binary]
    if spec["lead"]:
        cmd.extend(spec["lead"].split())
    if eq_start:
        cmd.append(f"{start_flag}{start:.3f}")
    else:
        cmd.extend([start_flag, f"{start:.3f}"])
    if eq_len:
        cmd.append(f"{length_flag}{duration:.3f}")
    else:
        cmd.extend([length_flag, f"{duration:.3f}"])
    cmd.append(str(audio_path))
    return cmd


class SegmentPlayer:
    """Plays one segment at a time; starting a new one stops the previous."""

    def __init__(
        self,
        audio_path: Path,
        popen: Callable[..., subprocess.Popen[bytes]] | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.audio_path = audio_path
        self._popen_factory = popen or subprocess.Popen
        detected = detect_player(which)
        self.available = detected is not None
        self.player_name = detected[0] if detected else ""
        self._spec = detected[1] if detected else {}
        self._process: subprocess.Popen[bytes] | None = None

    def play_segment(self, start: float, end: float) -> str:
        """Start playback; returns a user-facing status message."""
        if not self.available:
            return (
                "[ERROR] No audio player found — preview requires ffmpeg or PowerShell.\n"
                "Install ffmpeg: https://ffmpeg.org"
            )
        self.stop()
        duration = max(0.0, end - start)
        cmd = build_command(self.player_name, self.audio_path, start, duration, self._spec)
        self._process = self._popen_factory(  # DEV: deliberately fire-and-forget
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return f"▶ {self.audio_path.name} {start:.2f}s → {end:.2f}s ({self.player_name})"

    def stop(self) -> str:
        proc, self._process = self._process, None
        if proc is None or proc.poll() is not None:
            return "■ stopped"
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            try:
                proc.kill()
            except OSError:  # pragma: no cover — process already gone
                pass
        return "■ stopped"
