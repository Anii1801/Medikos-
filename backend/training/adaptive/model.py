"""Fit and export the next-slot ranker (multinomial logistic regression -> plain-JSON weights).

sklearn is used ONLY for fitting. Inference everywhere (CV folds, evaluation, the live backend)
goes through ``app.adaptive.ranker.LearnedSlotRanker`` so there is one inference code path.
"""
from __future__ import annotations

import collections
from typing import Any, Sequence

import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

from app.adaptive.features import featurize
from app.adaptive.ranker import LearnedSlotRanker
from app.adaptive.schema import TARGET_CLASSES
from .data import Example

DEFAULT_THRESHOLDS = {"min_confidence": 0.5, "max_oov_ratio": 0.5}   # fixed a priori, validated on LOCO (see evaluate.py)


def _matrix(examples: Sequence[Example], vocab: dict[str, int]):
    rows, cols, vals = [], [], []
    for r, e in enumerate(examples):
        for k, v in featurize(e.state)[0].items():
            j = vocab.get(k)
            if j is not None:
                rows.append(r); cols.append(j); vals.append(v)
    return sparse.csr_matrix((vals, (rows, cols)), shape=(len(examples), len(vocab)))


def fit_weights(examples: Sequence[Example], C: float, seed: int, min_df: int = 2) -> dict[str, Any]:
    df: collections.Counter = collections.Counter()
    for e in examples:
        df.update(featurize(e.state)[0].keys())
    keep = sorted(k for k, c in df.items() if c >= min_df or not k.startswith("t:"))
    vocab = {k: i for i, k in enumerate(keep)}
    X = _matrix(examples, vocab)
    y = np.array([e.target for e in examples])
    clf = LogisticRegression(C=C, max_iter=5000, random_state=seed)
    clf.fit(X, y)
    classes = [str(c) for c in clf.classes_]
    coef = []
    for row in clf.coef_:
        coef.append({str(j): round(float(w), 5) for j, w in enumerate(row) if abs(w) >= 1e-4})
    return {"classes": classes, "vocab": vocab, "intercept": [round(float(b), 5) for b in clf.intercept_], "coef": coef}


def runtime_ranker(weights: dict[str, Any], version: str, thresholds: dict[str, float] | None = None) -> LearnedSlotRanker:
    config = {"version": version, "fallback_thresholds": dict(thresholds or DEFAULT_THRESHOLDS)}
    return LearnedSlotRanker(config, weights, {"weights_sha256": None})


def validation_log_loss(ranker: LearnedSlotRanker, examples: Sequence[Example]) -> float:
    classes = ranker.classes
    probs = np.array([[p[c] for c in classes] for p in (ranker._probabilities(featurize(e.state)[0]) for e in examples)])
    probs = np.clip(probs, 1e-9, 1.0)
    return float(log_loss([e.target for e in examples], probs, labels=classes))


def predict_next(ranker: LearnedSlotRanker, e: Example) -> list[tuple[str, float]]:
    """Raw next-slot distribution over ALL classes (including STOP), best first."""
    probs = ranker._probabilities(featurize(e.state)[0])
    return sorted(probs.items(), key=lambda kv: -kv[1])
