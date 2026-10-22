# Model card: adaptive_ranker/v1

**Purpose.** Rank the next history-taking question slot from the pre-answer interview state, inside a deterministic safety layer. Optional; off by default.
**Not for.** Diagnosis, triage, disease prediction, or any use that bypasses the clinician-reviewed rules.
**Model.** Multinomial logistic regression (sklearn fit; JSON weights; numpy-free pure-Python inference). 13 target classes.
**Data.** 240 train / 30 valid interviews from `Datasets/.../01_history_interview` (SYNTHETIC, templated, 14 complaints). Test split (30) never used for selection.
**Metrics.** See `docs/EVALUATION_RESULTS.md` sections A1-A7. Headline: top-1 ~100% equals a template lookup, so it demonstrates imitation of the recorded template, not adaptive skill.
**Known failure modes.** Does not reliably defer on unseen complaints (stays confident; errors concern `rad` applicability). Hindi/English complaint text only. Order-invariant state: cannot use answer content.
**Safety.** Mandatory safety questions precede it; it cannot drop questions; falls back to the reviewed ontology order on any doubt or error. `review_status: provisional_pending_local_clinician_signoff`.
**Provenance.** `manifest.json` records data hashes, seed, environment, git commit, command, and the SHA-256 of the weights (verified at load).
