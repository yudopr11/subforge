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


def detect_player(which: Callable[[str], str | None] = shutil.which) -> tuple[str, dict[str, str]] | None:
    for binary, spec in _SPECS.items():
        if which(binary):
            return binary, spec
    return None


def build_command(
    player_binary: str,
    audio_path: Path,
    start: float,
    duration: float,
    spec: dict[str, str],
) -> list[str]:
    """CLI args playing [start, start+duration) of the audio file."""
    if player_binary == "powershell":
        abs_uri = audio_path.resolve().as_uri()
        ms_wait = max(100, int(duration * 1000))
        ps_code = (
            f"Add-Type -AssemblyName presentationCore;"
            f"$p = New-Object System.Windows.Media.MediaPlayer;"
            f"$p.Open([System.Uri]'{abs_uri}');"
            f"Start-Sleep -Milliseconds 300;"
            f"$p.Position = [System.TimeSpan]::FromSeconds({start:.3f});"
            f"$p.Play();"
            f"Start-Sleep -Milliseconds {ms_wait};"
            f"$p.Stop();"
            f"$p.Close();"
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
