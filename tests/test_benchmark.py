import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from scripts.compare_model_runs import compare

ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_emits_utf8_json_under_cp1252():
    result = subprocess.run(
        [sys.executable, "-m", "scripts.benchmark", "--include-answers", "--summary"],
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"},
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert "Uvažovanie" in result.stderr.decode("utf-8")
    output = result.stdout.decode("utf-8")
    assert "odpoveď" in output
    report = json.loads(output)[0]
    assert report["simulated"] is True
    assert report["completed"] == report["total"] == 3

    legacy_settings = {
        key: value
        for key, value in report["settings"].items()
        if key not in {"cpu_threads", "ollama_use_mmap"}
    }
    assert (
        compare(report | {"settings": legacy_settings}, report)["matched_completed_responses"] == 3
    )
    with pytest.raises(ValueError, match="execution settings"):
        compare(report, report | {"settings": report["settings"] | {"cpu_threads": 2}})


def test_real_benchmark_comparison_uses_one_corpus_and_validated_options(tmp_path):
    requests = []

    class StubOllama(BaseHTTPRequestHandler):
        def respond(self, body):
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            assert self.path == "/api/tags"
            self.respond(
                b'{"models":[{"name":"qwen3.5:4b","digest":"4b-hash"},'
                b'{"name":"qwen3.5:9b","digest":"9b-hash"}]}'
            )

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/api/show":
                self.respond(b'{"thinking":{"values":[true,false]}}')
                return
            assert self.path == "/api/chat"
            requests.append(payload)
            lines = [
                {"message": {"thinking": "interný text [[never/store]]"}},
                {"message": {"content": "Odpoveď bez zdroja [[bad/id]]"}},
                {
                    "done": True,
                    "done_reason": "stop",
                    "eval_count": 10,
                    "eval_duration": 1000000000,
                },
            ]
            self.respond(("\n".join(map(json.dumps, lines)) + "\n").encode("utf-8"))

    output = tmp_path / "výsledky.json"
    with ThreadingHTTPServer(("127.0.0.1", 0), StubOllama) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.benchmark",
                    "--model",
                    "qwen3.5:4b",
                    "--model",
                    "qwen3.5:9b",
                    "--reasoning",
                    "on",
                    "--reasoning",
                    "off",
                    "--context-window",
                    "2048",
                    "--repeats",
                    "2",
                    "--temperature",
                    "0.2",
                    "--output",
                    str(output),
                    "--summary",
                ],
                cwd=ROOT,
                env={**os.environ, "TM_LAW_OLLAMA_URL": f"http://127.0.0.1:{server.server_port}"},
                capture_output=True,
                check=True,
                timeout=45,
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)

    report_text = output.read_text(encoding="utf-8")
    report = json.loads(report_text)
    assert result.stdout == b"" and "Uvažovanie" in result.stderr.decode("utf-8")
    assert len(report) == 4 and len(requests) == 8
    assert len({run["corpus_sha256"] for run in report}) == 1
    assert len({run["dataset_sha256"] for run in report}) == 1
    assert {payload["think"] for payload in requests} == {True, False}
    assert all(
        payload["options"]["seed"] == 42 and payload["keep_alive"] == 0 for payload in requests
    )
    assert all(payload["options"]["num_ctx"] == 2048 for payload in requests)
    assert all("num_thread" not in payload["options"] for payload in requests)
    assert all("use_mmap" not in payload["options"] for payload in requests)
    assert all(run["settings"]["cpu_threads"] is None for run in report)
    assert len({payload["messages"][-1]["content"] for payload in requests}) == 1
    assert all(run["completed"] == 2 and not run["simulated"] for run in report)
    assert "never/store" not in report_text and "Odpoveď bez zdroja" not in report_text
    for run in report:
        assert run["summary"]["median_tokens_per_second"] == 10
        assert run["summary"]["rejected_identifiers"] == 2
        assert run["cases"][0]["verified_ids"] == []
        assert run["cases"][0]["rejected_ids"] == ["bad/id"]
        assert run["cases"][0]["expert_review"]["legal_correctness"] is None


def test_benchmark_thread_default_ignores_env_and_rejects_invalid_counts(tmp_path):
    output = tmp_path / "default.json"
    env = os.environ.copy()
    env["TM_LAW_OLLAMA_NUM_THREADS"] = "2"
    env["TM_LAW_OLLAMA_URL"] = "http://127.0.0.1:1"
    result = subprocess.run(
        [sys.executable, "-m", "scripts.benchmark", "--output", str(output)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        check=True,
        timeout=30,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert all(run["simulated"] and run["settings"]["cpu_threads"] is None for run in report)
    for value in ("0", "257", "1000"):
        rejected = subprocess.run(
            [sys.executable, "-m", "scripts.benchmark", "--num-threads", value],
            cwd=ROOT,
            env=env,
            capture_output=True,
            timeout=30,
        )
        assert rejected.returncode != 0
        assert "256" in rejected.stderr.decode("utf-8")


def test_benchmark_two_threads_reach_payload_and_report(tmp_path):
    requests = []

    class StubOllama(BaseHTTPRequestHandler):
        def respond(self, body):
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            assert self.path == "/api/tags"
            self.respond(b'{"models":[{"name":"qwen3.5:4b","digest":"4b-hash"}]}')

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/api/chat"
            requests.append(payload)
            self.respond(
                b'{"message":{"content":"Odpoved bez citacie."},"done":false}\n'
                b'{"done":true,"done_reason":"stop","eval_count":2,"eval_duration":1000000000}\n'
            )

    output = tmp_path / "two-threads.json"
    with ThreadingHTTPServer(("127.0.0.1", 0), StubOllama) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.benchmark",
                    "--model",
                    "qwen3.5:4b",
                    "--context-window",
                    "2048",
                    "--device",
                    "cpu",
                    "--num-threads",
                    "2",
                    "--mmap",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env={
                    **os.environ,
                    "TM_LAW_OLLAMA_URL": f"http://127.0.0.1:{server.server_port}",
                    "TM_LAW_OLLAMA_NUM_THREADS": "8",
                },
                capture_output=True,
                check=True,
                timeout=30,
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)

    report = json.loads(output.read_text(encoding="utf-8"))
    assert result.returncode == 0 and len(requests) == 1
    assert requests[0]["options"]["num_thread"] == 2
    assert requests[0]["options"]["num_gpu"] == 0
    assert requests[0]["options"]["use_mmap"] is True
    assert report[0]["settings"]["cpu_threads"] == 2
    assert report[0]["settings"]["ollama_use_mmap"] is True
    assert report[0]["simulated"] is False
