"""EDA API routes — admin-level analytics and data-quality endpoints.

Purpose:
  Provides aggregate, de-identified analytics for research and audit.
  Data cleaning pipeline is logged and traceable per DPDP Act requirements.

References:
  Obermeyer & Emanuel (2016) NEJM — fairness auditing in clinical ML
  Rajkomar et al. (2019) — EHR deep learning audit trail
  Mehrabi et al. (2021) — bias & fairness survey
"""
from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException, Depends
from . import db
from .ml_pipeline import (
    eda_records, eda_lab_values, ml_red_flag_score,
    compute_text_quality_score, predict_likely_conditions, predict_prakriti_imbalance
)

router = APIRouter(prefix="/api/eda", tags=["eda"])


@router.get("/summary")
def eda_summary(limit: int = 500):
    """Aggregate EDA: CC distribution, priority mix, severity, completeness.

    De-identified — no patient names or IDs returned.
    """
    with db.tx() as c:
        rows = c.execute(
            "SELECT answers, sections, flags, priority FROM records ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    records = []
    for r in rows:
        try:
            records.append({
                "answers": json.loads(r["answers"]),
                "sections": json.loads(r["sections"]),
                "flags": json.loads(r["flags"]),
                "priority": r["priority"],
            })
        except Exception:
            continue
    return eda_records(records)


@router.get("/labs")
def eda_labs(limit: int = 500):
    """Lab-value EDA across documents uploaded to this local MediKiosk instance.

    These values are not a MIMIC benchmark and should not be interpreted as a representative cohort.
    """
    with db.tx() as c:
        rows = c.execute(
            "SELECT entities FROM documents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    all_labs = []
    for r in rows:
        try:
            all_labs.extend(json.loads(r["entities"]).get("labs", []))
        except Exception:
            continue
    return {
        "lab_stats": eda_lab_values(all_labs),
        "total_docs_analysed": len(rows),
        "note": "Descriptive statistics over locally uploaded documents only; not a clinical benchmark.",
    }


@router.get("/data-quality")
def data_quality(limit: int = 200):
    """Data cleaning quality report: OCR engine coverage, empty extractions, text quality.

    Helps identify:
      - Which OCR engine performs best
      - What fraction of documents had extractable entities
      - Average text quality score
    """
    with db.tx() as c:
        rows = c.execute(
            "SELECT engine, doc_type, text, entities FROM documents ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()

    engines: dict = {}
    doc_types: dict = {}
    entity_coverage = {"meds": 0, "labs": 0, "dx": 0}
    quality_scores = []
    empty_count = 0

    for r in rows:
        engine = r["engine"] or "unknown"
        engines[engine] = engines.get(engine, 0) + 1
        doc_types[r["doc_type"]] = doc_types.get(r["doc_type"], 0) + 1
        text = r["text"] or ""
        qs = compute_text_quality_score(text)
        quality_scores.append(qs["quality_score"])
        if qs["word_count"] < 5:
            empty_count += 1
        try:
            ent = json.loads(r["entities"])
            if ent.get("medications"): entity_coverage["meds"] += 1
            if ent.get("labs"): entity_coverage["labs"] += 1
            if ent.get("diagnoses"): entity_coverage["dx"] += 1
        except Exception:
            pass

    total = len(rows) or 1
    return {
        "total_documents": total,
        "ocr_engine_dist": engines,
        "doc_type_dist": doc_types,
        "empty_or_unreadable_pct": round(100 * empty_count / total, 1),
        "avg_text_quality_score": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0,
        "entity_extraction_coverage_pct": {
            k: round(100 * v / total, 1) for k, v in entity_coverage.items()
        },
        "cleaning_pipeline": [
            "1. OCR noise removal (pipes, braces, backslashes)",
            "2. Whitespace normalisation",
            "3. Devanagari-safe special-char stripping",
            "4. Unit normalisation (mg/dl→mg/dL, etc.)",
            "5. Medical abbreviation expansion (ADAM v3 + Indian clinical set)",
            "6. Regex NER (entities: meds, labs, diagnoses)",
        ],
    }


@router.get("/red-flag-ml/{record_id}")
def ml_flag(record_id: int):
    """Report model availability honestly; no validated risk model is bundled.

    The legacy route is retained for API compatibility, but does not expose an
    uncalibrated heuristic as a probability or a disease prediction.
    """
    with db.tx() as c:
        row = c.execute("SELECT id FROM records WHERE id=?", (record_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Record not found")
    return {
        "record_id": record_id,
        "ml_red_flag_probability": None,
        "risk_level": "NOT_VALIDATED",
        "likely_conditions": [],
        "model": "No trained or validated clinical risk model checkpoint is bundled.",
        "model_available": False,
        "disclaimer": "No model-derived risk probability or diagnosis is available. Review the rule-based red-flag evidence and assess the patient clinically.",
    }


@router.get("/ayush-analysis/{record_id}")
def ayush_analysis(record_id: int):
    """AYUSH Prakriti-Vikriti analysis for records collected in AYUSH mode.

    Dataset: AYUSH TKDL + AyurvedaNet prakriti classification corpus.
    """
    with db.tx() as c:
        row = c.execute("SELECT answers FROM records WHERE id=?", (record_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Record not found")
    answers = json.loads(row["answers"])
    if not answers.get("_ay"):
        return {"message": "Record not collected in AYUSH mode", "ayush_mode": False}
    return {
        "ayush_mode": True,
        "record_id": record_id,
        "analysis": predict_prakriti_imbalance(answers),
        "disclaimer": "Pattern-matched from TKDL reference tables. AYUSH physician assessment required.",
    }
