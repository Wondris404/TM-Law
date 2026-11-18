import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

from backend.tm_law.corpus import (
    coverage,
    draft_sections,
    load_package,
    original_text,
    read_limited,
)
from backend.tm_law.extract import MAX_UPLOAD
from backend.tm_law.store import Store


def main():
    parser = argparse.ArgumentParser(description="Offline import of legal source packages.")
    parser.add_argument("--data-dir", type=Path, default=Path(".tm-law"))
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "import"):
        commands.add_parser(name).add_argument("manifest", type=Path)
    commands.add_parser("draft").add_argument("original", type=Path)
    export = commands.add_parser("export-original")
    export.add_argument("sha256")
    export.add_argument("output", type=Path)
    commands.add_parser("coverage")
    args = parser.parse_args()

    try:
        store = Store(args.data_dir)
        if args.command == "draft":
            raw = read_limited(args.original, MAX_UPLOAD)
            report = {
                "original_sha256": hashlib.sha256(raw).hexdigest(),
                "needs_review": True,
                "passages": draft_sections(original_text(raw, args.original.suffix.lower())),
            }
        elif args.command == "coverage":
            store.initialize()
            report = coverage(store)
        elif args.command == "export-original":
            store.initialize()
            original = store.get_legal_original(args.sha256)
            if original is None:
                parser.error("Originál sa v archíve nenašiel.")
            with args.output.open("xb") as handle:
                handle.write(original)
            report = {"sha256": args.sha256, "bytes": len(original)}
        else:
            version, original = load_package(args.manifest)
            report = {
                "version_id": version.version_id,
                "original_sha256": version.original_sha256,
                "fictional": version.fictional,
                "passages": len(version.passages),
            }
            if args.command == "import":
                store.initialize()
                digest, created = store.import_version(version, original)
                report.update(created=created, content_sha256=digest)
    except ValidationError as exc:
        fields = ", ".join(".".join(map(str, error["loc"])) or "manifest" for error in exc.errors())
        parser.error(f"Neplatné polia: {fields}")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
