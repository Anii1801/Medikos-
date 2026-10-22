"""Hindi / Hinglish (Devanagari and romanised) rules for the clinical NLP layer.

Scope and honesty: this is a RULE-BASED layer. It covers negation, uncertainty, numbers, durations, a core
symptom/condition lexicon, family-experiencer cues and "no allergy / no medicine" statements. It was measured on
the project's SYNTHETIC templated Hindi answers (training/hindi_nlp_eval.py) and on a small hand-written set; it is
not validated Hindi clinical understanding. Known gaps are listed in docs/HINDI_HINGLISH_NLP.md.

Concept names deliberately reuse the English lexicon's names so that the existing red-flag rules fire on Hindi input.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_DEV = "\u0900-\u097F"
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def has_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text or "")


def normalise(text: str) -> str:
    """Canonicalise spelling variants so one pattern matches them: nukta dropped (ज़->ज), chandrabindu -> anusvara
    (पाँच->पांच), Devanagari digits -> ASCII. Length may change; use :func:`normalise_with_map` when offsets matter."""
    return normalise_with_map(text)[0]


def normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Return (normalised text, index map) where ``map[i]`` is the position in ``text`` of normalised char ``i``."""
    src = unicodedata.normalize("NFC", text or "")
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(src):
        if ch == "\u093C":                       # nukta
            continue
        if ch == "\u0901":                       # chandrabindu
            ch = "\u0902"
        out.append(ch.translate(_DEV_DIGITS))
        idx.append(i)
    return "".join(out), idx


def _n(p: str) -> str:
    return normalise(p)


def _t(p: str) -> str:
    """Token pattern with boundaries that work for both Devanagari (combining marks are not \\w) and Latin."""
    return rf"(?<![{_DEV}\w])(?:{p})(?![{_DEV}\w])"


def _rx(p: str) -> re.Pattern:
    return re.compile(_n(p), re.I)


# ------------------------------------------------------------------------------------------ assertion cues
_NEG_WORDS = r"नहीं|नही|नहि|बिना|बगैर|nahi|nahin|nahee|nhi|bina|bagair"
NEG = _rx(_t(_NEG_WORDS))
UNCERTAIN = _rx(
    r"(?<![" + _DEV + r"\w])(?:पता\s*(?:नहीं|नही)|मालूम\s*(?:नहीं|नही)|याद\s*(?:नहीं|नही)|पक्का\s*(?:नहीं|नही)|कह\s*नहीं\s*सकत\w*|"
    r"शायद|हो\s*सकता\s*है|मुझे\s*लगता\s*है|pata\s*(?:nahi|nhi|nahin)|pta\s*(?:nahi|nhi)|maloom\s*(?:nahi|nhi)|malum\s*(?:nahi|nhi)|"
    r"yaad\s*(?:nahi|nhi)|pakka\s*(?:nahi|nhi)|shayad|ho\s*sakta\s*hai|mujhe\s*lagta\s*hai)(?![" + _DEV + r"\w])")
DECLINE = _rx(r"(?:नहीं|नही)\s*बताना|बताना\s*(?:नहीं|नही)|बताने\s*का\s*मन\s*नहीं|(?:nahi|nhi)\s*batana|batana\s*(?:nahi|nhi)")

_POST_BREAK = re.compile(_n(r"[,;।.]|\bऔर\b|\bलेकिन\b|\bपर\b|\bकिंतु\b|\baur\b|\blekin\b|\bbut\b"), re.I)
_POST_NEG = re.compile(r"^[\s]*(?:[^\s,;।.]+\s+){0,2}?" + _t(_NEG_WORDS), re.I)
_UNC_POST = re.compile(r"^[\s]*(?:[^\s,;।.]+\s+){0,2}?" + _t(r"शायद|हो\s*सकता\s*है|shayad|ho\s*sakta\s*hai"), re.I)
_FAMILY_STRICT = _rx(
    r"(?<![" + _DEV + r"\w])(?:पिता(?:जी)?|पापा|माँ|मां|माता(?:जी)?|मम्मी|भाई|बहन|दादा|दादी|नाना|नानी|चाचा|मामा|मौसी|बुआ|बेटा|बेटी|परिवार|"
    r"papa|pitaji|mummy|maa|bhai|behen|bahan|dada|dadi|nana|nani|chacha|mama|parivar)\s*(?:को|में|के|ki|ko|mein|ke)(?![" + _DEV + r"\w])")


def classify_answer_hi(text: str) -> str | None:
    """'uncertain' | 'negative' | 'reported' for Hindi/Hinglish text, or None if there is no Hindi/Hinglish cue at all
    (the caller then falls back to the English rules). Uncertainty and declining are checked BEFORE negation because
    'पता नहीं' / 'batana nahi' contain a negation word."""
    t = normalise(text or "")
    if DECLINE.search(t) or UNCERTAIN.search(t):
        return "uncertain"
    if NEG.search(t):
        return "negative"
    return "reported" if has_devanagari(t) else None


