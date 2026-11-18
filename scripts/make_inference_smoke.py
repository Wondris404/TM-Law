"""Build a tiny artificial local Llama-format model for runtime and quantization smoke tests."""

import argparse
import os
from pathlib import Path

from training.dataset import read_examples

ROOT = Path(__file__).resolve().parents[1]


def create_foundation(output: Path):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    import sentencepiece
    import torch
    from transformers import LlamaConfig, LlamaForCausalLM

    items = read_examples((ROOT / "data" / "training-smoke.jsonl").read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    text = output / "sentences.txt"
    text.write_text("\n".join(f"{row.prompt}\n{row.answer}" for row in items), encoding="utf-8")
    sentencepiece.SentencePieceTrainer.train(
        input=str(text),
        model_prefix=str(output / "tokenizer"),
        vocab_size=384,
        model_type="bpe",
        byte_fallback=True,
        hard_vocab_limit=False,
        unk_id=0,
        bos_id=1,
        eos_id=2,
        pad_id=3,
        num_threads=1,
        minloglevel=2,
    )
    vocab = sentencepiece.SentencePieceProcessor(
        model_file=str(output / "tokenizer.model")
    ).vocab_size()
    torch.manual_seed(42)
    LlamaForCausalLM(
        LlamaConfig(
            vocab_size=vocab,
            hidden_size=256,
            intermediate_size=512,
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            max_position_embeddings=8192,
            bos_token_id=1,
            eos_token_id=2,
            pad_token_id=3,
        )
    ).save_pretrained(output, safe_serialization=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    create_foundation(args.output)


if __name__ == "__main__":
    main()
