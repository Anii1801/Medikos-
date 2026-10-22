"""Profile every CSV / JSONL actually present under Datasets/ (never trusts a manifest).

    cd backend && PYTHONPATH=. python -m training.audit_datasets
Writes evaluation_results/dataset_profile.json and prints a markdown table.
"""
import csv, json, sys
from pathlib import Path
from collections import Counter
from app.datasets import DATASET_ROOT

csv.field_size_limit(sys.maxsize)
OUT = Path(__file__).resolve().parents[2] / "evaluation_results" / "dataset_profile.json"


def profile(path: Path) -> dict:
    if path.suffix == ".jsonl":
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        cols = sorted({k for r in rows for k in r})
        rows = [{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows]
    else:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rd = csv.DictReader(fh); cols = rd.fieldnames or []; rows = list(rd)
    empty = sum(1 for r in rows for c in cols if str(r.get(c, "")).strip() == "")
    sig = Counter(tuple(str(r.get(c, "")) for c in cols) for r in rows)
    d = {"rows": len(rows), "columns": len(cols), "column_names": cols[:14], "empty_cell_share": round(empty / max(1, len(rows) * len(cols)), 4),
         "exact_duplicate_rows": sum(v - 1 for v in sig.values() if v > 1)}
    for key in ("split", "language", "source_type", "label", "triage_label", "doc_type"):
        if key in cols:
            d[f"{key}_counts"] = dict(Counter(r[key] for r in rows).most_common(8))
    return d


res = {}
for p in sorted(DATASET_ROOT.rglob("*")):
    if p.is_file() and p.suffix in (".csv", ".jsonl") and "fhir_bundles" not in str(p):
        res[str(p.relative_to(DATASET_ROOT))] = profile(p)
res["_image_files_present"] = sum(1 for p in DATASET_ROOT.rglob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"))
res["_audio_files_present"] = sum(1 for p in DATASET_ROOT.rglob("*") if p.suffix.lower() in (".wav", ".mp3", ".flac", ".m4a", ".ogg"))
OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
print("| file | rows | cols | empty cells | exact dup rows |\n|---|---:|---:|---:|---:|")
for k, v in res.items():
    if not k.startswith("_"):
        print(f"| `{k}` | {v['rows']:,} | {v['columns']} | {v['empty_cell_share']:.1%} | {v['exact_duplicate_rows']} |")
print("images/pdfs on disk:", res["_image_files_present"], " audio files on disk:", res["_audio_files_present"])
