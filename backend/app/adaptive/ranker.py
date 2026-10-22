"""Learned next-question-slot ranker: dependency-free inference + reviewed-fallback signals.

The checkpoint is plain JSON (multinomial logistic regression weights) with a
SHA-256 recorded in ``manifest.json``; no pickle is ever loaded, so a tampered
artefact cannot execute code. The ranker only RANKS slots. It never decides
safety questions, never invents a question, and signals a fallback whenever it
is outside the situation it was trained for.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .features import featurize
from .schema import STOP, TARGET_CLASSES

MODELS_DIR = Path(os.environ.get(
    "MEDIKIOSK_MODELS_DIR", Path(__file__).resolve().parents[2] / "models"))
DEFAULT_MODEL = os.environ.get("MEDIKIOSK_ADAPTIVE_MODEL", "adaptive_ranker/v1")


class RankerUnavailable(RuntimeError):
    pass


@dataclass
class RankResult:
    ranked: list[tuple[str, float]] = field(default_factory=list)   # (slot, probability), best first
    confidence: float = 0.0          # model probability for the slot that decides the next question
    oov_ratio: float = 1.0           # share of complaint-text n-grams never seen in training
    fallback_reason: str | None = None

    @property
    def usable(self) -> bool:
        return self.fallback_reason is None


class LearnedSlotRanker:
    def __init__(self, config: dict[str, Any], weights: dict[str, Any], manifest: dict[str, Any]):
        self.config, self.manifest = config, manifest
        self.classes: list[str] = weights["classes"]
        self.vocab: dict[str, int] = weights["vocab"]
        self.intercept: list[float] = weights["intercept"]
        # coef[class][feature_index], stored sparsely as {feature_index: weight} per class
        self.coef: list[dict[int, float]] = [{int(k): v for k, v in row.items()} for row in weights["coef"]]
        self.version: str = config["version"]
        thr = config["fallback_thresholds"]
        self.min_confidence: float = thr["min_confidence"]
        self.max_oov: float = thr["max_oov_ratio"]

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, model: str = DEFAULT_MODEL, models_dir: Path | None = None) -> "LearnedSlotRanker":
        base = (models_dir or MODELS_DIR) / model
        try:
            manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
            raw = (base / "weights.json").read_bytes()
        except OSError as exc:
            raise RankerUnavailable(f"checkpoint not found at {base}: {exc}") from exc
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest.get("weights_sha256"):
            raise RankerUnavailable("weights.json does not match the SHA-256 recorded in manifest.json")
        config = json.loads((base / "config.json").read_text(encoding="utf-8"))
        return cls(config, json.loads(raw), manifest)

    # ---------------------------------------------------------------- inference
    def _probabilities(self, feats: dict[str, float]) -> dict[str, float]:
        idx = [(self.vocab[k], v) for k, v in feats.items() if k in self.vocab]
        logits = []
        for c in range(len(self.classes)):
            row = self.coef[c]
            logits.append(self.intercept[c] + sum(row.get(i, 0.0) * v for i, v in idx))
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        z = sum(exps)
        return {cls_: e / z for cls_, e in zip(self.classes, exps)}

    def rank(self, state: dict[str, Any], candidates: Iterable[str] | None = None) -> RankResult:
        """Rank the askable ``candidates`` for ``state``.

        The model predicts the next slot given the slots asked so far. To rank several candidates we
        roll it forward: take its best unasked slot; if that slot is askable it is next in the ranking;
        either way it is then treated as asked and the model is queried again. A slot the app cannot ask
        (e.g. 'rad' outside chest pain) is thus skipped instead of destroying the ranking.
        ``confidence`` is the model's own probability for the slot that decides the NEXT question; a
        ``fallback_reason`` is set whenever the model should not be trusted for this situation."""
        if not (state.get("cc_text") or "").strip():
            return RankResult(fallback_reason="empty_state")
        remaining = [c for c in (candidates if candidates is not None else TARGET_CLASSES) if c in self.classes and c != STOP]
        if not remaining:
            return RankResult(fallback_reason="no_known_candidates")
        _, text_feats = featurize(state)
        known = sum(1 for k in text_feats if k in self.vocab)
        oov = 1.0 - (known / len(text_feats)) if text_feats else 1.0
        asked = list(state.get("asked") or [])
        ranked: list[tuple[str, float]] = []
        decision_confidence: float | None = None
        pool = {c for c in self.classes if c != STOP and c not in asked}
        for _ in range(len(self.classes)):
            if not pool or not remaining:
                break
            probs = self._probabilities(featurize({"cc_text": state["cc_text"], "asked": asked})[0])
            top = max(pool, key=lambda c: probs[c])
            if top in remaining:
                ranked.append((top, probs[top]))
                remaining.remove(top)
                if decision_confidence is None:
                    decision_confidence = probs[top]
            pool.discard(top)
            asked.append(top)
        for c in remaining:                      # slots the model never ranked: keep them, lowest priority
            ranked.append((c, 0.0))
        conf = decision_confidence if decision_confidence is not None else 0.0
        reason = None
        if oov > self.max_oov:
            reason = "unfamiliar_complaint"
        elif conf < self.min_confidence:
            reason = "low_confidence"
        return RankResult(ranked=ranked, confidence=conf, oov_ratio=oov, fallback_reason=reason)


_CACHED: dict[str, Any] = {}


def get_default_ranker() -> LearnedSlotRanker | None:
    """Load the default checkpoint once; ``None`` (never an exception) if unavailable."""
    if "ranker" not in _CACHED:
        try:
            _CACHED["ranker"] = LearnedSlotRanker.load()
        except (RankerUnavailable, KeyError, ValueError):
            _CACHED["ranker"] = None
    return _CACHED["ranker"]
