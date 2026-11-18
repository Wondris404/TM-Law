import argparse
import asyncio
import hashlib
import json
import os
import platform
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import date
from pathlib import Path
from statistics import median

from pydantic import Field, ValidationError

from backend.tm_law.rag import answer
from backend.tm_law.runtime import MockRuntime, Ollama
from backend.tm_law.schemas import ChatInput, LegalVersion, RuntimeOptions, StrictModel
from backend.tm_law.store import SCHEMA_VERSION, Store

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkCase(StrictModel):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    question: str = Field(min_length=3, max_length=4000)
    query: str | None = Field(default=None, min_length=1, max_length=400)
    as_of: date | None = None
    expected_sources: list[str]
    reference_answer: str | None = None
    criteria: list[str] = Field(default_factory=list)
    expert_verified: bool = False
    fictional: bool = False


def read_cases(data: bytes):
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


def snapshot_corpus(store: Store, source_dir: Path | None, simulated: bool) -> str:
    store.initialize()
    if source_dir is not None:
        source = (source_dir / "legal.sqlite3").resolve()
        with (
            closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as src,
            closing(store.connect(store.legal)) as dst,
        ):
            if src.execute("PRAGMA user_version").fetchone()[0] not in {1, SCHEMA_VERSION}:
                raise ValueError("Nepodporovaná schéma zdrojovej právnej databázy.")
            src.backup(dst)
        store.initialize()
    elif simulated:
        for file in sorted((ROOT / "data").glob("demo-*.json")):
            store.import_version(LegalVersion.model_validate_json(file.read_bytes()))

    with closing(store.connect(store.legal)) as conn:
        rows = [
            tuple(row)
            for row in conn.execute(
                "SELECT version_id, content_sha256 FROM legal_version ORDER BY version_id"
            )
        ]
    return hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest()


async def run_case(store, runtime, task, options, repeat, include_answers=False):
    request = ChatInput(question=task.question, query=task.query, as_of=task.as_of, options=options)
    result = None
    async for event in answer(store, runtime, request, None):
        if event["type"] in {"done", "error"}:
            result = event

    base = {
        "id": task.id,
        "category": task.category,
        "repeat": repeat,
        "expert_verified": task.expert_verified,
        "expert_review": {"legal_correctness": None, "completeness": None, "review_notes": None},
    }
    if result is None or result["type"] == "error":
        error = result or {}
        return {
            **base,
            "status": "error",
            "error": error.get("message"),
            "error_code": error.get("code"),
            "response_completeness": error.get("code", "incomplete"),
            **error.get("metrics", {}),
        }

    expected = set(task.expected_sources)
    verified = set(result["verified_ids"])
    retrieved = set(result["retrieved_ids"])
    rejected = result["rejected"]
    citations = len(verified) + len(rejected)
    done_reason = result["metrics"]["done_reason"]
    completeness = {"stop": "stopped", "length": "length_limit"}.get(done_reason, "unknown")
    if runtime.simulated:
        completeness = "simulated"
    return {
        **base,
        "status": "done",
        "response_completeness": completeness,
        **({"answer": result["answer"]} if include_answers else {}),
        "cited_ids": result["cited_ids"],
        "verified_ids": result["verified_ids"],
        "retrieved_ids": result["retrieved_ids"],
        "context_ids": result["context_ids"],
        "rejected_ids": rejected,
        "missing_citations": bool(expected - verified),
        "missing_expected_ids": sorted(expected - verified),
        "citation_identifier_validity": len(verified) / citations if citations else None,
        "unverified_identifier_rate": len(rejected) / citations if citations else None,
        "expected_sources_cited": len(expected & verified) / len(expected) if expected else None,
        "retrieval_recall": len(expected & retrieved) / len(expected) if expected else None,
        "historical_fixture_match": expected == verified and not rejected
        if task.category == "historické znenia"
        else None,
        "unsupported_citation_on_empty_expectation": bool(citations) if not expected else None,
        "evidence_status": result["evidence_status"],
        "reasoning": result["reasoning"],
        "model_digest": result["model_digest"],
        "model_metadata": result["model_metadata"],
        **result["metrics"],
    }


def describe(rows):
    def statistic(key, operation):
        values = [row[key] for row in rows if row.get(key) is not None]
        return operation(values) if values else None

    memory = [row["memory"] for row in rows if row.get("memory")]
    processes = [process for sample in memory for process in sample["processes"]]
    return {
        "median_seconds": statistic("seconds", median),
        "median_load_seconds": statistic("ollama_load_seconds", median),
        "median_first_token_seconds": statistic("first_token_seconds", median),
        "median_tokens_per_second": statistic("tokens_per_second", median),
        "peak_backend_rss_bytes": max(
            (p["peak_rss_bytes"] for p in processes if p["role"] == "backend"), default=None
        ),
        "peak_individual_ollama_rss_bytes": max(
            (p["peak_rss_bytes"] for p in processes if p["role"] != "backend"), default=None
        ),
        "combined_peak_pss_bytes": max(
            (
                s["combined_peak_pss_bytes"]
                for s in memory
                if s["combined_peak_pss_bytes"] is not None
            ),
            default=None,
        ),
        "missing_citation_responses": sum(row.get("missing_citations", False) for row in rows),
        "rejected_identifiers": sum(len(row.get("rejected_ids", [])) for row in rows),
        "length_limited_responses": sum(
            row["response_completeness"] == "length_limit" for row in rows
        ),
    }


