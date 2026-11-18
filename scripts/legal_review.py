import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from random import Random
from uuid import uuid4

from pydantic import ValidationError

from backend.tm_law.evaluation import benchmark_cases, read_review_judgments, review_statistics


def prepare_sheet(case_bytes: bytes, runs: list[dict], seed: int) -> tuple[dict, dict]:
    digest = hashlib.sha256(case_bytes).hexdigest()
    cases = {case.id: case for case in benchmark_cases(case_bytes)}
    rows = []
    key = {}
    for run in runs:
        if run["dataset_sha256"] != digest:
            raise ValueError("Dataset fingerprint differs from the benchmark report.")
        if run["simulated"]:
            continue
        for row in run["cases"]:
            if row["status"] != "done":
                continue
            if "answer" not in row:
                raise ValueError("Review requires a rerun with --include-answers on approved data.")
            task = cases[row["id"]]
            review_id = uuid4().hex
            rows.append(
                {
                    "review_id": review_id,
                    "case": task.model_dump(mode="json"),
                    "answer": row["answer"],
                    "citations": row.get("sources_for_review", []),
                    "judgment": {
                        "legal_correctness": None,
                        "citation_support": None,
                        "completeness": None,
                        "unsupported_claims": None,
                        "unnecessary_refusal": None,
                    },
                }
            )
            key[review_id] = {
                "model": run["model"],
                "settings": run["settings"],
                "case_id": row["id"],
                "repeat": row["repeat"],
                "model_digest": row.get("model_digest"),
            }
    if not rows:
        raise ValueError("No completed real-model responses available for review.")
    Random(seed).shuffle(rows)
    return (
        {"dataset_sha256": digest, "shuffling_seed": seed, "rows": rows},
        {"dataset_sha256": digest, "mapping": key},
    )


def aggregate(key, reviews):
    buckets = defaultdict(list)
    seen = set()
    for row in reviews:
        if row.review_id not in key["mapping"] or row.review_id in seen:
            raise ValueError("Unknown or duplicate review ID.")
        seen.add(row.review_id)
        origin = key["mapping"][row.review_id]
        label = (
            origin["model"],
            origin["model_digest"],
            json.dumps(origin["settings"], sort_keys=True),
        )
        buckets[label].append(row)
    return {
        "dataset_sha256": key["dataset_sha256"],
        "submitted_reviews": len(seen),
        "unsubmitted_reviews": len(key["mapping"]) - len(seen),
        "groups": [
            {
                "model": model,
                "model_digest": digest,
                "settings": json.loads(settings),
                "judgments": review_statistics(group),
            }
            for (model, digest, settings), group in buckets.items()
        ],
    }


def save_new(path: Path, data) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare blinded review sheets or summarize submitted judgments."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    for argument in ("cases", "report", "sheet", "key"):
        prepare.add_argument(f"--{argument}", type=Path, required=True)
    prepare.add_argument("--seed", type=int, default=42)
    score = commands.add_parser("aggregate")
    for argument in ("key", "judgments", "output"):
        score.add_argument(f"--{argument}", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            if (
                args.sheet.resolve() == args.key.resolve()
                or args.sheet.exists()
                or args.key.exists()
            ):
                raise ValueError("Sheet and key must be two distinct new files.")
            sheet, key = prepare_sheet(
                args.cases.read_bytes(), json.loads(args.report.read_bytes()), args.seed
            )
            save_new(args.sheet, sheet)
            save_new(args.key, key)
            print(f"Review rows: {len(sheet['rows'])}")
        else:
            result = aggregate(
                json.loads(args.key.read_bytes()),
                read_review_judgments(args.judgments.read_bytes()),
            )
            save_new(args.output, result)
            print(f"Submitted reviews: {result['submitted_reviews']}")
    except ValidationError:
        parser.error("Review JSON failed validation.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