def post_cue(post: str) -> str | None:
    """Assertion cue AFTER a concept (Hindi is verb-final: 'बुखार नहीं है'). Looks only up to the next
    comma / conjunction so 'सिरदर्द है, चक्कर नहीं' does not negate the headache."""
    post = normalise(post)
    m = _POST_BREAK.search(post)
    window = post[: m.start()] if m else post
    if _UNC_POST.match(window):
        return "uncertain"
    if _POST_NEG.match(window):
        return "absent"
    return None


def pre_negation(pre: str) -> bool:
    """'बिना बुखार के' / 'bina bukhar ke' (without fever): a negation cue BEFORE the concept."""
    return bool(re.search(_n(_t(r"बिना|बगैर|bina|bagair")), normalise(pre), re.I))


def pre_uncertain(pre: str) -> bool:
    return bool(re.search(_n(_t(r"शायद|मुझे\s*लगता\s*है|shayad|mujhe\s*lagta\s*hai")), normalise(pre), re.I))


def family_cue(pre: str) -> bool:
    return bool(_FAMILY_STRICT.search(normalise(pre)))


# ------------------------------------------------------------------------------------------ numbers and durations
_NUM_WORDS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "छह": 6, "छः": 6, "छे": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15, "बीस": 20, "तीस": 30, "आधा": 0.5, "आधे": 0.5, "डेढ": 1.5, "ढाई": 2.5,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "chhah": 6, "che": 6, "saat": 7,
    "aath": 8, "nau": 9, "das": 10, "barah": 12, "pandrah": 15, "bees": 20, "tees": 30, "aadha": 0.5, "adha": 0.5, "dedh": 1.5, "dhai": 2.5,
}
_NUM_WORDS = {normalise(k): v for k, v in _NUM_WORDS.items()}
_UNIT_DAYS = {
    "दिन": 1, "दिनों": 1, "din": 1, "dino": 1, "dinon": 1,
    "हफ्ता": 7, "हफ्ते": 7, "हफ्तों": 7, "हफ्तो": 7, "सप्ताह": 7, "hafta": 7, "hafte": 7, "haftey": 7, "hafton": 7, "hafto": 7,
    "महीना": 30, "महीने": 30, "महीनों": 30, "माह": 30, "mahina": 30, "mahine": 30, "mahinon": 30, "mahino": 30, "maheena": 30, "maheene": 30,
    "साल": 365, "सालों": 365, "वर्ष": 365, "बरस": 365, "saal": 365, "saalon": 365, "sal": 365, "baras": 365, "varsh": 365,
    "घंटा": 1 / 24, "घंटे": 1 / 24, "घंटों": 1 / 24, "ghanta": 1 / 24, "ghante": 1 / 24, "ghantey": 1 / 24, "ghanton": 1 / 24,
    "मिनट": 1 / 1440, "minute": 1 / 1440, "min": 1 / 1440,
}
_UNIT_DAYS = {normalise(k): v for k, v in _UNIT_DAYS.items()}
_APPROX = _rx(_t(r"करीब|क़रीब|लगभग|तकरीबन|कुछ|कई|अंदाज़न|karib|kareeb|lagbhag|takriban|kuch|kai|around|about"))
_NUMTOKEN = r"(?P<n>\d+(?:\.\d+)?|" + "|".join(sorted(map(re.escape, _NUM_WORDS), key=len, reverse=True)) + r"|कुछ|कई|kuch|kai)"
_UNITTOKEN = r"(?P<u>" + "|".join(sorted(map(re.escape, _UNIT_DAYS), key=len, reverse=True)) + r")"
_DUR = re.compile(rf"(?<![{_DEV}\w]){_NUMTOKEN}\s*{_UNITTOKEN}(?![{_DEV}\w])", re.I)
_AGO = re.compile(r"\s*(?:पहले|pehle|pahle)", re.I)
_SINCE_WORDS = {"कल से": ("yesterday", 1.0), "परसों से": ("day before yesterday", 2.0), "आज सुबह से": ("this morning", 0.3), "आज से": ("today", 0.2),
                "kal se": ("yesterday", 1.0), "parson se": ("day before yesterday", 2.0), "aaj subah se": ("this morning", 0.3),
                "कल रात से": ("last night", 0.5), "kal raat se": ("last night", 0.5)}
_SINCE_WORDS = {normalise(k): v for k, v in _SINCE_WORDS.items()}


