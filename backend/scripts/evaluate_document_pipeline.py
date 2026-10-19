"""Evaluate OCR on a permissioned JSONL image set without inventing results.

Each row must contain {"image": "path", "reference": "transcript"}.
The script deliberately exits with a clear message when no evaluation set is
provided; bundled synthetic examples are not treated as clinical evidence.
"""
import argparse
import difflib
import json
from pathlib import Path

from app.ocr import ocr_document


def baseline(data: bytes) -> str:
    from PIL import Image
    import io
    import pytesseract
    return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang="eng")


def distance(a: str, b: str) -> int:
    return sum(tag[2] - tag[1] if tag[0] != "equal" else 0
               for tag in difflib.SequenceMatcher(None, a, b).get_opcodes())


def error_rate(pred: str, ref: str, words: bool = False) -> float:
    left, right = (pred.split(), ref.split()) if words else (list(pred), list(ref))
    return distance(left, right) / max(1, len(right))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, required=True,
                        help="permissioned JSONL with image and reference transcript")
    args = parser.parse_args()
    if not args.pairs.exists():
        raise SystemExit(f"Evaluation file not found: {args.pairs}; no metrics were produced.")
    rows = [json.loads(line) for line in args.pairs.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise SystemExit("Evaluation file is empty; no metrics were produced.")
    scores = []
    for row in rows:
        path = Path(row["image"])
        data = path.read_bytes()
        text, engine, _ = ocr_document(data, path.name)
        reference = row["reference"]
        base = baseline(data)
        scores.append({"baseline_cer": error_rate(base, reference), "baseline_wer": error_rate(base, reference, True),
                       "proposed_cer": error_rate(text, reference), "proposed_wer": error_rate(text, reference, True),
                       "engine": engine})
    print(json.dumps({"documents": len(scores),
                      "baseline_cer": sum(x["baseline_cer"] for x in scores) / len(scores),
                      "baseline_wer": sum(x["baseline_wer"] for x in scores) / len(scores),
                      "proposed_cer": sum(x["proposed_cer"] for x in scores) / len(scores),
                      "proposed_wer": sum(x["proposed_wer"] for x in scores) / len(scores),
                      "note": "Field-level and clinical correctness require annotated structured references."},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
