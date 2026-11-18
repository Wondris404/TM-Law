"""Check benchmark references against the exact local corpus used for evaluation."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date
from functools import lru_cache
from subprocess import TimeoutExpired

from .corpus import normalized, original_text
from .evaluation import BenchmarkCase
from .store import Store

REFERENCE_QUERY = """
SELECT p.text, p.norm_status, v.metadata, a.sha256 AS archived_sha256
FROM passage p
JOIN legal_version v USING(version_id)
LEFT JOIN legal_version_original a USING(version_id)
WHERE p.version_id=? AND p.source_id=?
"""


def temporal_problem(metadata: dict, as_of: date | None) -> str | None:
    if as_of is None:
        return None
    day = as_of.isoformat()
    if metadata["kind"] == "rozhodnutie":
        issued = metadata.get("decision_date")
        if not issued:
            return "unknown_decision_date"
        return "after_decisive_date" if issued > day else None
    start = metadata.get("effective_from")
    end = metadata.get("effective_until")
    if not start or not (end or metadata.get("open_ended")) or not metadata.get("effective_basis"):
        return "unsubstantiated_effectiveness"
    if day < start or (end and day >= end):
        return "outside_effective_interval"
    return None


def audit_sources(store: Store, cases: list[BenchmarkCase]) -> dict:
    with closing(store.connect(store.legal)) as conn:
        conn.execute("BEGIN")
        return _audit_snapshot(conn, cases)


def _audit_snapshot(conn: sqlite3.Connection, cases: list[BenchmarkCase]) -> dict:
    @lru_cache(maxsize=4)
    def archive(sha256: str) -> tuple[str | None, str | None]:
        row = conn.execute(
            "SELECT suffix, payload FROM legal_original WHERE sha256=?", (sha256,)
        ).fetchone()
        if row is None:
            return "missing_original", None
        payload = row["payload"]
        if hashlib.sha256(payload).hexdigest() != sha256:
            return "original_digest_mismatch", None
        try:
            return None, normalized(original_text(payload, row["suffix"]))
        except (OSError, ValueError, TimeoutExpired):
            return "original_text_unavailable", None

    def check(case: BenchmarkCase, citation: str) -> dict:
        row = conn.execute(REFERENCE_QUERY, citation.split("/", 1)).fetchone()
        if row is None:
            return {"citation_id": citation, "problems": ["missing_passage"]}
        metadata = json.loads(row["metadata"])
        sha256 = row["archived_sha256"]
        problems = []
        if metadata["fictional"]:
            problems.append("fictional_source")
        if row["norm_status"] == "repealed":
            problems.append("repealed_passage")
        if problem := temporal_problem(metadata, case.as_of):
            problems.append(problem)
        if not sha256:
            problems.append("missing_original")
        elif sha256 != metadata.get("original_sha256"):
            problems.append("archive_link_mismatch")
        else:
            issue, text = archive(sha256)
            if issue:
                problems.append(issue)
            elif normalized(row["text"]) not in text:
                problems.append("passage_not_in_original")
        return {
            "citation_id": citation,
            "original_sha256": sha256,
            "problems": problems,
        }

    rows = []
    grounded = failed = excluded = unreferenced = 0
    for case in cases:
        references = []
        errors = []
        if case.fictional:
            status = "fictional_case"
            excluded += 1
        elif not case.expected_sources:
            status = "no_expected_references"
            unreferenced += 1
        else:
            references = [
                check(case, citation) for citation in dict.fromkeys(case.expected_sources)
            ]
            missing_date = case.category == "historické znenia" and case.as_of is None
            errors = ["missing_decisive_date"] if missing_date else []
            verified = not errors and not any(ref["problems"] for ref in references)
            status = "references_verified" if verified else "references_failed"
            grounded += int(verified)
            failed += int(not verified)
        rows.append(
            {
                "id": case.id,
                "as_of": case.as_of.isoformat() if case.as_of else None,
                "status": status,
                "problems": errors,
                "references": references,
            }
        )
    return {
        "kind": "source_audit",
        "ready": grounded > 0 and failed == 0,
        "cases_with_verified_references": grounded,
        "failed_referenced_cases": failed,
        "fictional_cases": excluded,
        "cases_without_expected_references": unreferenced,
        "cases": rows,
    }
