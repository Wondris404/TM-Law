import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_emits_utf8_json_under_cp1252():
    result = subprocess.run(
        [sys.executable, "-m", "scripts.benchmark"],
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"},
        capture_output=True,
        check=True,
        timeout=30,
    )
    output = result.stdout.decode("utf-8")
    assert "odpoveď" in output
    report = json.loads(output)[0]
    assert report["simulated"] is True
    assert report["completed"] == report["total"] == 3