def parse_temporal_hi(text: str) -> dict[str, Any] | None:
    """Normalise a Hindi/Hinglish duration to days. Returns {kind, text, duration_days, approximate} or None.
    'कुछ दिन' (a few days) is approximate with no day count; 'करीब 4 महीने से' is approximate with 120 days."""
    t = normalise(text or "")
    m = _DUR.search(t)
    if m:
        raw_n = m.group("n").lower()
        unit_days = _UNIT_DAYS[m.group("u").lower()]
        approx = bool(_APPROX.search(t[: m.end()]))
        if raw_n in (normalise("कुछ"), normalise("कई"), "kuch", "kai"):
            return {"kind": "duration", "text": m.group(0), "duration_days": None, "approximate": True}
        n = float(raw_n) if re.fullmatch(r"\d+(?:\.\d+)?", raw_n) else float(_NUM_WORDS[raw_n])
        kind = "ago" if _AGO.match(t[m.end():]) else "duration"
        return {"kind": kind, "text": m.group(0), "duration_days": round(n * unit_days, 4), "approximate": approx}
    for phrase, (_, days) in _SINCE_WORDS.items():
        if phrase in t:
            return {"kind": "onset", "text": phrase, "duration_days": days, "approximate": True}
    m = re.search(_n(_t(r"बचपन\s*से|bachpan\s*se|जन्म\s*से|janm\s*se")), t, re.I)
    if m:
        return {"kind": "relative", "text": m.group(0), "duration_days": None, "approximate": True}
    return None


def parse_number_hi(text: str) -> float | None:
    """First number in Hindi/Hinglish text: ASCII or Devanagari digits ('७'), or a number word ('सात', 'saat')."""
    t = normalise(text or "")
    m = re.search(r"\d+(?:\.\d+)?", t)
    if m:
        return float(m.group(0))
    for w in sorted(_NUM_WORDS, key=len, reverse=True):
        if re.search(rf"(?<![{_DEV}\w]){re.escape(w)}(?![{_DEV}\w])", t, re.I):
            return float(_NUM_WORDS[w])
    return None


