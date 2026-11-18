"""Prepare isolated, explicitly reusable text data for optional supervised training."""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, ValidationError

from backend.tm_law.evaluation import SourceId, benchmark_cases, question_key
from backend.tm_law.schemas import Key, Short, StrictModel

SPLITS = ("train", "validation", "test")
SLOVLEX_VERSION = re.compile(r"(sk-zz-[0-9]{4}-[0-9]+)-[0-9]{8}")
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=8000)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class TeacherProvenance(StrictModel):
    model: Short
    revision: Short
    model_sha256: Sha256
    responses_sha256: Sha256
    reuse_terms: Short
    approved_for_training: Literal[True]


class TrainingExample(StrictModel):
    id: Key
    group: Key
    task: Short
    prompt: Text
    answer: Text
    provenance: Short
    license: Literal["CC0-1.0", "CC-BY-4.0", "MIT", "public-domain"]
    contains_personal_data: Literal[False]
    reusable_for_training: Literal[True]
    origin: Literal["synthetic", "licensed_public"]
    source_groups: list[Key] = Field(default_factory=list)
    source_ids: list[SourceId] = Field(default_factory=list)


def read_examples(raw: bytes) -> list[TrainingExample]:
    rows = []
    ids = set()
    for index, line in enumerate(raw.decode("utf-8-sig").split("\n"), start=1):
        if not line.strip():
            continue
        try:
            item = TrainingExample.model_validate_json(line)
        except ValidationError as exc:
            fields = ", ".join(".".join(map(str, e["loc"])) or "JSON" for e in exc.errors())
            raise ValueError(f"Invalid training example on line {index} ({fields}).") from exc
        if item.id in ids or not question_key(item.prompt):
            raise ValueError(f"Duplicate ID or empty normalized prompt on line {index}.")
        ids.add(item.id)
        rows.append(item)
    return rows


def reference_keys(source_ids: list[str]) -> set[str]:
    versions = {source.split("/", 1)[0] for source in source_ids}
    families = {match[1] for version in versions if (match := SLOVLEX_VERSION.fullmatch(version))}
    return versions | families


def source_keys(item: TrainingExample) -> set[str]:
    return set(item.source_groups) | reference_keys(item.source_ids)


def holdout_keys(holdouts: list[bytes]) -> tuple[set[str], set[str]]:
    if not holdouts:
        raise ValueError("Explicit benchmark holdout data is required.")
    questions, sources = set(), set()
    for dataset in holdouts:
        cases = benchmark_cases(dataset)
        if not cases:
            raise ValueError("Benchmark holdout must contain at least one case.")
        for case in cases:
            questions.add(question_key(case.question))
            sources.update(case.source_groups)
            sources.update(reference_keys(case.expected_sources + case.forbidden_sources))
    return questions, sources


def overlaps_holdout(item: TrainingExample, questions: set[str], sources: set[str]) -> bool:
    return (
        question_key(item.prompt) in questions
        or item.group in sources
        or bool(source_keys(item).intersection(sources))
    )


def write_split(rows: list[TrainingExample]) -> bytes:
    return "".join(row.model_dump_json() + "\n" for row in rows).encode("utf-8")


def prepare(
    raw: bytes,
    holdouts: list[bytes],
    output: Path,
    seed: int,
    *,
    teacher: TeacherProvenance | None = None,
) -> dict:
    input_digest = hashlib.sha256(raw).hexdigest()
    if teacher is not None and teacher.responses_sha256 != input_digest:
        raise ValueError("Teacher response file does not match its declared SHA-256.")
    held_questions, held_sources = holdout_keys(holdouts)
    examples = read_examples(raw)
    groups = {}
    sources_by_group = {}
    prompts = {}
    contamination = duplicates = 0
    for item in sorted(examples, key=lambda example: example.id):
        key = question_key(item.prompt)
        sources = source_keys(item)
        if overlaps_holdout(item, held_questions, held_sources):
            contamination += 1
            continue
        if key in prompts:
            previous = prompts[key]
            if (
                question_key(previous.answer) != question_key(item.answer)
                or item.group != previous.group
                or sources != source_keys(previous)
            ):
                raise ValueError(
                    "Duplicate normalized prompt with conflicting answer or provenance."
                )
            duplicates += 1
            continue
        for source in sources:
            assigned = sources_by_group.setdefault(source, item.group)
            if assigned != item.group:
                raise ValueError("A source family appears in multiple training groups. Unify them.")
        prompts[key] = item
        groups.setdefault(item.group, []).append(item)
    ranked = sorted(groups, key=lambda group: hashlib.sha256(f"{seed}:{group}".encode()).digest())
    if len(ranked) < 3:
        raise ValueError("Three independent groups are required after holdout filtering.")
    reserved = max(1, int(len(ranked) * 0.1))
    chosen = {
        "test": ranked[:reserved],
        "validation": ranked[reserved : 2 * reserved],
        "train": ranked[2 * reserved :],
    }
    payloads = {
        label: write_split([item for group in chosen[label] for item in groups[group]])
        for label in SPLITS
    }
    manifest = {
        "schema": 1,
        "seed": seed,
        "input_sha256": input_digest,
        "holdout_sha256": [hashlib.sha256(item).hexdigest() for item in holdouts],
        "excluded_holdout_rows": contamination,
        "deduplicated_rows": duplicates,
        "splits": {
            label: {
                "examples": sum(len(groups[g]) for g in chosen[label]),
                "groups": chosen[label],
                "sha256": hashlib.sha256(payloads[label]).hexdigest(),
            }
            for label in SPLITS
        },
    }
    if teacher is not None:
        manifest["teacher"] = teacher.model_dump(mode="json")
    output.mkdir(parents=True, exist_ok=False)
    for label, payload in payloads.items():
        (output / f"{label}.jsonl").write_bytes(payload)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def prepared_splits(directory: Path) -> tuple[dict, dict[str, list[TrainingExample]]]:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if manifest["schema"] != 1 or not manifest["holdout_sha256"]:
        raise ValueError("Unrecognized dataset manifest or missing holdout.")
    if "teacher" in manifest:
        teacher = TeacherProvenance.model_validate(manifest["teacher"])
        if teacher.responses_sha256 != manifest["input_sha256"]:
            raise ValueError("Teacher response digest does not match the prepared input.")
    splits = {}
    seen = set()
    for label in SPLITS:
        raw = (directory / f"{label}.jsonl").read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["splits"][label]["sha256"]:
            raise ValueError(f"Prepared split {label} failed integrity verification.")
        splits[label] = rows = read_examples(raw)
        keys = {
            (kind, value)
            for row in rows
            for kind, value in (
                ("id", row.id),
                ("prompt", question_key(row.prompt)),
                *(("group", key) for key in {row.group, *source_keys(row)}),
            )
        }
        if not rows or keys.intersection(seen):
            raise ValueError("Dataset split is empty or groups/prompts overlap across splits.")
        seen.update(keys)
    return manifest, splits
