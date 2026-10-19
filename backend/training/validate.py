from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import DatasetError, load_manifest, load_rows, validate_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="training/configs/datasets.json")
    parser.add_argument("--root", default="..")
    args = parser.parse_args()
    manifest = load_manifest(Path(args.manifest))
    root = Path(args.root)
    report = []
    for spec in manifest:
        item = {"dataset_id": spec.dataset_id, "availability": spec.availability,
                "licence_status": spec.licence_status, "notes": spec.notes}
        if spec.local_path:
            try:
                item["validation"] = validate_rows(spec, load_rows(root, spec))
            except DatasetError as exc:
                item["error"] = str(exc)
        report.append(item)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
