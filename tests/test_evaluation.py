import hashlib
import json
from pathlib import Path

import pytest
from tm_law.evaluation import BenchmarkCase, ReviewJudgment, benchmark_cases, deterministic_checks

from scripts.legal_review import aggregate, prepare_sheet

ROOT = Path(__file__).resolve().parents[1]


def test_starter_dataset_and_historical_citation_trap():
    cases = benchmark_cases((ROOT / "benchmarks/slovak-starter.jsonl").read_bytes())
    assert len(cases) == 13 and not any(case.expert_verified for case in cases)
    past = next(case for case in cases if case.id == "historic-2022")
    assert past.as_of.year == 2022
    wrong = {
        "retrieved_ids": ["demo-2022/p7-1"],
        "context_ids": [],
        "verified_ids": [],
        "cited_ids": ["demo-2024/p7-1"],
        "rejected": ["demo-2024/p7-1"],
        "evidence_status": "available",
        "unsupported_mentions": ["40/1964"],
    }
    checks = deterministic_checks(past, wrong)
    assert checks["retrieval_covers_expected"]
    assert not checks["context_covers_expected"]
    assert not checks["expected_ids_verified"]
    assert not checks["forbidden_ids_absent"]
    assert not checks["historical_ids_match"]
    assert checks["no_unmarked_legal_mentions"] is False
    clean = deterministic_checks(past, wrong | {"unsupported_mentions": []})
    assert clean["no_unmarked_legal_mentions"] is True


def test_family_law_benchmark_separates_scenarios_and_source_provenance():
    cases = benchmark_cases((ROOT / "benchmarks/slovak-family-law.jsonl").read_bytes())
    assert len(cases) == 9
    assert {case.difficulty for case in cases} == {"basic", "intermediate", "advanced"}
    assert sum(bool(case.expected_sources) for case in cases) == 8
    assert all(case.scenario_type == "synthetic" and not case.fictional for case in cases)
    assert all(not case.expert_verified for case in cases)
    assert all(case.source_groups == ["sk-zz-2005-36"] and case.as_of for case in cases)
    before = next(case for case in cases if case.id == "rodina-otcovstvo-posledny-den")
    after = next(case for case in cases if case.id == "rodina-otcovstvo-prvy-den")
    assert before.expected_sources == after.forbidden_sources
    assert after.expected_sources == before.forbidden_sources


def test_blind_sheet_and_assessed_denominators():
    item = BenchmarkCase(
        id="case", category="example", question="Over príklad", expected_sources=[]
    )
    raw = item.model_dump_json().encode()
    run = {
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "simulated": False,
        "model": "example:1b",
        "settings": {"reasoning": "off"},
        "cases": [
            {"id": "case", "status": "done", "repeat": 1, "answer": "Ukážka"},
            {"id": "case", "status": "done", "repeat": 2, "answer": "Ďalšia ukážka"},
        ],
    }
    sheet, key = prepare_sheet(raw, [run], 42)
    assert "example:1b" not in json.dumps(sheet)
    review = ReviewJudgment(review_id=sheet["rows"][0]["review_id"], citation_support="partial")
    output = aggregate(key, [review])
    assert output["submitted_reviews"] == 1 and output["unsubmitted_reviews"] == 1
    stats = output["groups"][0]["judgments"]
    assert stats["citation_support"] == {"assessed": 1, "unassessed": 0, "counts": {"partial": 1}}
    assert stats["legal_correctness"]["assessed"] == 0
    with pytest.raises(ValueError, match="duplicate"):
        aggregate(key, [review, review])
    with pytest.raises(ValueError, match="No completed real"):
        prepare_sheet(raw, [run | {"simulated": True}], 42)
