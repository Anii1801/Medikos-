"""ClinicalNLPService - fact-level clinical information extraction.

Rule-based BASELINE (method="rule_v1"). It is NOT a trained model, it reports no
calibrated confidence (``confidence`` is always None), and it supports English only.
Hindi / code-mixed text is not handled and must be reviewed by a human.

What it does that a keyword search does not:
  * assertion status per mention: present / absent / uncertain / historical /
    hypothetical, plus experiencer (patient vs family);
  * negation scope is limited to the clause, so "black stools but no vomiting blood"
    yields one present and one absent fact instead of suppressing both;
  * temporal normalisation ("for 3 days", "two years ago", "since yesterday");
  * medication / dose / frequency and allergy extraction with unit normalisation;
  * provenance (source id, source type, original clause, character span);
  * conflict detection between facts (never silently resolved).

Missing information is never converted to a negative: no fact is emitted for a
concept that is not mentioned.
"""
from __future__ import annotations

from . import hindi_nlp
import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

METHOD = "rule_v1"

Assertion = Literal["present", "absent", "uncertain", "historical", "hypothetical"]


class TemporalContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["duration", "onset", "ago", "relative", "current"]
    text: str
    duration_days: float | None = None
    approximate: bool = False


class ClinicalFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_id: str
    field: Literal["symptom", "condition", "medication", "allergy", "measurement"]
    concept: str
    normalized_value: str | dict[str, Any] | None = None
    assertion: Assertion
    experiencer: Literal["patient", "family"] = "patient"
    temporal: TemporalContext | None = None
    original_text: str            # the clause the fact came from, original wording
    source_id: str
    source_type: Literal["patient", "document", "observation"] = "patient"
    span: tuple[int, int]         # character span of the mention inside the source text
    confidence: float | None = None   # deliberately None: rule baseline is uncalibrated
    method: str = METHOD
    verification_status: Literal["unverified", "clinician_confirmed", "clinician_rejected"] = "unverified"


