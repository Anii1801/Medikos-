"""State -> sparse features. Single definition shared by training and serving.

A *state* is only what is known immediately BEFORE the next question is asked:
    {"cc_text": <patient's chief-complaint wording>, "asked": [<canonical slots asked so far, in order>]}
No later patient answer can enter a feature; ``tests/test_adaptive_ranker.py``
verifies this by mutating the future and checking the features do not change.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

NGRAM_RANGE = (2, 4)
_PUNCT = re.compile(r"[^\w\u0900-\u097F ]+", re.U)


def normalise_text(text: Any) -> str:
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = _PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def script_of(text: str) -> str:
    dev = sum("\u0900" <= ch <= "\u097F" for ch in text)
    lat = sum(ch.isascii() and ch.isalpha() for ch in text)
    return "devanagari" if dev > lat else "latin"


def text_ngrams(text: str, ngram_range: tuple[int, int] = NGRAM_RANGE) -> list[str]:
    padded = f" {normalise_text(text)} "
    lo, hi = ngram_range
    return [padded[i:i + n] for n in range(lo, hi + 1) for i in range(len(padded) - n + 1)]


def featurize(state: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    """Return (feature -> value, text n-gram feature names) for one state."""
    feats: dict[str, float] = {}
    grams = text_ngrams(state.get("cc_text") or "")
    names: list[str] = []
    if grams:
        weight = 1.0 / math.sqrt(len(grams))
        for g in grams:
            key = f"t:{g}"
            feats[key] = feats.get(key, 0.0) + weight
        names = list(feats)
        feats[f"lang:{script_of(normalise_text(state.get('cc_text') or ''))}"] = 1.0
    # The asked SET, not the order: the deterministic safety layer may legitimately reorder questions
    # and the model must not treat a reordered-but-complete state as unfamiliar.
    for slot in set(state.get("asked") or []):
        feats[f"a:{slot}"] = 1.0
    return feats, names
