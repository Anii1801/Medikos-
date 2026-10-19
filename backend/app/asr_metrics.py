"""ASR evaluation utilities; metrics are not clinical validation."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from .ocr import extract


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)


def edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, lval in enumerate(left, 1):
        current = [i]
        for j, rval in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (lval != rval)))
        previous = current
    return previous[-1]


def wer(reference: str, hypothesis: str) -> float:
    ref = _tokens(reference)
    return edit_distance(_tokens(hypothesis), ref) / max(1, len(ref))


def clinical_terms(text: str) -> set[str]:
    facts = extract(text)
    terms = {m["name"].lower() for m in facts["medications"]}
    terms.update(lab["test"].lower() for lab in facts["labs"])
    terms.update(facts["symptoms"])
    terms.update(facts["allergies"])
    return terms


def evaluate(rows: Iterable[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        language = str(row.get("language") or "unknown").lower()
        reference = row.get("reference_text") or row.get("reference") or ""
        hypothesis = row.get("transcript") or row.get("simulated_asr_text") or ""
        expected, actual = clinical_terms(reference), clinical_terms(hypothesis)
        grouped[language].append({
            "wer": wer(reference, hypothesis),
            "entity_recall": len(expected & actual) / max(1, len(expected)),
            "entity_precision": len(expected & actual) / max(1, len(actual)),
            "has_audio": bool(row.get("audio") or row.get("audio_path")),
        })
    result = {}
    for language, scores in grouped.items():
        result[language] = {
            "rows": len(scores),
            "wer": sum(x["wer"] for x in scores) / len(scores),
            "clinical_entity_recall": sum(x["entity_recall"] for x in scores) / len(scores),
            "clinical_entity_precision": sum(x["entity_precision"] for x in scores) / len(scores),
            "audio_present": all(x["has_audio"] for x in scores),
            "note": "Text-pair rows do not measure acoustic or accent performance" if not all(x["has_audio"] for x in scores) else None,
        }
    return result
