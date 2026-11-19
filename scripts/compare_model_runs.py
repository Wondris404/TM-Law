"""Compare aligned experiments for base, adapted, quantized or compressed models."""

import argparse
import json
from pathlib import Path
from statistics import median

METRICS = (
    "seconds",
    "first_token_seconds",
    "tokens_per_second",
    "ollama_load_seconds",
    "retrieval_recall",
    "context_recall",
    "expected_sources_cited",
)


def indexed(rows):
    keyed = {(row["id"], row["repeat"]): row for row in rows}
    if len(keyed) != len(rows):
        raise ValueError("Duplicate rows in benchmark comparison.")
    return keyed


def compare(baseline: dict, candidate: dict) -> dict:
    fields = ("dataset_sha256", "corpus_sha256", "platform", "simulated")
    default_settings = {"cpu_threads": None, "ollama_use_mmap": None}
    baseline_settings = default_settings | baseline["settings"]
    candidate_settings = default_settings | candidate["settings"]
    if baseline_settings != candidate_settings or any(
        baseline[key] != candidate[key] for key in fields
    ):
        raise ValueError(
            "Benchmark runs must share corpus, tasks, execution settings and platform."
        )
    left, right = indexed(baseline["cases"]), indexed(candidate["cases"])
    if left.keys() != right.keys():
        raise ValueError("Benchmark runs have different case or repeat IDs.")
    pairs = [
        (left[key], right[key])
        for key in left
        if left[key]["status"] == right[key]["status"] == "done"
    ]
    stats = []
    for key in METRICS:
        deltas = [
            b[key] - a[key] for a, b in pairs if a.get(key) is not None and b.get(key) is not None
        ]
        stats.append(
            {
                "metric": key,
                "matched_observations": len(deltas),
                "median_candidate_minus_baseline": median(deltas) if deltas else None,
            }
        )

    def variant(report):
        sizes = {
            row["model_metadata"]["disk_size_bytes"]
            for row in report["cases"]
            if row.get("model_metadata")
            and row["model_metadata"].get("disk_size_bytes") is not None
        }
        return {
            "model": report["model"],
            "completed": report["completed"],
            "runtime_failures": report["runtime_failures"],
            "digests": sorted(
                {row["model_digest"] for row in report["cases"] if row.get("model_digest")}
            ),
            "disk_size_bytes": next(iter(sizes)) if len(sizes) == 1 else None,
            "combined_peak_pss_bytes": report["summary"]["combined_peak_pss_bytes"],
        }

    return {
        "baseline": variant(baseline),
        "candidate": variant(candidate),
        "simulated": baseline["simulated"],
        "digest": {key: baseline[key] for key in ("dataset_sha256", "corpus_sha256")},
        "matched_completed_responses": len(pairs),
        "metrics": stats,
        "legal_review": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--baseline-run", type=int, default=0)
    parser.add_argument("--candidate-run", type=int, default=0)
    args = parser.parse_args()
    try:
        left = json.loads(args.baseline.read_bytes())[args.baseline_run]
        right = json.loads(args.candidate.read_bytes())[args.candidate_run]
        comparison = compare(left, right)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, KeyError, OSError, IndexError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
