"""Canonical history slots and the mappings between the dataset, the ontology and safety rules.

Review status: every clinical choice in this file (which questions are
mandatory first, which slots are safety critical) is an ENGINEERING PROPOSAL
that is *pending local clinician sign-off*. Nothing here is clinically validated.
"""
from __future__ import annotations

REVIEW_STATUS = "provisional_pending_local_clinician_signoff"

#: The 13 question slots that appear in the supplied interview dataset
#: (``AI`` rows in slot_inventory.csv), in the order of the recorded template.
CANONICAL_SLOTS: tuple[str, ...] = (
    "cc", "dur", "char", "rad", "agg", "rel", "sev", "assoc", "pmh", "drug", "allergy", "fam", "pers",
)
#: Terminal class: the recorded interviews end with a CONFIRM turn (stop asking, confirm with patient).
STOP = "STOP"
#: AI rows in the dataset that are not history questions.
NON_QUESTION_SLOTS = {"RED_FLAG_ALERT"}
DATASET_AI_SLOT_TO_CLASS = {**{s: s for s in CANONICAL_SLOTS}, "CONFIRM": STOP}
TARGET_CLASSES: tuple[str, ...] = tuple(s for s in CANONICAL_SLOTS if s != "cc") + (STOP,)

#: Which canonical slot(s) each *ontology* question covers. Questions that are
#: absent here (progression, site/location, morning stiffness, ROS, free text,
#: AYUSH) are valid clinical questions that simply have no counterpart in the
#: dataset's 13-slot schema; they can be ordered but cannot be scored by it.
ONTOLOGY_TO_CANONICAL: dict[str, tuple[str, ...]] = {
    "cc": ("cc",), "cc_text": ("cc",),
    "dur": ("dur",), "sev": ("sev",),
    "cp_char": ("char",), "fv_pat": ("char",), "co_type": ("char",), "ha_type": ("char",), "hpi_char": ("char",),
    "cp_rad": ("rad",),
    "cp_agg": ("agg", "rel"), "hpi_mod": ("agg", "rel"),
    "assoc": ("assoc",), "fv_exp": ("assoc",), "co_night": ("assoc",), "st_rel": ("assoc",), "ha_assoc": ("assoc",),
    "pmh": ("pmh",), "meds": ("drug",), "allergy": ("allergy",), "fam": ("fam",), "pers": ("pers",),
}

#: Ontology questions that exist only since the v1 coverage fix. The frozen
#: "ontology_v0" baseline used in evaluations excludes them.
V1_ADDITIONS = frozenset({"hpi_char", "hpi_mod"})

#: Safety layer (authoritative, never reordered by the learned model): for each
#: ontology chief complaint, the questions whose answers drive the red-flag rules.
#: They are asked before any model-ranked question. PENDING CLINICIAN SIGN-OFF.
MANDATORY_FIRST: dict[str, tuple[str, ...]] = {
    "Chest pain": ("cp_rad", "cp_char", "assoc"),
    "Headache": ("ha_type", "ha_assoc"),
    "Cough / breathlessness": ("co_type", "co_night", "assoc"),
    "Stomach pain": ("st_rel",),
    "Fever": ("fv_exp",),
    "Weakness / tiredness": ("assoc",),
}

#: Slots whose omission is counted as a safety-critical omission in evaluations.
SAFETY_CRITICAL_SLOTS: tuple[str, ...] = ("sev", "assoc", "pmh", "drug", "allergy")
SAFETY_CRITICAL_EXTRA_BY_COMPLAINT: dict[str, tuple[str, ...]] = {
    "chest pain": ("char", "rad"),
    "sudden weakness on one side and slurred speech": ("char", "rad"),
}

#: Dataset complaint -> (ontology chief-complaint option, text the app would hold
#: for the ranker). "Other" complaints are typed by the patient, so the text is
#: the complaint itself. This mapping is an ORACLE complaint normalisation used
#: only to exercise the real backend with the dataset's interviews.
COMPLAINT_TO_ONTOLOGY_CC: dict[str, str] = {
    "chest pain": "Chest pain",
    "burning in the chest and stomach after meals": "Stomach pain",
    "fever": "Fever",
    "cough and breathlessness": "Cough / breathlessness",
    "pain in the abdomen": "Stomach pain",
    "headache with dizziness": "Headache",
    "knee pain": "Joint / back pain",
    "low back pain": "Joint / back pain",
    "joint pain and morning stiffness": "Joint / back pain",
    "sudden weakness on one side and slurred speech": "Weakness / tiredness",
    "constipation": "Other",
    "excessive thirst and frequent urination": "Other",
    "itching with skin rash": "Other",
    "difficulty sleeping": "Other",
}


def canonical_slots_for(question_id: str) -> tuple[str, ...]:
    return ONTOLOGY_TO_CANONICAL.get(question_id, ())


def covered_slots(question_ids) -> set[str]:
    out: set[str] = set()
    for qid in question_ids:
        out.update(canonical_slots_for(qid))
    return out
