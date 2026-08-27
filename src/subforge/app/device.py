"""Hardware detection and model recommendations for whisper.cpp."""

import ctypes
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceSpecs:
    ram_gb: float
    cpu_cores: int


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
        return DeviceSpecs(ram_gb=ram, cpu_cores=cores)

    @staticmethod
    def recommend_model(specs: DeviceSpecs) -> str:
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
