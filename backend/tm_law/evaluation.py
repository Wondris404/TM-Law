"""Dataset validation, deterministic identifier checks and human review scoring."""

import json
import unicodedata
from collections import Counter
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, ValidationError, model_validator

from .schemas import Key, StrictModel

SOURCE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}/[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$"
SourceId = Annotated[str, StringConstraints(pattern=SOURCE_ID)]
EvidenceStatus = Literal["available", "insufficient", "version_conflict"]
Grade = Literal["yes", "partial", "no"]


class BenchmarkCase(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=3, max_length=4000)
    query: str | None = Field(default=None, min_length=1, max_length=400)
    as_of: date | None = None
    expected_sources: list[SourceId]
    forbidden_sources: list[SourceId] = Field(default_factory=list)
    expected_evidence: EvidenceStatus | None = None
    reference_answer: str | None = None
    criteria: list[str] = Field(default_factory=list)
    expert_verified: bool = False
    fictional: bool = False
    scenario_type: Literal["real", "synthetic", "adapted"] | None = None
    difficulty: Literal["basic", "intermediate", "advanced"] | None = None
    provenance: str | None = Field(default=None, max_length=500)
    source_groups: list[Key] = Field(default_factory=list)
    required_characteristics: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_sources(self):
        if set(self.expected_sources).intersection(self.forbidden_sources):
            raise ValueError("A source cannot be expected and forbidden simultaneously.")
        if self.expected_evidence == "insufficient" and self.expected_sources:
            raise ValueError("Insufficient evidence cannot require an available source.")
        return self


def benchmark_cases(data: bytes) -> list[BenchmarkCase]:
    result = []
    ids = set()
    for index, line in enumerate(data.decode("utf-8-sig").split("\n"), start=1):
        if not line.strip():
            continue
        try:
            task = BenchmarkCase.model_validate_json(line)
        except ValidationError as exc:
            paths = ", ".join(
                ".".join(map(str, issue["loc"])) or "JSON"
                for issue in exc.errors(include_input=False)
            )
            raise ValueError(f"Neplatná úloha na riadku {index} ({paths}).") from exc
        if task.id in ids:
            raise ValueError(f"Duplicitné ID úlohy na riadku {index}.")
        ids.add(task.id)
        result.append(task)
    return result


def question_key(text: str) -> str:
    normal = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in normal).split())


def deterministic_checks(case: BenchmarkCase, result: dict) -> dict:
    expected = set(case.expected_sources)
    retrieved = set(result["retrieved_ids"])
    context = set(result["context_ids"])
    verified = set(result["verified_ids"])
    cited = set(result["cited_ids"])
    historical = case.category == "historické znenia" and case.as_of is not None
    return {
        "retrieval_covers_expected": expected <= retrieved if expected else None,
        "context_covers_expected": expected <= context if expected else None,
        "expected_ids_verified": expected <= verified if expected else None,
        "forbidden_ids_absent": not cited.intersection(case.forbidden_sources)
        if case.forbidden_sources
        else None,
        "historical_ids_match": expected == verified and not result["rejected"]
        if historical
        else None,
        "evidence_status_matches": result["evidence_status"] == case.expected_evidence
        if case.expected_evidence
        else None,
        "no_rejected_identifiers": not result["rejected"],
        "no_citations_when_evidence_missing": not cited
        if case.expected_evidence == "insufficient"
        else None,
    }


class ReviewJudgment(StrictModel):
    review_id: Key
    legal_correctness: Grade | None = None
    citation_support: Grade | None = None
    completeness: Grade | None = None
    unsupported_claims: bool | None = None
    unnecessary_refusal: bool | None = None


def review_statistics(reviews: list[ReviewJudgment]) -> dict:
    fields = (
        "legal_correctness",
        "citation_support",
        "completeness",
        "unsupported_claims",
        "unnecessary_refusal",
    )
    result = {}
    for field in fields:
        counted = Counter(getattr(review, field) for review in reviews)
        unassessed = counted.pop(None, 0)
        result[field] = {
            "assessed": len(reviews) - unassessed,
            "unassessed": unassessed,
            "counts": {
                (str(value).lower() if isinstance(value, bool) else value): count
                for value, count in counted.items()
            },
        }
    return result


def read_review_judgments(raw: bytes) -> list[ReviewJudgment]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Review judgments must be a JSON array.")
    return [ReviewJudgment.model_validate(row) for row in data]
