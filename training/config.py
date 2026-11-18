from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from backend.tm_law.schemas import Key, Short, StrictModel


class TrainingConfig(StrictModel):
    model_name: Key
    base_directory: Path
    base_model_id: Short
    base_revision: Annotated[str, Field(pattern=r"^(?:[a-f0-9]{40}|synthetic-smoke-v1)$")]
    base_license: Short
    data_directory: Path
    output_directory: Path
    method: Literal["lora", "qlora"] = "lora"
    device: Literal["cpu", "cuda"] = "cuda"
    rank: Annotated[int, Field(ge=1, le=128)] = 8
    alpha: Annotated[int, Field(ge=1, le=256)] = 16
    target_modules: Annotated[list[Key], Field(min_length=1, max_length=32)]
    max_steps: Annotated[int, Field(ge=1, le=100_000)] = 100
    checkpoint_steps: Annotated[int, Field(ge=1)] = 25
    max_length: Annotated[int, Field(ge=32, le=8192)] = 512
    batch_size: Annotated[int, Field(ge=1, le=32)] = 1
    accumulation: Annotated[int, Field(ge=1, le=64)] = 4
    learning_rate: Annotated[float, Field(gt=0, le=0.1)] = 0.0002
    seed: Annotated[int, Field(ge=0, le=2**32 - 1)] = 42
    cpu_threads: Annotated[int, Field(ge=1, le=16)] = 2
    smoke_only: bool = False

    @model_validator(mode="after")
    def check_modes(self):
        if self.method == "qlora" and self.device != "cuda":
            raise ValueError("QLoRA in this implementation requires CUDA.")
        if self.smoke_only != (self.base_revision == "synthetic-smoke-v1"):
            raise ValueError("The synthetic foundation is restricted to explicit smoke runs.")
        if self.checkpoint_steps > self.max_steps:
            raise ValueError("checkpoint_steps must be at most max_steps.")
        return self
