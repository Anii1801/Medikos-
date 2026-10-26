"""OCR-in-the-loop test: render KNOWN report text to images / PDFs, run the real pipeline, score against labels.

    cd backend && PYTHONPATH=. python -m training.lab_scan_eval

Ground truth is exact (we rendered it). What this measures: Tesseract + the extractor on degraded renderings of a
single monospace layout. What it does NOT measure: real scanner/phone-camera artefacts, other fonts or layouts,
handwriting. Real, permissioned scans with annotation are still required before any real-world claim.
"""
from __future__ import annotations

import argparse
import io
import json
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app import ocr
from .lab_extraction_eval import OUT, evaluate, load

FONT = next(
    (path for path in (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/System/Library/Fonts/Menlo.ttc"),
        Path("/System/Library/Fonts/Supplemental/Courier New.ttf"),
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("C:/Windows/Fonts/cour.ttf"),
    ) if path.is_file()),
    None,
)
if FONT is None:
    raise RuntimeError("No supported monospace test font found; install DejaVu Sans Mono or use macOS Menlo.")
DEGRADE = {  # keyed by the dataset's own scan_quality tag
    "good": dict(dpi=200, rotate=0.0, blur=0.0, noise=0.0, jpeg=95),
    "fair": dict(dpi=150, rotate=1.0, blur=0.7, noise=6.0, jpeg=70),
    "poor": dict(dpi=110, rotate=2.0, blur=1.2, noise=14.0, jpeg=40),
}


def render(text: str, quality: str, seed: int) -> Image.Image:
    cfg, rnd = DEGRADE[quality], random.Random(seed)
    size = max(12, round(cfg["dpi"] / 8))
    font = ImageFont.truetype(str(FONT), size)
    lines = text.split("\n")
    w = int(size * 0.62 * max(len(l) for l in lines)) + 80
    h = int(size * 1.5 * len(lines)) + 80
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((40, 40 + i * size * 1.5), line, font=font, fill=0)
    if cfg["rotate"]:
        img = img.rotate(rnd.uniform(-cfg["rotate"], cfg["rotate"]), expand=True, fillcolor=255)
    if cfg["blur"]:
        img = img.filter(ImageFilter.GaussianBlur(cfg["blur"]))
    if cfg["noise"]:
        px = img.load()
        for _ in range(int(w * h * 0.02)):
            x, y = rnd.randrange(img.width), rnd.randrange(img.height)
            px[x, y] = max(0, min(255, px[x, y] + int(rnd.gauss(0, cfg["noise"] * 4))))
    return img


def to_png(img: Image.Image) -> bytes:
    b = io.BytesIO(); img.save(b, "PNG"); return b.getvalue()


def to_scanned_pdf(img: Image.Image, jpeg_quality: int) -> bytes:
    """Image-only PDF (no text layer): what a scanner produces."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    jb = io.BytesIO(); img.convert("RGB").save(jb, "JPEG", quality=jpeg_quality)
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=(img.width, img.height))
    c.drawImage(ImageReader(io.BytesIO(jb.getvalue())), 0, 0, img.width, img.height)
    c.save()
    return out.getvalue()


def to_text_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    out = io.BytesIO(); c = canvas.Canvas(out, pagesize=A4); c.setFont("Courier", 8)
    y = 810
    for line in text.split("\n"):
        c.drawString(30, y, line); y -= 11
    c.save()
    return out.getvalue()


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _strip_rules(text: str) -> str:
    return "\n".join(l for l in text.split("\n") if l.strip("- ") != "")


def wer(ref: str, hyp: str) -> float:
    rw, hw = ref.split(), hyp.split()
    prev = list(range(len(hw) + 1))
    for i, a in enumerate(rw, 1):
        cur = [i]
        for j, b in enumerate(hw, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a != b)))
        prev = cur
    return prev[-1] / max(1, len(rw))


def run(split: str = "test", limit: int | None = None) -> dict[str, Any]:
    labels, docs = load()
    ids = [rid for rid, g in sorted(labels.items()) if g[0]["split"] == split][:limit]
    channels: dict[str, dict[str, str]] = {"image_png": {}, "scanned_pdf": {}, "text_pdf": {}}
    cer_rows: dict[str, list[tuple[str, float, float]]] = {k: [] for k in channels}
    for n, rid in enumerate(ids):
        d = docs[rid]
        gt, q = d["ground_truth_text"], d["scan_quality"]
        img = render(gt, q, seed=n)
        blobs = {"image_png": (to_png(img), f"{rid}.png"),
                 "scanned_pdf": (to_scanned_pdf(img, DEGRADE[q]["jpeg"]), f"{rid}.pdf"),
                 "text_pdf": (to_text_pdf(gt), f"{rid}.pdf")}
        for ch, (data, fname) in blobs.items():
            text, engine, _ = ocr.ocr_document(data, fname)
            channels[ch][rid] = text
            ref, hyp = _strip_rules(gt), _strip_rules(text)   # CER/WER ignore the '-----' separator line (no clinical content)
            cer_rows[ch].append((q, edit_distance(" ".join(ref.split()), " ".join(hyp.split())) / max(1, len(" ".join(ref.split()))), wer(ref, hyp)))
    out: dict[str, Any] = {"split": split, "reports": len(ids),
                           "render_font": FONT.name,
                           "disclaimer": "synthetic rendering of one monospace layout; not evidence about real scans"}
    for ch, texts in channels.items():
        ev = evaluate("ground_truth_text", ocr.extract, (split,), text_override=texts)
        by_q: dict[str, Any] = {}
        for q in DEGRADE:
            rows = [r for r in cer_rows[ch] if r[0] == q]
            if rows:
                by_q[q] = {"reports": len(rows), "char_error_rate_excluding_rule_lines": round(sum(r[1] for r in rows) / len(rows), 4),
                           "word_error_rate_excluding_rule_lines": round(sum(r[2] for r in rows) / len(rows), 4)}
        out[ch] = {"ocr_by_scan_quality": by_q,
                   "extraction": {k: v for k, v in ev.items() if k not in ("per_test", "error_examples", "critical_result_note")},
                   "empty_ocr_output": sum(1 for t in texts.values() if not t.strip())}
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, default=OUT / "lab_scan_eval.json")
    args = parser.parse_args()
    res = run(args.split, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(res, indent=2), encoding="utf-8")
    for ch in ("image_png", "scanned_pdf", "text_pdf"):
        print(ch, json.dumps(res[ch]["ocr_by_scan_quality"]), json.dumps({k: res[ch]["extraction"][k] for k in
              ("test_name_recall", "exact_value_accuracy", "unit_accuracy", "printed_reference_interval_accuracy", "abnormal_status_accuracy_vs_printed_flag", "false_abnormal_rate_on_printed_normal", "ambiguous_extraction_rate")}))