# --------------------------------------------------------------------------- lexicon
# (concept, field, regex). Patterns cover natural phrasing, not only list options.
_S = "symptom"
_C = "condition"
LEXICON: list[tuple[str, str, str]] = [
    ("chest_pain", _S, r"chest\s+(?:pain|discomfort|pressure|tightness|heaviness)|pain\s+(?:in|over|across)\s+(?:my\s+|the\s+)?chest|(?:pressure|heaviness|tightness)\s+(?:in|on|over)\s+(?:the\s+|my\s+)?(?:centre\s+of\s+(?:my\s+|the\s+)?)?(?:center\s+of\s+(?:my\s+|the\s+)?)?chest"),
    ("pressure_heaviness", _S, r"pressure\s*/\s*heaviness|\bpressure\b|\bheaviness\b"),
    ("sweating", _S, r"\bsweat(?:ing|y|s)?\b|\bperspir\w*"),
    ("radiation_arm_jaw", _S, r"arm\s*/\s*jaw\s*/\s*back|(?:arm|jaw)\b[^.;]{0,25}\bpain|pain\b[^.;]{0,25}\b(?:arm|jaw)\b|\bradiat\w+|spread\w*\s+to\s+(?:my\s+|the\s+)?(?:arm|jaw|back)"),
    ("breathlessness", _S, r"breathless\w*|short(?:ness)?\s+of\s+breath|difficulty\s+breathing|trouble\s+breathing"),
    ("respiratory_distress", _S, r"(?:can(?:no|')?t|cannot|can\s+not|unable\s+to)\s+(?:even\s+)?(?:breathe|catch\s+my\s+breath)|(?:can\s+)?barely\s+breathe|struggling\s+to\s+breathe|gasping|breathless\w*\s+at\s+rest|(?:severe|extreme)\s+(?:breathlessness|shortness\s+of\s+breath)|(?:unable|cannot|can't)\s+to?\s*speak\s+(?:a\s+)?full\s+sentences?|unable\s+to\s+speak\s+full\s+sentences"),
    ("speech_disturbance", _S, r"slurred\s+speech|slurring|speech\s+(?:is|was|has\s+been|became|feels?)\s+(?:\w+\s+)?(?:slurred|slurring|garbled)|(?:can(?:no|')?t|cannot|unable\s+to)\s+(?:speak|talk)\s+properly|difficulty\s+(?:speaking|talking)|trouble\s+(?:speaking|talking)"),
    ("facial_droop", _S, r"fac(?:e|ial)\s+(?:is\s+|was\s+|feels?\s+)?(?:droop\w*|sagging|falling|numb)|droop\w*\s+(?:of\s+(?:my\s+|the\s+)?)?(?:face|mouth)|one\s+side\s+of\s+(?:my\s+|the\s+)?face"),
    ("focal_weakness", _S, r"(?:one[- ]sided|unilateral)\s+weakness|weakness\s+(?:of|in|on)\s+(?:the\s+|my\s+)?(?:face|arms?|legs?|one\s+side|left|right)|weakness\s+of\s+face\s*/\s*arm\s*/\s*leg|(?:my\s+)?(?:arm|leg|hand)\s+(?:is\s+|feels?\s+|became\s+|has\s+become\s+)?(?:weak|numb|limp)|(?:can(?:no|')?t|cannot|unable\s+to)\s+(?:lift|move)\s+(?:my\s+)?(?:arm|leg|hand)"),
    ("vomiting_blood", _S, r"vomit\w*\s+(?:of\s+)?blood|blood\s+in\s+(?:my\s+|the\s+)?vomit|h(?:a)?ematemesis|coffee[- ]ground"),
    ("melaena", _S, r"black\s+(?:tarry\s+)?(?:stools?|motions?)|\bmel(?:a)?ena\b|tarry\s+stools?|blood\s+in\s+(?:my\s+|the\s+)?stools?|black\s+stools?\s*/\s*blood"),
    ("fever", _S, r"\bfever\w*|\bfebrile\b|high\s+temperature|\bbukhar\b"),
    ("rash", _S, r"\brash(?:es)?\b|skin\s+spots?|\bhives\b"),
    ("bleeding", _S, r"bleeding\s+gums|(?<!vaginal )\bbleed\w*\b"),
    ("vaginal_bleeding", _S, r"vaginal\s+bleeding|bleeding\s+(?:from|per)\s+(?:the\s+|my\s+)?vagina|\bspotting\b"),
    ("pregnancy", _C, r"\bpregnan\w*|\bexpecting\b"),
    ("severe_abdominal_pain", _S, r"(?:severe|intense|unbearable|terrible)\s+(?:abdominal|stomach|belly|tummy)\s+pain|(?:abdominal|stomach|belly|tummy)\s+pain\s+(?:is\s+)?(?:severe|unbearable)"),
    ("self_harm", _S, r"self[- ]harm\w*|suicid\w*|want(?:ing|ed)?\s+to\s+die|kill\s+myself|end\s+my\s+life|harm\s+myself|better\s+off\s+dead"),
    ("syncope", _S, r"\bfaint(?:ed|ing)?\b|passed\s+out|blacked\s+out|\bsyncope\b|\bcollapsed\b|dizziness\s*/\s*fainting"),
    ("cough", _S, r"\bcough\w*"),
    ("dizziness", _S, r"\bdizz\w*|\bgiddiness\b|\blight[- ]?headed\b|\bvertigo\b"),
    ("headache", _S, r"head\s*ache|\bhead\s+pain\b|worst\s+headache"),
    ("neck_stiffness", _S, r"neck\s+(?:stiffness|rigidity)|stiff\s+neck|neck\s+aakar"),
    ("vomiting", _S, r"\bvomit\w*+(?!\s+(?:of\s+)?blood)|\bthrowing\s+up\b|\bnausea\b"),
    ("weight_loss", _S, r"weight\s+loss|losing\s+weight|lost\s+weight"),
    ("abdominal_pain", _S, r"(?:abdominal|stomach|belly|tummy)\s+pain|pain\s+in\s+(?:my\s+|the\s+)?(?:abdomen|stomach|belly)"),
    ("diabetes", _C, r"\bdiabet\w*|\bsugar\s+(?:problem|disease)"),
    ("hypertension", _C, r"hypertension|high\s+(?:bp|blood\s+pressure)|\bbp\s+problem"),
    ("asthma", _C, r"\basthma\b"),
    ("tuberculosis", _C, r"tuberculosis|\btb\b"),
    ("heart_disease", _C, r"heart\s+(?:disease|attack|condition|problem)|cardiac\s+(?:disease|history)|\bcoronary\b"),
    ("kidney_disease", _C, r"kidney\s+(?:disease|failure|problem)|\brenal\s+(?:disease|failure)"),
    ("thyroid_disease", _C, r"\bthyroid\b"),
    ("stroke_history", _C, r"\bstroke\b|\blakwa\b|paralysis"),
]
_COMPILED = [(c, f, re.compile(p, re.I)) for c, f, p in LEXICON]
_COMPILED += [(c, f, re.compile(p, re.I)) for c, f, p in hindi_nlp.LEXICON_HI]   # Hindi/Hinglish terms reuse the same concept names

