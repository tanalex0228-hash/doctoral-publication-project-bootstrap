#!/usr/bin/env python
"""Export governed metadata and private evidence for an offline archival bundle.

Run from the repository after configuring the normal PostgreSQL environment:
    python scripts/export_portable_data.py /secure/export/2026-09-25
"""

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import django  # noqa: E402

django.setup()

from django.core.files.storage import default_storage  # noqa: E402
from reporting.portable_export import EXPORT_MODELS, document_manifest, rows_for  # noqa: E402


def write_csv(path, rows):
    rows = list(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["id"])
        writer.writeheader()
        writer.writerows(rows)


def safe_destination(root, storage_key):
    target = (root / storage_key).resolve()
    if root.resolve() not in target.parents:
        raise ValueError("Unsafe document storage key in export manifest.")
    return target


def main():
    parser = argparse.ArgumentParser(description="Create a portable metadata and private-evidence export bundle.")
    parser.add_argument("output", type=Path, help="An empty or new operator-controlled output directory")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata = output / "metadata"
    metadata.mkdir(exist_ok=True)
    for name, model in EXPORT_MODELS.items():
        write_csv(metadata / f"{name}.csv", rows_for(model))
    manifest = document_manifest()
    (metadata / "source_documents.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    private_root = output / "private_files"
    for document in manifest:
        if not default_storage.exists(document["storage_key"]):
            continue
        target = safe_destination(private_root, document["storage_key"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with default_storage.open(document["storage_key"], "rb") as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)
    print(f"Portable export written to {output}")


if __name__ == "__main__":
    main()
