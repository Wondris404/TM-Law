import argparse
from pathlib import Path

from backend.tm_law.schemas import LegalVersion
from backend.tm_law.store import Store


def main():
    parser = argparse.ArgumentParser(description="Import a locally supplied legal version JSON.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path(".tm-law"))
    args = parser.parse_args()
    with args.source.open("rb") as handle:
        data = handle.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        parser.error("Import is limited to 5 MiB per version")
    version = LegalVersion.model_validate_json(data)
    store = Store(args.data_dir)
    store.initialize()
    digest, created = store.import_version(version)
    print(
        f"{version.version_id}: {'imported' if created else 'already present'} (SHA-256 {digest})"
    )


if __name__ == "__main__":
    main()