def human_summary(runs):
    def value(item, unit):
        return f"{item:.2f} {unit}" if item is not None else "nedostupné"

    print(
        "Model | Uvažovanie | Kontext | Dokončené | Latencia | Tok/s | Spoločná PSS",
        file=sys.stderr,
    )
    for run in runs:
        settings = run["settings"]
        stats = run["summary"]
        label = f"{run['model']} (simulácia)" if run["simulated"] else run["model"]
        pss = stats["combined_peak_pss_bytes"]
        print(
            f"{label} | {settings['reasoning']} | {settings['context_window']} | "
            f"{run['completed']}/{run['total']} | {value(stats['median_seconds'], 's')} | "
            f"{value(stats['median_tokens_per_second'], 'tok/s')} | "
            f"{value(pss / 1048576 if pss is not None else None, 'MiB')}",
            file=sys.stderr,
        )


async def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare local TM-Law runtimes on UTF-8 JSONL.")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--model", action="append", help="Installed Ollama tag; repeat to compare.")
    parser.add_argument("--context-window", type=int, action="append", help="Repeat to compare.")
    parser.add_argument("--reasoning", choices=("auto", "on", "off"), action="append")
    parser.add_argument("--device", choices=("auto", "cpu"), default="auto")
    parser.add_argument("--temperature", type=float, default=0.15)
    parser.add_argument("--max-tokens", type=int, default=768)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--measure-memory", action="store_true")
    parser.add_argument("--summary", action="store_true", help="Write a readable table to stderr.")
    parser.add_argument("--output", type=Path, help="Write JSON directly as UTF-8.")
    parser.add_argument("--include-answers", action="store_true", help="Include model answer text.")
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 20:
        parser.error("--repeats must be between 1 and 20.")
    simulated = not args.model
    models = dict.fromkeys(args.model or ["tm-law-mock"])
    contexts = dict.fromkeys(args.context_window or [4096])
    modes = dict.fromkeys(args.reasoning or ["auto"])
    if simulated and set(modes) != {"auto"}:
        parser.error("Non-default reasoning modes need --model.")

    work = []
    try:
        for model in models:
            for context in contexts:
                for mode in modes:
                    options = RuntimeOptions(
                        model=model,
                        context_window=context,
                        reasoning=mode,
                        temperature=args.temperature,
                        max_tokens=args.max_tokens,
                        measure_memory=args.measure_memory,
                        device=args.device,
                        seed=args.seed,
                    )
                    if options.max_tokens > options.context_window // 2:
                        parser.error("--max-tokens must not exceed half of each --context-window.")
                    work.append(options)
        path = args.cases or ROOT / "benchmarks" / ("smoke.jsonl" if simulated else "runtime.jsonl")
        case_bytes = path.read_bytes()
        selected = [task for task in read_cases(case_bytes) if simulated or not task.fictional]
    except (OSError, ValueError) as exc:
        parser.error(
            str(exc) if not isinstance(exc, ValidationError) else "Invalid model or settings."
        )
    if not selected:
        parser.error("No eligible tasks. Ollama needs non-fictional tasks.")
    if not simulated and args.data_dir is None and any(task.expected_sources for task in selected):
        parser.error("Tasks with expected source IDs need --data-dir.")

    runs = []
    with tempfile.TemporaryDirectory(prefix="tm-law-benchmark-") as temp:
        store = Store(Path(temp))
        try:
            corpus_hash = snapshot_corpus(store, args.data_dir, simulated)
        except (sqlite3.Error, OSError, ValueError) as exc:
            parser.error(f"Could not read the legal corpus. {exc}")
        for options in work:
            runtime = (
                MockRuntime()
                if simulated
                else Ollama(
                    os.getenv("TM_LAW_OLLAMA_URL", "http://127.0.0.1:11434"),
                    options.model,
                    keep_alive=0,
                )
            )
            rows = []
            for repetition in range(1, args.repeats + 1):
                for task in selected:
                    row = await run_case(
                        store, runtime, task, options, repetition, args.include_answers
                    )
                    rows.append(row)
            completed = sum(row["status"] == "done" for row in rows)
            runs.append(
                {
                    "schema_version": 2,
                    "model": options.model,
                    "simulated": simulated,
                    "settings": options.model_dump(exclude={"model"})
                    | {
                        "repeats": args.repeats,
                        "ollama_keep_alive": 0 if not simulated else None,
                    },
                    "dataset_sha256": hashlib.sha256(case_bytes).hexdigest(),
                    "corpus_sha256": corpus_hash,
                    "platform": {"os": platform.system(), "architecture": platform.machine()},
                    "cases": rows,
                    "completed": completed,
                    "total": len(rows),
                    "runtime_failures": sum(
                        row.get("error_code") == "runtime_error" for row in rows
                    ),
                    "summary": describe(rows),
                }
            )
    report = json.dumps(runs, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        try:
            args.output.write_text(report, encoding="utf-8")
        except OSError as exc:
            parser.error(f"Could not write UTF-8 report. {exc}")
    else:
        sys.stdout.write(report)
    if args.summary:
        human_summary(runs)
    return int(any(run["completed"] != run["total"] for run in runs))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(asyncio.run(main()))
