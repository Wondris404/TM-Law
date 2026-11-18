import argparse
import json
from pathlib import Path

from training.dataset import TeacherProvenance, prepare


def main():
    parser = argparse.ArgumentParser(
        description="Validate, deduplicate and split approved training data."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--teacher-manifest", type=Path, help="Provenance for approved teacher responses."
    )
    args = parser.parse_args()
    try:
        teacher = (
            TeacherProvenance.model_validate_json(args.teacher_manifest.read_bytes())
            if args.teacher_manifest
            else None
        )
        result = prepare(
            args.input.read_bytes(),
            [item.read_bytes() for item in args.holdout],
            args.output,
            args.seed,
            teacher=teacher,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
