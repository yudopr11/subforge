import sys
from pathlib import Path
from unittest.mock import patch

from subforge.app.binaries import (
    ensure_ffmpeg_binary,
    ensure_whisper_binary,
    find_in_path_or_bin,
)


def test_find_in_path_or_bin_existing(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_exe = bin_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    fake_exe.write_text("fake binary")

    monkeypatch.setenv("SUBFORGE_BIN_DIR", str(bin_dir))
    found = find_in_path_or_bin("ffmpeg")
    assert found == fake_exe


def test_ensure_whisper_binary_cached(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target_name = "whisper-cli.exe" if sys.platform == "win32" else "whisper-cli"
    (bin_dir / target_name).write_text("fake whisper binary")

    monkeypatch.setenv("SUBFORGE_BIN_DIR", str(bin_dir))
    path = ensure_whisper_binary()
    assert path == bin_dir / target_name


def test_ensure_ffmpeg_binary_cached(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    (bin_dir / target_name).write_text("fake ffmpeg binary")

    monkeypatch.setenv("SUBFORGE_BIN_DIR", str(bin_dir))
    path = ensure_ffmpeg_binary()
    assert path == bin_dir / target_name


def test_find_in_path_or_bin_system_fallback(monkeypatch):
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        found = find_in_path_or_bin("ffmpeg")
        assert found == Path("/usr/bin/ffmpeg")


def test_find_in_path_or_bin_none_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SUBFORGE_BIN_DIR", str(tmp_path / "empty_bin"))
    with patch("shutil.which", return_value=None):
        found = find_in_path_or_bin("nonexistent_tool_xyz")
        assert found is None


def test_ensure_ffmpeg_binary_download(tmp_path: Path, monkeypatch):
    import httpx

    bin_dir = tmp_path / "download_bin"
    monkeypatch.setenv("SUBFORGE_BIN_DIR", str(bin_dir))

    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=b"fake-ffmpeg-content"))
    client = httpx.Client(transport=transport)

    with patch("shutil.which", return_value=None):
        path = ensure_ffmpeg_binary(dest_dir=bin_dir, http_client=client)
        assert path.exists()
        assert path.read_bytes() == b"fake-ffmpeg-content"


def test_ensure_whisper_binary_download(tmp_path: Path, monkeypatch):
    import io
    import zipfile

    import httpx

    bin_dir = tmp_path / "download_whisper_bin"
    monkeypatch.setenv("SUBFORGE_BIN_DIR", str(bin_dir))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Release/whisper-cli.exe" if sys.platform == "win32" else "Release/whisper-cli", b"fake-whisper-binary")
        z.writestr("Release/whisper.dll", b"fake-dll")
    zip_bytes = buf.getvalue()

    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=zip_bytes))
    client = httpx.Client(transport=transport)

    with patch("shutil.which", return_value=None):
        path = ensure_whisper_binary(dest_dir=bin_dir, http_client=client)
        assert path.exists()
        assert path.read_bytes() == b"fake-whisper-binary"

