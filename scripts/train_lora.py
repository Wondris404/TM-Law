"""Train local LoRA/QLoRA adapters. No model weights are downloaded by this script."""

import argparse
import hashlib
import json
import os
import re
from importlib.metadata import version
from pathlib import Path

from pydantic import ValidationError

from training.config import TrainingConfig
from training.dataset import holdout_keys, overlaps_holdout, prepared_splits

ROOT = Path(__file__).resolve().parents[1]
PROJECT_HOLDOUTS = ("slovak-starter.jsonl", "slovak-family-law.jsonl", "slovak-cloud-law.jsonl")


def base_weights(base: Path) -> list[Path]:
    if not (base / "config.json").is_file():
        raise ValueError("The base must contain config.json.")
    single = base / "model.safetensors"
    index = base / "model.safetensors.index.json"
    if single.is_file():
        if index.is_file():
            raise ValueError("The base contains both a single weights file and a sharded index.")
        return [single]
    if index.is_file():
        data = json.loads(index.read_bytes())
        weight_map = data.get("weight_map") if isinstance(data, dict) else None
        if not isinstance(weight_map, dict) or not weight_map:
            raise ValueError("Missing weight map in the local safetensors index.")
        if any(
            not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+\.safetensors", name)
            for name in weight_map.values()
        ):
            raise ValueError("The safetensors index must address local shard files by name.")
        weights = [base / name for name in sorted(set(weight_map.values()))]
        if any(not path.is_file() for path in weights):
            raise ValueError("The base has missing local safetensors shards.")
        return weights
    raise ValueError("The base must contain local safetensors weights.")


def check_dataset(config: TrainingConfig):
    manifest, splits = prepared_splits(config.data_directory)
    if config.smoke_only:
        return manifest, splits
    if any(row.origin == "synthetic" for rows in splits.values() for row in rows):
        raise ValueError("Synthetic samples are reserved for explicit smoke runs.")
    holdouts = [(ROOT / "benchmarks" / name).read_bytes() for name in PROJECT_HOLDOUTS]
    missing = [
        name
        for name, data in zip(PROJECT_HOLDOUTS, holdouts, strict=True)
        if hashlib.sha256(data).hexdigest() not in manifest["holdout_sha256"]
    ]
    if missing:
        raise ValueError(
            f"Prepare the dataset with current project holdouts: {', '.join(missing)}."
        )
    questions, sources = holdout_keys(holdouts)
    if any(overlaps_holdout(row, questions, sources) for rows in splits.values() for row in rows):
        raise ValueError("Prepared training data overlaps a project benchmark holdout.")
    return manifest, splits


def preflight(config: TrainingConfig) -> dict:
    if config.output_directory.exists():
        raise ValueError("Output must be a new directory for a new training run.")
    weights = base_weights(config.base_directory)
    if not (config.base_directory / "tokenizer_config.json").is_file():
        raise ValueError("The local base must contain tokenizer_config.json.")
    if not any(
        (config.base_directory / name).is_file()
        for name in ("tokenizer.json", "tokenizer.model", "spiece.model", "vocab.json", "vocab.txt")
    ):
        raise ValueError("The local base is missing tokenizer data.")
    _, splits = check_dataset(config)
    sizes = {path.name: path.stat().st_size for path in weights}
    if not all(sizes.values()):
        raise ValueError("A local safetensors weights file is empty.")
    return {
        "status": "inputs_checked",
        "model": config.base_model_id,
        "revision": config.base_revision,
        "method": config.method,
        "target_device": config.device,
        "weight_file_sizes_bytes": sizes,
        "splits": {label: len(rows) for label, rows in splits.items()},
        "smoke_only": config.smoke_only,
    }


def file_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def base_provenance(base: Path) -> dict[str, str]:
    weights = base_weights(base)
    configuration = sorted(
        p for p in base.iterdir() if p.is_file() and p.suffix in {".json", ".jinja"}
    )
    return {path.name: file_sha256(path) for path in weights + configuration}


