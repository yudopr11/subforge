"""Hardware detection and model recommendations for whisper.cpp."""

import ctypes
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceSpecs:
    ram_gb: float
    cpu_cores: int
    has_gpu: bool = False
    gpu_name: str | None = None
    recommended_backend: str = "cpu"  # "cuda", "vulkan", or "cpu"


def _detect_gpu() -> tuple[str | None, str]:
    """Detect available GPU and recommend backend ('cuda', 'vulkan', or 'cpu')."""
    # 1. Check for NVIDIA GPU via nvidia-smi
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi and sys.platform == "win32":
        # Check standard Windows paths
        for cand in (
            "C:\\Windows\\System32\\nvidia-smi.exe",
            "C:\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe",
        ):
            if os.path.exists(cand):
                nvsmi = cand
                break

    if nvsmi:
        try:
            res = subprocess.run(
                [nvsmi, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                name = res.stdout.strip().split("\n")[0].strip()
                return name, "cuda"
        except Exception:  # noqa: BLE001, S110
            pass

    # 2. Windows: query Win32_VideoController via PowerShell
    if sys.platform == "win32":
        try:
            ps_cmd = 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                names = [n.strip() for n in res.stdout.strip().split("\n") if n.strip()]
                # Prefer dedicated GPU over integrated graphics
                dedicated = [n for n in names if not any(ig in n.lower() for ig in ("intel(r) uhd", "intel(r) hd", "basic display"))]
                chosen = dedicated[0] if dedicated else names[0]
                lowered = chosen.lower()
                if any(kw in lowered for kw in ("nvidia", "geforce", "rtx", "gtx", "quadro")):
                    return chosen, "cuda"
                if any(kw in lowered for kw in ("amd", "radeon", "arc", "intel", "iris")):
                    return chosen, "vulkan"
                return chosen, "vulkan"
        except Exception:  # noqa: BLE001, S110
            pass

    # 3. Linux: inspect /sys/class/drm or lspci
    if sys.platform.startswith("linux"):
        try:
            if os.path.exists("/proc/driver/nvidia/version"):
                return "NVIDIA GPU", "cuda"
            lspci = shutil.which("lspci")
            if lspci:
                res = subprocess.run([lspci], capture_output=True, text=True, timeout=2.0, check=False)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if "VGA" in line or "3D" in line or "Display" in line:
                            low = line.lower()
                            if "nvidia" in low:
                                return line.split(":", 2)[-1].strip(), "cuda"
                            if "amd" in low or "radeon" in low or "intel" in low:
                                return line.split(":", 2)[-1].strip(), "vulkan"
        except Exception:  # noqa: BLE001, S110
            pass

    return None, "cpu"


def _get_total_ram_gb() -> float:
    # 1. Windows via GlobalMemoryStatusEx
    if sys.platform == "win32":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            # windll is only available on Windows
            windll = getattr(ctypes, "windll", None)
            if windll is not None and windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return float(round(stat.ullTotalPhys / (1024**3), 1))
        except (AttributeError, OSError):
            pass

    # 2. Linux via /proc/meminfo
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return float(round(kb / (1024**2), 1))
        except (OSError, ValueError, IndexError):
            pass

    # 3. macOS / Unix via sysconf
    try:
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if isinstance(pages, int) and isinstance(page_size, int):
                return float(round((pages * page_size) / (1024**3), 1))
    except (OSError, ValueError, AttributeError):
        pass

    return 8.0  # Safe fallback default


class DeviceDetector:
    @staticmethod
    def get_specs() -> DeviceSpecs:
        cores = os.cpu_count() or 4
        ram = _get_total_ram_gb()
        gpu_name, backend = _detect_gpu()
        has_gpu = backend != "cpu" and gpu_name is not None
        return DeviceSpecs(
            ram_gb=ram,
            cpu_cores=cores,
            has_gpu=has_gpu,
            gpu_name=gpu_name,
            recommended_backend=backend,
        )

    @staticmethod
    def recommend_model(specs: DeviceSpecs) -> str:
        if specs.has_gpu:
            return "large-v3-turbo"

        ram = specs.ram_gb
        cores = specs.cpu_cores

        if ram < 6.0 or cores <= 2:
            return "tiny"
        if ram < 10.0 or cores < 4:
            return "base"
        if ram < 16.0 or cores < 6:
            return "small"
        if ram <= 32.0 or cores < 12:
            return "large-v3-turbo"
        return "large-v3"