# ------------------------------------------------------------------------ assertion cues
_NEG_PRE = re.compile(
    r"\b(?:no|not|never|without|denies|denied|deny|denying|negative\s+for|free\s+of|absence\s+of|nil|nor|neither"
    r"|don'?t|doesn'?t|didn'?t|haven'?t|hasn'?t|hadn'?t|do\s+not|does\s+not|did\s+not|have\s+not|has\s+not)\b", re.I)
_NEG_POST = re.compile(r"^[\s,:\-]*(?:\w+\s+){0,2}?(?:is\s+|are\s+|was\s+|were\s+)?(?:not\s+present|absent|ruled\s+out|negative|denied)\b", re.I)
_UNCERTAIN = re.compile(
    r"\b(?:not\s+sure|unsure|uncertain|not\s+certain|don'?t\s+know|do\s+not\s+know|dont\s+know|can'?t\s+tell|cannot\s+tell"
    r"|maybe|perhaps|possibly|probably|might|could\s+be|i\s+think|i\s+guess|suspect\w*|seems?\s+like|not\s+clear)\b", re.I)
_PRE_PSEUDO_NEG = re.compile(r"\bno\s+(?:doubt|change|improvement)\b|\bnot\s+only\b", re.I)
_RESOLVED = re.compile(r"\b(?:recovered|resolved|settled|subsided|gone|went\s+away|cleared|no\s+longer|not\s+any\s*more|fully\s+recovered)\b", re.I)
_HIST_CUE = re.compile(
    r"\b(?:last\s+year|years?\s+ago|months?\s+ago|previously|in\s+the\s+past|history\s+of|used\s+to|formerly|childhood|as\s+a\s+child"
    r"|in\s+(?:19|20)\d\d|a\s+long\s+time\s+ago|earlier\s+in\s+life)\b", re.I)
_ONGOING = re.compile(r"\b(?:today|now|currently|right\s+now|at\s+the\s+moment|this\s+morning|tonight|still|started|began|since|ongoing|for\s+the\s+(?:last|past))\b", re.I)
_HYPO = re.compile(r"\b(?:if\s+i|in\s+case|what\s+if|worried\s+(?:about|that)|afraid\s+(?:of|that)|scared\s+(?:of|that))\b", re.I)
_FAMILY = re.compile(r"\b(?:my|his|her)\s+(?:father|mother|dad|mom|mum|brother|sister|son|daughter|grand\w+|uncle|aunt|parents?|family)\b|\bfamily\s+history\b|\bruns\s+in\s+(?:the|my)\s+family\b", re.I)
_CLAUSE_SPLIT = re.compile(r"\s+(?:but|however|although|though|except|yet|while)\s+|\s+and\s+(?=(?:i|my|now|there|she|he|it|today)\b)", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")

# ------------------------------------------------------------------------ temporal
_NUMW = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "couple": 2}
_UNIT_DAYS = {"minute": 1 / 1440, "hour": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}
_NUM = r"(?P<n>\d+(?:\.\d+)?|a\s+few|a\s+couple\s+of|couple\s+of|several|few|an|a|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_UNIT = r"(?P<u>minute|hour|day|week|month|year)s?"
_APPROX_EN = r"(?:(?:about|around|approximately|approx\.?|roughly|nearly|almost)\s+)?"
_T_DUR = re.compile(rf"\b(?:for|since|from|over)\s+(?:the\s+)?(?:last\s+|past\s+)?{_APPROX_EN}{_NUM}\s+{_UNIT}\b", re.I)
_T_BARE = re.compile(rf"^\s*{_APPROX_EN}{_NUM}\s+{_UNIT}\b", re.I)    # a bare answer to 'how long?': "About 2 weeks."
_T_AGO = re.compile(rf"\b{_NUM}\s+{_UNIT}\s+ago\b", re.I)
_T_SINCE = re.compile(r"\bsince\s+(?P<w>yesterday|this\s+morning|morning|last\s+night|today|last\s+week|last\s+month|last\s+year)\b", re.I)
_T_REL = re.compile(r"\b(?P<w>last\s+(?:year|month|week)|this\s+(?:year|month|week))\b", re.I)
_SINCE_DAYS = {"yesterday": 1, "this morning": 0.3, "morning": 0.3, "last night": 0.5, "today": 0.2,
               "last week": 7, "last month": 30, "last year": 365}


