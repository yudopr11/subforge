"""Management and automated self-provisioning of binary dependencies (whisper-cli, ffmpeg)."""

import io
import platform
import shutil
import sys
import tarfile
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
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-cublas-12.4.0-bin-x64.zip"
)
WHISPER_CPP_LINUX_X64_TAR = (
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-ubuntu-x64.tar.gz"
)
WHISPER_CPP_LINUX_ARM64_TAR = (
    "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-ubuntu-arm64.tar.gz"
)

FFMPEG_WIN_X64 = (
    "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-win32-x64"
)
FFMPEG_LINUX_X64 = (
    "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-linux-x64"
)


def find_in_path_or_bin(tool_name: str, bin_dir: Path | None = None) -> Path | None:
    """Find a binary in the app's bin directory or system PATH."""
    target_dir = bin_dir or get_bin_dir()
    is_windows = sys.platform == "win32"

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


def _download_stream_bytes(
    client: httpx.Client,
    url: str,
    description: str,
    progress_callback: Callable[[float, str], Any] | None = None,
) -> bytes:
    with client.stream("GET", url) as response:
        response.raise_for_status()
        total_header = response.headers.get("content-length")
        total_bytes = int(total_header) if total_header and total_header.isdigit() else 0
        buffer = bytearray()
        downloaded = 0
        for chunk in response.iter_bytes(chunk_size=65536):
            if chunk:
                buffer.extend(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    if total_bytes > 0:
                        pct = downloaded / total_bytes
                        dl_mb = downloaded / (1024 * 1024)
                        tot_mb = total_bytes / (1024 * 1024)
                        progress_callback(
                            pct,
                            f"{description}: {dl_mb:.1f}/{tot_mb:.1f} MB ({int(pct * 100)}%)",
                        )
                    else:
                        dl_mb = downloaded / (1024 * 1024)
                        progress_callback(0.0, f"{description}: {dl_mb:.1f} MB")
        return bytes(buffer)


def _download_stream_to_file(
    client: httpx.Client,
    url: str,
    target_path: Path,
    description: str,
    progress_callback: Callable[[float, str], Any] | None = None,
) -> None:
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with client.stream("GET", url) as response:
        response.raise_for_status()
        total_header = response.headers.get("content-length")
        total_bytes = int(total_header) if total_header and total_header.isdigit() else 0
        downloaded = 0
        with open(tmp_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        if total_bytes > 0:
                            pct = downloaded / total_bytes
                            dl_mb = downloaded / (1024 * 1024)
                            tot_mb = total_bytes / (1024 * 1024)
                            progress_callback(
                                pct,
                                f"{description}: {dl_mb:.1f}/{tot_mb:.1f} MB ({int(pct * 100)}%)",
                            )
                        else:
                            dl_mb = downloaded / (1024 * 1024)
                            progress_callback(0.0, f"{description}: {dl_mb:.1f} MB")
    if target_path.exists():
        target_path.unlink()
    tmp_path.rename(target_path)


def _extract_archive(content: bytes, dest_dir: Path) -> None:
    """Extract zip or tar.gz archive into dest_dir, stripping root folder prefix if present."""
    # Try tar archive first (.tar.gz / .tar)
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if len(parts) > 1 and (
                    parts[0].startswith("whisper-") or parts[0] in ("Release", "build")
                ):
                    fn = Path(*parts[1:])
                else:
                    fn = Path(member.name)

                if member.isdir():
                    (dest_dir / fn).mkdir(parents=True, exist_ok=True)
                elif member.isfile() or member.issym():
                    target = dest_dir / fn
                    target.parent.mkdir(parents=True, exist_ok=True)
                    f = tar.extractfile(member)
                    if f:
                        target.write_bytes(f.read())
                        if sys.platform != "win32":
                            target.chmod(0o755)
            return
    except (tarfile.TarError, io.UnsupportedOperation):
        pass

    # Try zip archive
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for zip_member in z.infolist():
                fn_str = (
                    zip_member.filename.removeprefix("Release/")
                    .removeprefix("build/bin/Release/")
                    .removeprefix("build/bin/")
                )
                parts = Path(fn_str).parts
                if len(parts) > 1 and parts[0].startswith("whisper-"):
                    fn_str = str(Path(*parts[1:]))

                if fn_str and not fn_str.endswith("/"):
                    target_file = dest_dir / fn_str
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_bytes(z.read(zip_member))
                    if sys.platform != "win32":
                        target_file.chmod(0o755)
            return
    except zipfile.BadZipFile:
        pass


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

    desc = f"Downloading whisper.cpp prebuilt binaries ({backend} backend)"
    if progress_callback:
        progress_callback(0.0, f"{desc}...")

    is_windows = sys.platform == "win32"
    machine = platform.machine().lower()

    if is_windows:
        if backend == "cuda":
            url = WHISPER_CPP_WIN_CUDA_ZIP
        elif backend == "vulkan":
            url = WHISPER_CPP_WIN_VULKAN_ZIP
        else:
            url = WHISPER_CPP_WIN_X64_ZIP
        fallback_url = WHISPER_CPP_WIN_X64_ZIP
    else:
        if machine in ("aarch64", "arm64"):
            url = WHISPER_CPP_LINUX_ARM64_TAR
            fallback_url = WHISPER_CPP_LINUX_ARM64_TAR
        else:
            url = WHISPER_CPP_LINUX_X64_TAR
            fallback_url = WHISPER_CPP_LINUX_X64_TAR

    try:
        content = _download_stream_bytes(client, url, desc, progress_callback)
    except Exception:  # noqa: BLE001
        fallback_desc = "Downloading whisper.cpp prebuilt binaries (fallback)"
        content = _download_stream_bytes(client, fallback_url, fallback_desc, progress_callback)

    _extract_archive(content, bin_dir)

    cli_exe = bin_dir / ("whisper-cli.exe" if is_windows else "whisper-cli")
    if cli_exe.exists():
        return cli_exe

    main_exe = bin_dir / ("main.exe" if is_windows else "main")
    if main_exe.exists():
        return main_exe

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

    is_windows = sys.platform == "win32"
    target_exe = bin_dir / ("ffmpeg.exe" if is_windows else "ffmpeg")
    url = FFMPEG_WIN_X64 if is_windows else FFMPEG_LINUX_X64

    _download_stream_to_file(
        client,
        url,
        target_exe,
        "Downloading static ffmpeg binary",
        progress_callback,
    )
    if not is_windows:
        target_exe.chmod(0o755)

    return target_exe
