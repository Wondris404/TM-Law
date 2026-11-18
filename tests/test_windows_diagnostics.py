import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows CIM and PowerShell inventory")
def test_windows_inventory_runs_without_starting_ollama(tmp_path):
    path = tmp_path / "inventory.json"
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "scripts" / "diagnose-windows.ps1"),
            "-Output",
            str(path),
        ],
        check=True,
        timeout=45,
        capture_output=True,
    )
    report = json.loads(path.read_bytes())
    assert report["schema"] == 1
    assert report["cpu"][0]["logical_processors"] > 0
    assert report["memory"]["os_visible_bytes"] >= report["memory"]["os_used_bytes"] > 0
    assert report["tools"]["powershell"]
    assert report["ollama"]["endpoint"] == "http://127.0.0.1:11434"