def _num(token: str) -> tuple[float | None, bool]:
    t = re.sub(r"\s+", " ", token.lower().strip())
    if t in ("few", "a few", "several"):
        return None, True
    if "couple" in t:
        return 2.0, True
    if t in _NUMW:
        return float(_NUMW[t]), False
    try:
        return float(t), False
    except ValueError:
        return None, True


def parse_temporal(text: str) -> TemporalContext | None:
    """Normalise a temporal expression to days. Approximate values are flagged."""
    for rx, kind in ((_T_DUR, "duration"), (_T_AGO, "ago"), (_T_BARE, "duration")):
        m = rx.search(text)
        if m:
            n, approx = _num(m.group("n"))
            approx = approx or bool(re.match(r"\W*(?:for\s+|since\s+|from\s+|over\s+)?(?:the\s+)?(?:last\s+|past\s+)?(?:about|around|approx|roughly|nearly|almost)", m.group(0), re.I))
            unit = m.group("u").lower()
            days = None if n is None else round(n * _UNIT_DAYS[unit], 4)
            return TemporalContext(kind=kind, text=m.group(0), duration_days=days, approximate=approx)
    m = _T_SINCE.search(text)
    if m:
        w = re.sub(r"\s+", " ", m.group("w").lower())
        return TemporalContext(kind="onset", text=m.group(0), duration_days=float(_SINCE_DAYS[w]), approximate=True)
    m = _T_REL.search(text)
    if m:
        w = re.sub(r"\s+", " ", m.group("w").lower())
        unit = w.split()[1]
        return TemporalContext(kind="relative", text=m.group(0), duration_days=float(_UNIT_DAYS[unit]), approximate=True)
    hi = hindi_nlp.parse_temporal_hi(text)
    if hi:
        return TemporalContext(**hi)
    m = re.search(r"\b(?:today|right\s+now|currently|at\s+the\s+moment|now)\b", text, re.I)
    if m:
        return TemporalContext(kind="current", text=m.group(0), duration_days=0.0)
    return None


# ---------------------------------------------------------------- medications / allergies
_MED_STOP = {"take", "taking", "took", "about", "dose", "doses", "with", "and", "the", "of", "for", "per", "only", "tablet",
             "tablets", "tab", "capsule", "medicine", "medicines", "drug", "daily", "night", "morning", "once", "twice",
             "every", "since", "have", "has", "had", "need", "needs", "is", "was", "are", "on", "my", "i", "of"}
_MED = re.compile(
    r"\b(?P<name>[A-Za-z][A-Za-z\-]{2,})\s*(?P<dose>\d+(?:\.\d+)?)\s*(?P<unit>mg|mcg|µg|ug|g|ml|iu|units?)\b"
    r"(?:\s*(?P<freq>once\s+(?:a\s+)?daily|twice\s+(?:a\s+)?daily|thrice\s+(?:a\s+)?daily|three\s+times\s+(?:a|per)\s+day|two\s+times\s+(?:a|per)\s+day|"
    r"\d+\s+times?\s+(?:a|per)\s+day|every\s+\d+\s+hours|at\s+night|\bod\b|\bbd\b|\bbid\b|\btid\b|\btds\b|\bqid\b|\bqd\b|\bhs\b|daily))?", re.I)
_FREQ_PER_DAY = {"od": 1, "qd": 1, "daily": 1, "once daily": 1, "once a daily": 1, "bd": 2, "bid": 2, "twice daily": 2, "twice a daily": 2,
                 "two times a day": 2, "two times per day": 2, "tid": 3, "tds": 3, "thrice daily": 3, "three times a day": 3,
                 "three times per day": 3, "qid": 4, "hs": 1, "at night": 1}
