# Adaptive next-question ranker v2

## Intended use

Experimental imitation of recorded next-question slots from synthetic, templated MediKiosk interviews. Not a diagnostic model and not evidence of clinical utility.

## Training

- Algorithm: multinomial scikit-learn LogisticRegression; plain JSON weights for dependency-free inference.
- Data: 300 synthetic interview groups, split 240/30/30 by patient; 7,863 dialogue turns.
- Features: complaint character n-grams (2-4), script, and previously asked slots.
- Selection: validation-only search over `C=[0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]` and `class_weight=[None, 'balanced']`; selected `{'C': 1000.0, 'class_weight': None, 'valid_log_loss': 0.00463, 'valid_top1': 0.9987, 'features': 1185}`.
- Final evaluation: held-out test split after selection; see `evaluation.json`.
- Checkpoint integrity: SHA-256 in `manifest.json`; membership hashes in `split_manifest.json`.

## Limitations

The label is mostly a repeated template. A training-only complaint/state template lookup matches or exceeds the ranker on this test set. Clinical relevance, patient safety, fairness, and generalization have not been established. The application continues to load v1 by default; this checkpoint is not integrated.
