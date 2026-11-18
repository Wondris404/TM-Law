"""Create an artificial text foundation for an offline CPU LoRA smoke test."""

import argparse
import json
import os
from pathlib import Path

from training.dataset import prepared_splits


def create_foundation(output: Path, train_data: Path, run_directory: Path):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    import torch
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast

    _, splits = prepared_splits(train_data)
    if any(row.origin != "synthetic" for split in splits.values() for row in split):
        raise ValueError("The toy foundation may only be used with synthetic smoke inputs.")
    output.mkdir(parents=True, exist_ok=False)
    foundation = output / "base"
    pre_tokenizer = Whitespace()
    words = {
        token
        for row in splits["train"]
        for token, _ in pre_tokenizer.pre_tokenize_str(row.prompt + " " + row.answer)
    }
    tokens = ["<pad>", "<unk>", "<eos>", "Používateľ", "Asistent", ":"]
    tokens.extend(sorted(words.difference(tokens)))
    engine = Tokenizer(WordLevel({word: i for i, word in enumerate(tokens)}, unk_token="<unk>"))
    engine.pre_tokenizer = pre_tokenizer
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=engine,
        unk_token="<unk>",
        pad_token="<pad>",
        eos_token="<eos>",
        model_max_length=128,
    )
    torch.manual_seed(42)
    model = GPT2LMHeadModel(
        GPT2Config(
            vocab_size=len(tokens),
            n_layer=2,
            n_head=2,
            n_embd=48,
            n_positions=128,
            bos_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
        )
    )
    model.save_pretrained(foundation, safe_serialization=True)
    tokenizer.save_pretrained(foundation)
    config = {
        "model_name": "tm-law-smoke",
        "base_directory": str(foundation.resolve()),
        "base_model_id": "TM-Law artificial GPT2Config fixture",
        "base_revision": "synthetic-smoke-v1",
        "base_license": "MIT",
        "data_directory": str(train_data.resolve()),
        "output_directory": str(run_directory.resolve()),
        "method": "lora",
        "device": "cpu",
        "rank": 2,
        "alpha": 4,
        "target_modules": ["c_attn"],
        "max_steps": 8,
        "checkpoint_steps": 4,
        "max_length": 128,
        "accumulation": 1,
        "learning_rate": 0.002,
        "smoke_only": True,
    }
    (output / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    create_foundation(args.output, args.data, args.run_directory)


if __name__ == "__main__":
    main()
