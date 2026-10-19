from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import DatasetError, load_manifest
from .pipelines import prepare_pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="training/configs/datasets.json")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--root", default="..")
    parser.add_argument("--output", default="training/artifacts/splits")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    specs = {spec.dataset_id: spec for spec in load_manifest(Path(args.manifest))}
    if args.dataset_id not in specs:
        raise SystemExit(f"Unknown dataset id: {args.dataset_id}")
    try:
        print(json.dumps(prepare_pipeline(Path(args.root), specs[args.dataset_id],
                                           Path(args.output), args.seed), indent=2))
    except DatasetError as exc:
        raise SystemExit(f"DATASET PREPARATION FAILED: {exc}") from exc


if __name__ == "__main__":
    main()