def encode_example(item, tokenizer, max_length: int) -> dict:
    if tokenizer.chat_template:
        prompt = tokenizer.apply_chat_template(
            [{"role": "user", "content": item.prompt}],
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        prompt = f"Používateľ: {item.prompt}\nAsistent:"
    # Tokenize the explicit completion separately so only assistant tokens receive loss.
    prefix = tokenizer.encode(prompt, add_special_tokens=False)
    completion = tokenizer.encode(item.answer, add_special_tokens=False)
    if not completion or len(prefix) + len(completion) + 1 > max_length:
        raise ValueError(f"Example {item.id} has no completion or exceeds max_length.")
    response = completion + [tokenizer.eos_token_id]
    return {"input_ids": prefix + response, "labels": [-100] * len(prefix) + response}


def checkpoint_path(output: Path, step: int | None, metadata: dict) -> Path | None:
    if step is None:
        if output.exists():
            raise ValueError(
                "Output must be a new directory. Specify a local checkpoint to resume."
            )
        output.mkdir(parents=True)
        return None
    checkpoint = output / f"checkpoint-{step}"
    previous = json.loads((output / "provenance.json").read_bytes())
    if previous != metadata or checkpoint.is_symlink() or not checkpoint.is_dir():
        raise ValueError(
            "Checkpoint provenance does not match the current data, model and settings."
        )
    return checkpoint


def train(config: TrainingConfig, resume_step: int | None):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    if config.device == "cuda" and not torch.cuda.is_available():
        raise ValueError(
            "CUDA not available. Use CPU only for appropriately small LoRA experiments."
        )
    set_seed(config.seed)
    torch.set_num_threads(config.cpu_threads)
    manifest, splits = check_dataset(config)

    packages = {name: version(name) for name in ("torch", "transformers", "peft", "accelerate")}
    if config.method == "qlora":
        packages["bitsandbytes"] = version("bitsandbytes")
    metadata = {
        "config": config.model_dump(mode="json"),
        "base_sha256": base_provenance(config.base_directory),
        "data_manifest": manifest,
        "packages": packages,
    }
    checkpoint = checkpoint_path(config.output_directory, resume_step, metadata)
    (config.output_directory / "provenance.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    tokenizer = AutoTokenizer.from_pretrained(
        config.base_directory, local_files_only=True, trust_remote_code=False
    )
    if tokenizer.eos_token_id is None:
        raise ValueError("The base tokenizer has no EOS token.")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    batch_data = {
        key: [encode_example(row, tokenizer, config.max_length) for row in rows]
        for key, rows in splits.items()
    }

    def collate(examples):
        width = max(len(row["input_ids"]) for row in examples)
        return {
            "input_ids": torch.tensor(
                [
                    row["input_ids"] + [tokenizer.pad_token_id] * (width - len(row["input_ids"]))
                    for row in examples
                ]
            ),
            "attention_mask": torch.tensor(
                [
                    [1] * len(row["input_ids"]) + [0] * (width - len(row["input_ids"]))
                    for row in examples
                ]
            ),
            "labels": torch.tensor(
                [row["labels"] + [-100] * (width - len(row["labels"])) for row in examples]
            ),
        }

    bf16 = config.device == "cuda" and torch.cuda.is_bf16_supported()
    model_options = {"local_files_only": True, "trust_remote_code": False, "use_safetensors": True}
    if config.method == "qlora":
        model_options.update(
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16 if bf16 else torch.float16,
            ),
            device_map={"": 0},
        )
    elif config.device == "cuda":
        model_options["dtype"] = torch.bfloat16 if bf16 else torch.float16
    model = AutoModelForCausalLM.from_pretrained(config.base_directory, **model_options)
    if config.method == "qlora":
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    model = get_peft_model(
        model,
        LoraConfig(
            r=config.rank,
            lora_alpha=config.alpha,
            target_modules=config.target_modules,
            task_type="CAUSAL_LM",
            bias="none",
        ),
    )
    trainable, total = model.get_nb_trainable_parameters()

    trainer = Trainer(
        model=model,
        train_dataset=batch_data["train"],
        eval_dataset=batch_data["validation"],
        data_collator=collate,
        processing_class=tokenizer,
        args=TrainingArguments(
            output_dir=str(config.output_directory),
            learning_rate=config.learning_rate,
            max_steps=config.max_steps,
            per_device_train_batch_size=config.batch_size,
            per_device_eval_batch_size=config.batch_size,
            gradient_accumulation_steps=config.accumulation,
            logging_steps=max(1, min(10, config.checkpoint_steps)),
            save_steps=config.checkpoint_steps,
            save_total_limit=3,
            report_to="none",
            disable_tqdm=True,
            fp16=config.device == "cuda" and not bf16,
            bf16=bf16,
            use_cpu=config.device == "cpu",
            seed=config.seed,
            data_seed=config.seed,
            dataloader_num_workers=0,
            dataloader_pin_memory=config.device == "cuda",
        ),
    )

    before = trainer.evaluate(eval_dataset=batch_data["test"], metric_key_prefix="test")
    trainer.train(resume_from_checkpoint=str(checkpoint) if checkpoint else None)
    after_validation = trainer.evaluate()
    after = trainer.evaluate(eval_dataset=batch_data["test"], metric_key_prefix="test")
    adapter = config.output_directory / "adapter"
    trainer.save_model(adapter)
    report = {
        "model": config.model_name,
        "method": config.method,
        "device": config.device,
        "steps": trainer.state.global_step,
        "seed": config.seed,
        "smoke_only": config.smoke_only,
        "trainable_parameters": trainable,
        "parameters": total,
        "test_loss_before": before["test_loss"],
        "test_loss_after": after["test_loss"],
        "validation_loss_after": after_validation["eval_loss"],
        "training_loss_log": [entry for entry in trainer.state.log_history if "loss" in entry],
        "adapter_sha256": {
            path.name: file_sha256(path)
            for path in sorted(adapter.glob("adapter*"))
            if path.is_file()
        },
    }
    (config.output_directory / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume-step", type=int)
    mode.add_argument(
        "--preflight", action="store_true", help="Check inputs without loading models."
    )
    args = parser.parse_args()
    if args.resume_step is not None and not re.fullmatch(r"[1-9][0-9]*", str(args.resume_step)):
        parser.error("--resume-step must name a positive checkpoint step.")
    try:
        config = TrainingConfig.model_validate_json(args.config.read_bytes())
        result = preflight(config) if args.preflight else train(config, args.resume_step)
    except ValidationError:
        parser.error("Training configuration failed validation.")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
