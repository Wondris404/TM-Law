import argparse
import json
import os
import tempfile
from pathlib import Path

from backend.tm_law.rag import answer
from backend.tm_law.runtime import MockRuntime, Ollama
from backend.tm_law.schemas import ChatInput, LegalVersion, RuntimeOptions
from backend.tm_law.store import Store

ROOT = Path(__file__).resolve().parents[1]


def cases(path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


async def run_case(store, runtime, task, model):
    request = ChatInput(
        question=task["question"],
        query=task.get("query"),
        as_of=task.get("as_of"),
        options=RuntimeOptions(model=model),
    )
    result = None
    async for event in answer(store, runtime, request, None):
        if event["type"] in {"done", "error"}:
            result = event
    if result is None or result["type"] == "error":
        return {"id": task["id"], "status": "error", "error": (result or {}).get("message")}
    expected = set(task["expected_sources"])
    cited = {source["citation_id"] for source in result["citations"]}
    retrieved = set(result["retrieved_ids"])
    invalid = len(result["rejected"])
    return {
        "id": task["id"],
        "category": task["category"],
        "expert_verified": task["expert_verified"],
        "status": "done",
        "answer": result["answer"],
        "cited_ids": sorted(cited),
        "retrieved_ids": sorted(retrieved),
        "citation_identifier_validity": len(cited) / (len(cited) + invalid)
        if cited or invalid
        else None,
        "unverified_identifier_rate": invalid / (len(cited) + invalid)
        if cited or invalid
        else None,
        "expected_sources_cited": len(expected & cited) / len(expected) if expected else None,
        "retrieval_recall": len(expected & retrieved) / len(expected) if expected else None,
        "historical_fixture_match": expected == cited
        if task["category"] == "historické znenia"
        else None,
        "unsupported_citation_on_empty_expectation": bool(cited or invalid)
        if not expected
        else None,
        "unnecessary_refusal_rate": None,
        **result["metrics"],
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Compare local TM-Law runtimes on a JSONL dataset."
    )
    parser.add_argument("--cases", type=Path, default=ROOT / "benchmarks" / "smoke.jsonl")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument(
        "--model", action="append", help="Installed Ollama model; repeat to compare."
    )
    args = parser.parse_args()
    all_tasks = list(cases(args.cases))
    models = args.model or ["tm-law-mock"]
    with tempfile.TemporaryDirectory(prefix="tm-law-benchmark-") as temp:
        store = Store(args.data_dir or Path(temp))
        store.initialize()
        if not args.model and args.data_dir is None:
            for file in sorted((ROOT / "data").glob("demo-*.json")):
                store.import_version(LegalVersion.model_validate_json(file.read_bytes()))
        runs = []
        for model in models:
            runtime = (
                Ollama(os.getenv("TM_LAW_OLLAMA_URL", "http://127.0.0.1:11434"), model)
                if args.model
                else MockRuntime()
            )
            selected = [
                task for task in all_tasks if runtime.simulated or not task.get("fictional")
            ]
            if not selected:
                parser.error(
                    "Ollama evaluation needs non-fictional tasks and a verified local corpus."
                )
            rows = [await run_case(store, runtime, task, model) for task in selected]
            runs.append(
                {
                    "model": model,
                    "simulated": runtime.simulated,
                    "cases": rows,
                    "completed": sum(row["status"] == "done" for row in rows),
                    "total": len(rows),
                }
            )
        print(json.dumps(runs, ensure_ascii=False, indent=2))
        return int(any(run["completed"] != run["total"] for run in runs))


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
