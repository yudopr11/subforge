import subprocess
import sys


def test_version_flag():
    proc = subprocess.run(
        [sys.executable, "-m", "subforge.cli.main", "--version"], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert proc.stdout.strip().startswith("subforge ")