_NO_MEDS = re.compile(r"\b(?:no|not\s+taking\s+any|don'?t\s+take\s+any|do\s+not\s+take\s+any)\s+(?:regular\s+)?(?:medicines?|medications?|drugs?|tablets?)\b|\bnone\b", re.I)
_ALLERGY = re.compile(r"\ballerg(?:ic|y|ies)\s+(?:to\s+)?(?P<a>[A-Za-z][A-Za-z\- ]{2,40}?)(?=\s+(?:causing|with|and|which|that|\()|[.,;]|$)", re.I)
_NO_ALLERGY = re.compile(r"\bno\s+(?:known\s+)?(?:drug\s+|food\s+|medicine\s+)?allerg(?:y|ies)\b|\bnkda\b|\bnot\s+allergic\b", re.I)
_NO_ALLERGY = re.compile(_NO_ALLERGY.pattern + "|" + hindi_nlp.NO_ALLERGY_HI, re.I)
_NO_MEDS = re.compile(_NO_MEDS.pattern + "|" + hindi_nlp.NO_MEDS_HI, re.I)
_REACTION = re.compile(r"\b(rash|hives|swelling|anaphylaxis|breathing\s+difficulty|vomiting|itching)\b", re.I)
_TEMP = re.compile(r"(?P<v>\d{2,3}(?:\.\d)?)\s*(?:°|deg(?:rees)?\s*)?\s*(?P<u>f|c|fahrenheit|celsius)\b", re.I)
_SPO2 = re.compile(r"(?:spo2|oxygen\s+saturation|saturation)\D{0,12}(?P<v>\d{2,3})\s*%?", re.I)
_BP = re.compile(r"\b(?P<s>\d{2,3})\s*/\s*(?P<d>\d{2,3})\s*(?:mm\s*hg)?\b", re.I)


def normalise_dose(value: float, unit: str) -> dict[str, Any]:
    """Return the dose in a canonical unit where one exists (mass -> mg)."""
    u = unit.lower().replace("µ", "u")
    if u == "g":
        return {"dose_mg": value * 1000.0}
    if u in ("mcg", "ug"):
        return {"dose_mg": value / 1000.0}
    if u == "mg":
        return {"dose_mg": value}
    return {"dose": value, "unit": u}