# ------------------------------------------------------------------------------------------ lexicon (reuses English concept names)
_L = r"(?<![" + _DEV + r"\w])"
_R = r"(?![" + _DEV + r"\w])"
_LEX = [
    ("chest_pain", "symptom", r"सीने\s*(?:में|मे|का)\s*(?:दर्द|जकड़न|जकडन|भारीपन|दबाव|जलन)|छाती\s*(?:में\s*)?(?:दर्द|जकड़न|भारीपन)|seene\s*(?:mein|me|main|ka)\s*(?:dard|bharipan|dabav|dabaav)|chhati\s*(?:mein\s*)?dard"),
    ("pressure_heaviness", "symptom", r"भारीपन|दबाव|bharipan|dabaav|dabav"),
    ("sweating", "symptom", r"पसीन\w*|paseena|pasina|paseene"),
    ("breathlessness", "symptom", r"सांस\s*(?:फूल\w*|की\s*तकलीफ|लेने\s*में\s*(?:तकलीफ|दिक्कत|परेशानी))|दम\s*फूल\w*|saans\s*phool\w*|saans\s*(?:lene\s*mein\s*)?(?:takleef|dikkat)|dam\s*phool\w*"),
    ("respiratory_distress", "symptom", r"सांस\s*(?:ही\s*)?(?:नहीं|नही)\s*(?:ले\s*पा|आ\s*पा)\w*|सांस\s*लेना\s*(?:बहुत\s*)?मुश्किल|saans\s*nahi\s*le\s*pa\w*"),
    ("speech_disturbance", "symptom", r"बोलने\s*में\s*(?:दिक्कत|तकलीफ|परेशानी|लड़खड़ाहट|लडखडाहट)|जुबान\s*(?:लड़खड़|अटक)\w*|बोल\s*(?:नहीं|नही)\s*पा\w*|लड़खड़ाहट|bolne\s*mein\s*(?:dikkat|takleef)|zubaan\s*lad\w*|zubaan\s*atak\w*"),
    ("facial_droop", "symptom", r"(?:चेहरा|चेहरे|मुंह|मुँह)\s*(?:एक\s*तरफ\s*)?(?:टेढ़ा|टेढा|टेढ़े|लटक\w*)|chehra\s*tedha|munh\s*tedha"),
    ("focal_weakness", "symptom", r"एक\s*तरफ[^.;।]{0,20}कमजोरी|कमजोरी[^.;।]{0,20}एक\s*तरफ|(?:हाथ|पैर|बांह|टांग)\s*(?:में\s*)?(?:कमजोरी|सुन्न|कमजोर)|आधे\s*शरीर\s*(?:में|का)|ek\s*taraf\s*kamzori|haath\s*(?:mein\s*)?kamzori|pair\s*(?:mein\s*)?kamzori"),
    ("vomiting_blood", "symptom", r"खून\s*की\s*उल्टी|उल्टी\s*(?:में\s*)?खून|khoon\s*ki\s*ulti"),
    ("melaena", "symptom", r"काला\s*(?:मल|टट्टी|पखाना)|काले\s*(?:मल|दस्त)|मल\s*(?:में\s*)?खून|kala\s*(?:mal|potty|tatti)"),
    ("fever", "symptom", r"बुखार|ज्वर|bukhar|bukhaar|tez\s*taap|\btaap\b"),
    ("rash", "symptom", r"चकत्ते|दाने|रैश|daane|chakatte"),
    ("bleeding", "symptom", r"खून\s*(?:आ|बह)\w*|रक्तस्राव|khoon\s*(?:aa|beh)\w*"),
    ("vaginal_bleeding", "symptom", r"योनि\s*से\s*(?:खून|रक्त)"),
    ("pregnancy", "condition", r"गर्भवती|गर्भ\b|प्रेग्नेंट|pregnant"),
    ("severe_abdominal_pain", "symptom", r"पेट\s*(?:में\s*)?(?:बहुत|तेज|असहनीय|भयंकर)\s*दर्द|pet\s*(?:mein\s*)?(?:bahut|tez)\s*dard"),
    ("abdominal_pain", "symptom", r"पेट\s*(?:में\s*)?दर्द|पेट\s*दर्द|pet\s*(?:mein\s*)?dard"),
    ("self_harm", "symptom", r"आत्महत्या|खुदकुशी|मरना\s*चाह\w*|मर\s*जाना\s*चाह\w*|जान\s*देना|खुद\s*को\s*(?:नुकसान|खत्म|मार)|marna\s*chah\w*|khudkushi|jaan\s*dena|atmahatya"),
    ("syncope", "symptom", r"बेहोश\w*|चक्कर\s*खाकर\s*गिर\w*|behosh\w*"),
    ("dizziness", "symptom", r"चक्कर|chakkar"),
    ("cough", "symptom", r"खांसी|खासी|khansi|khaansi|khasi"),
    ("headache", "symptom", r"सिर\s*(?:में\s*)?दर्द|सिरदर्द|सर\s*(?:में\s*)?दर्द|सरदर्द|माथे\s*में\s*दर्द|sir\s*(?:mein\s*)?dard|sirdard|sar\s*(?:mein\s*)?dard|sardard"),
    ("neck_stiffness", "symptom", r"गर्दन\s*(?:में\s*)?(?:अकड़न|अकडन|अकड़|जकड़न)|gardan\s*(?:mein\s*)?akad\w*"),
    ("vomiting", "symptom", r"उल्टी|उलटी|जी\s*मिचला\w*|मितली|ulti|jee\s*michla\w*|ji\s*michla\w*"),
    ("weight_loss", "symptom", r"वजन\s*(?:कम|घट)\w*|wajan\s*(?:kam|ghat)\w*|vajan\s*(?:kam|ghat)\w*"),
    ("diabetes", "condition", r"शुगर|मधुमेह|डायबिटीज|diabetes"),
    ("hypertension", "condition", r"हाई\s*बीपी|उच्च\s*रक्तचाप|बीपी\s*(?:की\s*)?(?:समस्या|बीमारी)|high\s*bp"),
    ("asthma", "condition", r"अस्थमा|दमा\b|asthma"),
    ("tuberculosis", "condition", r"टीबी|तपेदिक|क्षय\s*रोग"),
    ("heart_disease", "condition", r"दिल\s*की\s*बीमारी|हृदय\s*रोग|दिल\s*का\s*दौरा|हार्ट\s*अटैक|dil\s*ki\s*bimari|dil\s*ka\s*daura"),
    ("kidney_disease", "condition", r"किडनी\s*(?:की\s*)?(?:बीमारी|खराबी|समस्या)|गुर्दे\s*(?:की|में)"),
    ("thyroid_disease", "condition", r"थायराइड|थायरॉइड"),
    ("stroke_history", "condition", r"लकवा|पक्षाघात|स्ट्रोक|lakwa"),
]
LEXICON_HI: list[tuple[str, str, str]] = [(c, f, _L + "(?:" + _n(p) + ")" + (_R if not p.endswith("\\w*") else "")) for c, f, p in _LEX]

NO_ALLERGY_HI = _n(r"कोई\s*(?:दवा\s*(?:की\s*)?)?एलर्जी\s*(?:नहीं|नही)|एलर्जी\s*(?:नहीं|नही)|(?:koi\s*)?allergy\s*(?:nahi|nhi|nahin)")
NO_MEDS_HI = _n(r"कोई\s*(?:दवा|दवाई|गोली)\s*(?:नहीं|नही)|(?:दवा|दवाई)\s*(?:नहीं|नही)\s*(?:लेता|लेती|लेते)|koi\s*(?:dawa|dawai|goli)\s*(?:nahi|nhi|nahin)|dawai?\s*(?:nahi|nhi)\s*(?:leta|leti)")
