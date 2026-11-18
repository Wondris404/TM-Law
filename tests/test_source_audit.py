import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

from tm_law.evaluation import BenchmarkCase
from tm_law.schemas import LegalVersion
from tm_law.source_audit import audit_sources
from tm_law.store import Store

ROOT = Path(__file__).resolve().parents[1]


def original_example(tmp_path):
    remote_placeholder = "https://example.test/publication"
    corpus = Store(tmp_path / "corpus")
    corpus.initialize()
    text = "Skúšobná pasáž vytvorená pre unit test."
    version = LegalVersion(
        version_id="demo-version",
        title="Fiktívna technická skúška",
        kind="predpis",
        authority="Test",
        source_url=remote_placeholder,
        acquired_on=date(2026, 11, 18),
        effective_from=date(2022, 1, 1),
        effective_until=date(2024, 1, 1),
        effective_basis="Testovaný interval.",
        provenance="Synthetic unit test.",
        reuse_terms="MIT",
        original_sha256=hashlib.sha256(text.encode()).hexdigest(),
        passages=[{"source_id": "s1", "text": text}],
    )
    return corpus, version, (".txt", text.encode())


def benchmark_case(day="2023-12-31", source="demo-version/s1"):
    return BenchmarkCase(
        id="historical-check",
        question="Aký je účinný testovací úsek?",
        category="historické znenia",
        as_of=day,
        expected_sources=[source],
    )


def test_audit_checks_archive_passage_and_exclusive_effective_end(tmp_path):
    corpus, version, original = original_example(tmp_path)
    corpus.import_version(version)
    plain = audit_sources(corpus, [benchmark_case()])
    assert not plain["ready"] and plain["cases"][0]["references"][0]["problems"] == [
        "missing_original"
    ]
    corpus.import_version(version, original)
    result = audit_sources(corpus, [benchmark_case()])
    assert result["ready"] and result["cases_with_verified_references"] == 1
    expired = audit_sources(corpus, [benchmark_case(day="2024-01-01")])
    assert expired["cases"][0]["references"][0]["problems"] == ["outside_effective_interval"]
    no_date = audit_sources(corpus, [benchmark_case(day=None)])
    assert no_date["cases"][0]["problems"] == ["missing_decisive_date"]
    with sqlite3.connect(corpus.legal) as conn:
        conn.execute("UPDATE legal_original SET payload=?", (b"modified",))
    invalid = audit_sources(corpus, [benchmark_case()])
    assert invalid["cases"][0]["references"][0]["problems"] == ["original_digest_mismatch"]


def test_benchmark_source_gate_refuses_before_runtime(tmp_path):
    corpus, _, _ = original_example(tmp_path)
    cases = tmp_path / "audit.jsonl"
    cases.write_text(benchmark_case().model_dump_json(), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.benchmark",
            "--model",
            "qwen3.5:4b",
            "--cases",
            str(cases),
            "--data-dir",
            str(corpus.directory),
            "--require-source-audit",
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["kind"] == "source_audit"
    assert report["failed_referenced_cases"] == 1 and not report["ready"]
    assert report["cases"][0]["references"][0]["problems"] == ["missing_passage"]