def _norm_text(s: str) -> str:
    # 1:1 character replacements only, so offsets into the original text stay valid.
    return s.translate(str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u00a0": " "}))


class ClinicalNLPService:
    """Stateless extractor. ``extract`` never raises on odd text; it returns what it can."""

    def extract(self, text: Any, *, source_id: str, source_type: str = "patient") -> list[ClinicalFact]:
        if text is None:
            return []
        if isinstance(text, (list, tuple)):
            out: list[ClinicalFact] = []
            for i, item in enumerate(text):
                out += self.extract(item, source_id=f"{source_id}[{i}]", source_type=source_type)
            return out
        raw = str(text)
        if not raw.strip():
            return []
        norm = _norm_text(raw)
        if hindi_nlp.has_devanagari(norm):
            # Match on a spelling-normalised copy (nukta, chandrabindu, digits), then map spans and quoted text back to the
            # ORIGINAL text so provenance still points at what the patient actually wrote.
            hn, idx = hindi_nlp.normalise_with_map(norm)
            return [self._remap(f, hn, idx, raw) for f in self._extract_normalised(hn, hn, source_id, source_type)]
        return self._extract_normalised(norm, raw, source_id, source_type)

    @staticmethod
    def _remap(fact: ClinicalFact, hn: str, idx: list[int], raw: str) -> ClinicalFact:
        def back(a: int, b: int) -> tuple[int, int]:
            a = min(max(a, 0), len(idx) - 1)
            b = min(max(b, a + 1), len(idx))
            return idx[a], idx[b - 1] + 1
        update: dict[str, Any] = {}
        if fact.span:
            update["span"] = back(*fact.span)
        pos = hn.find(fact.original_text) if fact.original_text else -1
        if pos >= 0:
            oa, ob = back(pos, pos + len(fact.original_text))
            update["original_text"] = raw[oa:ob]
        return fact.model_copy(update=update)

    def _extract_normalised(self, norm: str, raw: str, source_id: str, source_type: str) -> list[ClinicalFact]:
        facts: list[ClinicalFact] = []
        offset = 0
        for sent_m in re.finditer(r"[^.!?;\n]+[.!?;]?", norm):
            sent = sent_m.group(0)
            s0 = sent_m.start()
            if not sent.strip():
                continue
            facts += self._sentence(sent, s0, raw, source_id, source_type)
            offset = sent_m.end()
        facts += self._meds_allergies_measurements(norm, raw, source_id, source_type)
        return facts

    def extract_many(self, sources: list[dict[str, Any]]) -> list[ClinicalFact]:
        facts: list[ClinicalFact] = []
        for s in sources:
            facts += self.extract(s.get("text"), source_id=s["source_id"], source_type=s.get("source_type", "patient"))
        return facts

    # ------------------------------------------------------------------ internals
    def _sentence(self, sent: str, s0: int, raw: str, source_id: str, source_type: str) -> list[ClinicalFact]:
        facts: list[ClinicalFact] = []
        sent_temporal = parse_temporal(sent)
        pos = 0
        for clause in _CLAUSE_SPLIT.split(sent):
            c0 = sent.find(clause, pos)
            if c0 < 0:
                c0 = pos
            pos = c0 + len(clause)
            if not clause.strip():
                continue
            seen: set[tuple[str, int]] = set()
            for concept, fld, rx in _COMPILED:
                for m in rx.finditer(clause):
                    key = (concept, m.start())
                    if key in seen:
                        continue
                    seen.add(key)
                    # A reaction named inside an allergy statement ("allergic to X causing rash")
                    # is part of the allergy fact, not a separate current symptom.
                    if fld == "symptom" and re.search(r"\ballerg", clause[:m.start()], re.I):
                        continue
                    assertion, experiencer = self._assert(clause, m.start(), m.end(), fld)
                    temporal = parse_temporal(clause) or sent_temporal
                    facts.append(ClinicalFact(
                        fact_id=uuid.uuid4().hex[:12], field=fld, concept=concept,
                        normalized_value=concept.replace("_", " "), assertion=assertion, experiencer=experiencer,
                        temporal=temporal, original_text=raw[s0 + c0: s0 + c0 + len(clause)].strip(),
                        source_id=source_id, source_type=source_type,
                        span=(s0 + c0 + m.start(), s0 + c0 + m.end())))
                    break  # one mention per concept per clause is enough
        return facts

    @staticmethod
    def _assert(clause: str, start: int, end: int, fld: str) -> tuple[Assertion, str]:
        pre_words = re.findall(r"\S+", clause[:start])[-7:]
        pre = " ".join(pre_words)
        post = clause[end:end + 45]
        experiencer = "family" if (_FAMILY.search(clause[:start]) or _FAMILY.search(pre) or hindi_nlp.family_cue(pre)) else "patient"
        hi_post = hindi_nlp.post_cue(post)
        if _HYPO.search(pre):
            return "hypothetical", experiencer
        if (_UNCERTAIN.search(pre) or re.match(r"^[\s,]*(?:or\s+not|\?)", post, re.I)
                or hindi_nlp.pre_uncertain(pre) or hi_post == "uncertain"):
            return "uncertain", experiencer
        pre_clean = _PRE_PSEUDO_NEG.sub(" ", pre)
        if _NEG_PRE.search(pre_clean) or _NEG_POST.match(post) or hi_post == "absent" or hindi_nlp.pre_negation(pre):
            return "absent", experiencer
        if fld == "symptom" and experiencer == "patient":
            if re.search(r"\bno\s+longer\b|\bnot\s+any\s*more\b", clause, re.I):
                return "absent", experiencer
            if _RESOLVED.search(clause):
                return "historical", experiencer      # "recovered", "resolved", "gone"
            if _HIST_CUE.search(clause) and not _ONGOING.search(clause):
                return "historical", experiencer      # "last year", "2 years ago" with no ongoing cue
        return "present", experiencer

    def _meds_allergies_measurements(self, norm: str, raw: str, source_id: str, source_type: str) -> list[ClinicalFact]:
        facts: list[ClinicalFact] = []

        def add(fld, concept, value, assertion, m, original):
            facts.append(ClinicalFact(
                fact_id=uuid.uuid4().hex[:12], field=fld, concept=concept, normalized_value=value, assertion=assertion,
                original_text=original, source_id=source_id, source_type=source_type, span=(m.start(), m.end())))

        for m in _MED.finditer(norm):
            name = m.group("name").lower()
            if name in _MED_STOP:
                continue
            dose = normalise_dose(float(m.group("dose")), m.group("unit"))
            freq = (m.group("freq") or "").lower().strip()
            freq = re.sub(r"\s+", " ", freq)
            value = {"name": name, **dose, "reported_dose": f"{m.group('dose')} {m.group('unit')}",
                     "frequency_text": freq or None, "times_per_day": _FREQ_PER_DAY.get(freq)}
            add("medication", name, value, "present", m, raw[m.start():m.end()])
        if _NO_MEDS.search(norm) and not _MED.search(norm):
            m = _NO_MEDS.search(norm)
            add("medication", "medication_use", "no medicines reported", "absent", m, raw)
        if _NO_ALLERGY.search(norm):
            m = _NO_ALLERGY.search(norm)
            add("allergy", "allergy_none", "no known allergies (patient report)", "absent", m, raw)
        else:
            for m in _ALLERGY.finditer(norm):
                agent = m.group("a").strip().lower()
                if not agent or agent in ("any", "anything"):
                    continue
                rx = _REACTION.search(norm[m.end():m.end() + 60])
                add("allergy", agent, {"agent": agent, "reaction": rx.group(1).lower() if rx else None}, "present", m, raw)
        for m in _TEMP.finditer(norm):
            v = float(m.group("v"))
            u = m.group("u").lower()
            c = round((v - 32) * 5 / 9, 1) if u.startswith("f") else v
            if 30 <= c <= 45:
                add("measurement", "temperature", {"value_c": c, "reported": m.group(0)}, "present", m, raw)
        for m in _SPO2.finditer(norm):
            v = int(m.group("v"))
            if 50 <= v <= 100:
                add("measurement", "spo2", {"value_percent": v, "reported": m.group(0).strip()}, "present", m, raw)
        for m in _BP.finditer(norm):
            s, d = int(m.group("s")), int(m.group("d"))
            if 60 <= s <= 260 and 30 <= d <= 160 and s > d:
                add("measurement", "blood_pressure", {"systolic_mmHg": s, "diastolic_mmHg": d}, "present", m, raw)
        return facts

    # ------------------------------------------------------------------ conflicts
    @staticmethod
    def find_conflicts(facts: list[ClinicalFact]) -> list[dict[str, Any]]:
        """Report conflicting facts for review. Nothing is resolved or dropped."""
        out: list[dict[str, Any]] = []
        groups: dict[tuple[str, str], list[ClinicalFact]] = {}
        for f in facts:
            if f.field in ("symptom", "condition") and f.assertion in ("present", "absent"):
                groups.setdefault((f.concept, f.experiencer), []).append(f)
        for (concept, exp), fs in groups.items():
            pos = [f for f in fs if f.assertion == "present"]
            neg = [f for f in fs if f.assertion == "absent"]
            if pos and neg:
                out.append({"type": "present_vs_absent", "concept": concept, "experiencer": exp,
                            "present": [{"fact_id": f.fact_id, "source_id": f.source_id, "text": f.original_text} for f in pos],
                            "absent": [{"fact_id": f.fact_id, "source_id": f.source_id, "text": f.original_text} for f in neg],
                            "resolution": "unresolved - clinician to confirm"})
        meds: dict[str, list[ClinicalFact]] = {}
        for f in facts:
            if f.field == "medication" and isinstance(f.normalized_value, dict):
                meds.setdefault(f.concept, []).append(f)
        for name, fs in meds.items():
            doses = {(f.normalized_value.get("dose_mg"), f.normalized_value.get("dose")) for f in fs}
            if len(doses) > 1:
                out.append({"type": "medication_dose_mismatch", "concept": name,
                            "values": [{"fact_id": f.fact_id, "source_id": f.source_id,
                                        "reported": f.normalized_value.get("reported_dose")} for f in fs],
                            "resolution": "unresolved - clinician to confirm"})
        has_allergy = any(f.field == "allergy" and f.assertion == "present" for f in facts)
        no_allergy = [f for f in facts if f.concept == "allergy_none"]
        if has_allergy and no_allergy:
            out.append({"type": "allergy_conflict", "concept": "allergy",
                        "values": [{"fact_id": f.fact_id, "source_id": f.source_id, "text": f.original_text} for f in facts if f.field == "allergy"],
                        "resolution": "unresolved - clinician to confirm"})
        return out


_service: ClinicalNLPService | None = None


def get_service() -> ClinicalNLPService:
    global _service
    if _service is None:
        _service = ClinicalNLPService()
    return _service
