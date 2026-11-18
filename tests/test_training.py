import hashlib
import json
from pathlib import Path

import pytest

from scripts.train_lora import base_weights, preflight
from training.config import TrainingConfig
from training.dataset import TeacherProvenance, prepare, prepared_splits, read_examples

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


def test_training_excludes_other_versions_of_benchmark_law(tmp_path):
    raw = (ROOT / "data/training-smoke.jsonl").read_bytes()
    example = read_examples(raw)[0].model_dump() | {
        "id": "other-version",
        "prompt": "Odlišná tréningová otázka",
        "source_ids": ["sk-zz-2005-36-20240101/paragraf-1"],
    }
    benchmark = (ROOT / "benchmarks/slovak-family-law.jsonl").read_bytes()
    summary = prepare(
        raw + json.dumps(example).encode() + b"\n", [benchmark], tmp_path / "data", 42
    )
    assert summary["excluded_holdout_rows"] == 1


def test_preflight_checks_model_files_without_loading_weights(tmp_path):
    base, data, output = (tmp_path / name for name in ("base", "data", "out"))
    base.mkdir()
    for name in ("config.json", "tokenizer_config.json", "tokenizer.json"):
        (base / name).write_text("{}", encoding="utf-8")
    index = base / "model.safetensors.index.json"
    index.write_text(
        json.dumps({"weight_map": {"weight": "../fake.safetensors"}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="local shard files"):
        base_weights(base)
    shard = "model-00001-of-00001.safetensors"
    index.write_text(json.dumps({"weight_map": {"weight": shard}}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing local"):
        base_weights(base)
    (base / shard).write_bytes(b"placeholder")
    raw = (ROOT / "data/training-smoke.jsonl").read_bytes()
    holdout = (ROOT / "benchmarks/slovak-starter.jsonl").read_bytes()
    prepare(raw, [holdout], data, 42)
    config = TrainingConfig(
        model_name="test",
        base_directory=base,
        base_model_id="synthetic preflight fixture",
        base_revision="synthetic-smoke-v1",
        base_license="MIT",
        data_directory=data,
        output_directory=output,
        target_modules=["c_attn"],
        device="cpu",
        smoke_only=True,
    )
    result = preflight(config)
    assert result["weight_file_sizes_bytes"] == {shard: 11}
    assert result["splits"] == {"train": 8, "validation": 1, "test": 1}
    assert not output.exists()


def test_distillation_checks_response_digest_and_records_teacher(tmp_path):
    raw = (ROOT / "data/training-smoke.jsonl").read_bytes()
    holdout = (ROOT / "benchmarks/slovak-starter.jsonl").read_bytes()
    teacher = TeacherProvenance(
        model="synthetic teacher fixture",
        revision="smoke-only",
        model_sha256="a" * 64,
        responses_sha256=hashlib.sha256(raw).hexdigest(),
        reuse_terms="MIT",
        approved_for_training=True,
    )
    output = tmp_path / "prepared"
    with pytest.raises(ValueError, match="declared SHA-256"):
        prepare(raw + b"\n", [holdout], output, 42, teacher=teacher)
    assert not output.exists()
    result = prepare(raw, [holdout], output, 42, teacher=teacher)
    assert result["teacher"] == teacher.model_dump()
    assert prepared_splits(output)[0] == result
