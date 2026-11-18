import json
from pathlib import Path

import pytest

from training.config import TrainingConfig
from training.dataset import prepare, prepared_splits, read_examples

ROOT = Path(__file__).resolve().parents[1]


def test_training_filters_holdout_and_deduplicates_groups(tmp_path):
    raw = (ROOT / "data/training-smoke.jsonl").read_bytes()
    holdout = (ROOT / "benchmarks/slovak-starter.jsonl").read_bytes()
    examples = read_examples(raw)
    first = examples[0].model_dump()
    duplicate = first | {"id": "zzz-duplicate"}
    leaked = first | {"id": "heldout", "source_groups": ["demo-dielna"]}
    payload = raw + ("\n".join(json.dumps(row) for row in (duplicate, leaked)) + "\n").encode()
    output = tmp_path / "prepared"
    summary = prepare(payload, [holdout], output, 42)
    assert summary["excluded_holdout_rows"] == summary["deduplicated_rows"] == 1
    assert [summary["splits"][name]["examples"] for name in ("train", "validation", "test")] == [
        8,
        1,
        1,
    ]
    assert prepare(payload, [holdout], tmp_path / "rerun", 42) == summary
    assert prepared_splits(output)[0] == summary
    test_data = output / "test.jsonl"
    test_data.write_bytes(test_data.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="integrity"):
        prepared_splits(output)


def test_training_rejects_personal_data_and_cpu_qlora(tmp_path):
    raw = (ROOT / "data/training-smoke.jsonl").read_bytes()
    record = read_examples(raw)[0].model_dump() | {"contains_personal_data": True}
    with pytest.raises(ValueError, match="contains_personal_data"):
        read_examples(json.dumps(record).encode())
    with pytest.raises(ValueError, match="requires CUDA"):
        TrainingConfig.model_validate(
            {
                "model_name": "test",
                "base_directory": tmp_path,
                "base_model_id": "test",
                "base_revision": "a" * 40,
                "base_license": "MIT",
                "data_directory": tmp_path,
                "output_directory": tmp_path / "out",
                "target_modules": ["q_proj"],
                "method": "qlora",
                "device": "cpu",
            }
        )
