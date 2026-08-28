"""Management and automated self-provisioning of binary dependencies (whisper-cli, ffmpeg)."""

import io
import os
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from subforge.app.storage import get_bin_dir

WHISPER_CPP_WIN_X64_ZIP = (
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-x64.zip"
)
WHISPER_CPP_WIN_VULKAN_ZIP = (
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-vulkan-bin-x64.zip"
)
WHISPER_CPP_WIN_CUDA_ZIP = (
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-cublas-12.2.0-bin-x64.zip"
)
WHISPER_CPP_LINUX_X64_ZIP = (
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-linux-x64.zip"
)
WHISPER_CPP_LINUX_VULKAN_ZIP = (
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-vulkan-bin-linux-x64.zip"
)

FFMPEG_WIN_X64 = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0/win32-x64"
FFMPEG_LINUX_X64 = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0/linux-x64"


def find_in_path_or_bin(tool_name: str, bin_dir: Path | None = None) -> Path | None:
    """Find a binary in the app's bin directory or system PATH."""
    target_dir = bin_dir or get_bin_dir()
    is_windows = os.name == "nt"

    # 1. Look in managed app bin dir
    candidates: list[Path] = []
    if is_windows:
        candidates.append(target_dir / f"{tool_name}.exe")
        candidates.append(target_dir / tool_name)
    else:
        candidates.append(target_dir / tool_name)
        candidates.append(target_dir / f"{tool_name}.exe")

    for c in candidates:
        if c.is_file():
            return c

    # 2. Look in system PATH
    which_names = [f"{tool_name}.exe", tool_name] if is_windows else [tool_name, f"{tool_name}.exe"]
    for name in which_names:
        which_path = shutil.which(name)
        if which_path and not which_path.lower().endswith((".cpl", ".dll")):
            return Path(which_path)

    return None


def ensure_whisper_binary(
    progress_callback: Callable[[float, str], Any] | None = None,
    dest_dir: Path | None = None,
    http_client: httpx.Client | None = None,
    backend: str | None = None,
) -> Path:
    """Ensure whisper-cli binary is available. Downloads if missing."""
    bin_dir = dest_dir or get_bin_dir()
    existing = find_in_path_or_bin("whisper-cli", bin_dir=bin_dir)
    if existing:
        return existing

    # Also check legacy alias 'main'
    existing_main = find_in_path_or_bin("main", bin_dir=bin_dir)
    if existing_main:
        return existing_main

    # Download prebuilt binary
    bin_dir.mkdir(parents=True, exist_ok=True)
    client = http_client or httpx.Client(timeout=120.0, follow_redirects=True)

    if backend is None:
        from subforge.app.device import DeviceDetector

        backend = DeviceDetector.get_specs().recommended_backend

    if progress_callback:
        progress_callback(0.1, f"Downloading whisper.cpp prebuilt binaries ({backend} backend)...")

    if os.name == "nt":
        if backend == "cuda":
            url = WHISPER_CPP_WIN_CUDA_ZIP
        elif backend == "vulkan":
            url = WHISPER_CPP_WIN_VULKAN_ZIP
        else:
            url = WHISPER_CPP_WIN_X64_ZIP
    else:
        if backend == "vulkan":
            url = WHISPER_CPP_LINUX_VULKAN_ZIP
        else:
            url = WHISPER_CPP_LINUX_X64_ZIP

    try:
        res = client.get(url)
        res.raise_for_status()
    except Exception:  # noqa: BLE001
        fallback_url = WHISPER_CPP_WIN_X64_ZIP if os.name == "nt" else WHISPER_CPP_LINUX_X64_ZIP
        res = client.get(fallback_url)
        res.raise_for_status()

    if os.name == "nt":
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            for member in z.infolist():
                fn = member.filename.removeprefix("Release/").removeprefix("build/bin/Release/")
                if fn and not fn.endswith("/"):
                    target_file = bin_dir / fn
                    target_file.write_bytes(z.read(member))
        cli_exe = bin_dir / "whisper-cli.exe"
        if cli_exe.exists():
            return cli_exe
    else:
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            for member in z.infolist():
                fn = member.filename.removeprefix("Release/").removeprefix("build/bin/")
                if fn and not fn.endswith("/"):
                    target_file = bin_dir / fn
                    target_file.write_bytes(z.read(member))
                    target_file.chmod(0o755)
        cli_bin = bin_dir / "whisper-cli"
        if cli_bin.exists():
            return cli_bin

    raise RuntimeError(
        "Could not automatically locate or install whisper-cli. "
        "Please install whisper.cpp manually and add 'whisper-cli' to your system PATH."
    )


def ensure_ffmpeg_binary(
    progress_callback: Callable[[float, str], Any] | None = None,
    dest_dir: Path | None = None,
    http_client: httpx.Client | None = None,
) -> Path:
    """Ensure ffmpeg binary is available. Downloads standalone static binary if missing."""
    bin_dir = dest_dir or get_bin_dir()
    existing = find_in_path_or_bin("ffmpeg", bin_dir=bin_dir)
    if existing:
        return existing

    bin_dir.mkdir(parents=True, exist_ok=True)
    client = http_client or httpx.Client(timeout=180.0, follow_redirects=True)

    if progress_callback:
        progress_callback(0.1, "Downloading static ffmpeg binary...")

    target_exe = bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    url = FFMPEG_WIN_X64 if os.name == "nt" else FFMPEG_LINUX_X64

    res = client.get(url)
    res.raise_for_status()
    target_exe.write_bytes(res.content)
    if os.name != "nt":
        target_exe.chmod(0o755)

    return target_exe
