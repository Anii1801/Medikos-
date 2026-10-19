from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import DatasetError, load_manifest, load_rows
from .pipelines import PIPELINES, smoke_train


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="training/configs/datasets.json")
    parser.add_argument("--root", default="..")
    parser.add_argument("--task", choices=sorted(PIPELINES), required=True)
    args = parser.parse_args()
    specs = {spec.dataset_id: spec for spec in load_manifest(Path(args.manifest))}
    spec = specs[PIPELINES[args.task]["dataset"]]
    try:
        print(json.dumps(smoke_train(args.task, load_rows(Path(args.root), spec)), indent=2))
    except DatasetError as exc:
        raise SystemExit(f"SMOKE TRAINING FAILED: {exc}") from exc


if __name__ == "__main__":
    main()
