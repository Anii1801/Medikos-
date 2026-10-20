"""Medical document digitisation: OCR + clinical entity extraction + timeline + abnormal flags."""
from __future__ import annotations
import io, re
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from .datasets import read_csv


class SourceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: str
    source_id: str
    page: int | None = None
    start: int | None = None
    end: int | None = None
    bbox: list[int] | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)
    text: str


class ExtractedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    value: Any
    status: str = "reported"
    confidence: float = Field(default=0.8, ge=0, le=1)
    source: SourceSpan
    review_required: bool = False

LABS = {  # name: (aliases regex, unit, low, high)
 "Haemoglobin": (r"h(?:a)?emoglobin|\bhb\b|\bhgb\b", "g/dL", 12.0, 17.0),
 "Fasting glucose": (r"fasting (?:blood )?(?:glucose|sugar)|\bfbs\b|\bfbg\b", "mg/dL", 70, 100),
 "Post-prandial glucose": (r"post ?prandial|\bppbs\b|\bppg\b", "mg/dL", 70, 140),
 "HbA1c": (r"hba1c|glycosylated|glycated", "%", 4.0, 5.6),
 "Creatinine": (r"creatinine", "mg/dL", 0.6, 1.3),
 "Urea": (r"\burea\b|\bbun\b", "mg/dL", 15, 45),
 "TSH": (r"\btsh\b", "uIU/mL", 0.4, 4.5),
 "WBC": (r"\bwbc\b|total leu[ck]ocyte|\btlc\b", "/uL", 4000, 11000),
 "Platelets": (r"platelet|\bplt\b", "/uL", 150000, 450000),
 "Total cholesterol": (r"total cholesterol|\bcholesterol\b", "mg/dL", 0, 200),
 "LDL": (r"\bldl\b", "mg/dL", 0, 100),
 "SGPT (ALT)": (r"sgpt|\balt\b", "U/L", 7, 56),
 "Systolic BP": (r"\bbp\b|blood pressure", "mmHg", 90, 130),
}
DRUGS = ["metformin","glimepiride","insulin","amlodipine","telmisartan","losartan","atenolol","metoprolol","aspirin","clopidogrel",
 "atorvastatin","rosuvastatin","warfarin","pantoprazole","omeprazole","paracetamol","ibuprofen","diclofenac","amoxicillin","azithromycin",
 "ciprofloxacin","levothyroxine","salbutamol","montelukast","cetirizine","furosemide","spironolactone","ramipril","enalapril","ashwagandha",
 "triphala","giloy","chyawanprash","arjunarishta","dashmoolarishta"]
DX = ["diabetes","hypertension","anaemia","anemia","asthma","tuberculosis","typhoid","dengue","malaria","hypothyroidism","ckd","kidney disease",
 "coronary artery disease","angina","myocardial infarction","stroke","fracture","pneumonia","uti","fatty liver","arthritis","gastritis"]
FALLBACK_INTERACTIONS = [
 ({"warfarin","aspirin"}, "Warfarin + aspirin: bleeding risk"),
 ({"warfarin","ibuprofen"}, "Warfarin + NSAID: bleeding risk"),
 ({"warfarin","diclofenac"}, "Warfarin + NSAID: bleeding risk"),
 ({"aspirin","clopidogrel"}, "Dual antiplatelet: bleeding risk (confirm intended)"),
 ({"ramipril","spironolactone"}, "ACE inhibitor + spironolactone: hyperkalaemia risk"),
 ({"enalapril","spironolactone"}, "ACE inhibitor + spironolactone: hyperkalaemia risk"),
 ({"losartan","spironolactone"}, "ARB + spironolactone: hyperkalaemia risk"),
 ({"metformin","ibuprofen"}, "NSAID with metformin: renal risk"),
 ({"atenolol","salbutamol"}, "Beta-blocker may antagonise salbutamol (asthma)"),
 ({"warfarin","ashwagandha"}, "Herb–drug: ashwagandha may alter anticoagulant effect (verify)"),
]


def _reference_interactions() -> list[tuple[set[str], str]]:
    """Load the maintained reference and retain legacy critical alerts."""
    rows = read_csv("drug_interactions")
    if not rows:
        return FALLBACK_INTERACTIONS
    result = []
    for row in rows:
        a, b = (row.get("drug_a") or "").strip().lower(), (row.get("drug_b") or "").strip().lower()
        if not a or not b:
            continue
        note = row.get("note") or "Potential interaction: verify with a clinician"
        result.append(({a, b}, f"{a.title()} + {b.title()}: {note}"))
    known_pairs = {frozenset(pair) for pair, _ in result}
    result.extend(
        (pair, message)
        for pair, message in FALLBACK_INTERACTIONS
        if frozenset(pair) not in known_pairs
    )
    return result or FALLBACK_INTERACTIONS

def ocr_document(data: bytes, filename: str) -> tuple[str, str, list[dict[str, Any]]]:
    """Return (text, engine). Falls back gracefully if no engine is installed."""
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            pages = []
            for page_number, page in enumerate(PdfReader(io.BytesIO(data)).pages, 1):
                page_text = page.extract_text() or ""
                pages.append({"page": page_number, "text": page_text, "blocks": []})
            txt = "\n".join(p["text"] for p in pages).strip()
            if txt: return txt, "pdf-text", pages
            return "", "pdf-scanned-unsupported", pages
        from PIL import Image, ImageOps
        import pytesseract
        img = ImageOps.autocontrast(ImageOps.grayscale(Image.open(io.BytesIO(data))))
        langs = "eng"
        try:
            have = pytesseract.get_languages(config="")
            langs = "+".join(l for l in ("eng", "hin") if l in have) or "eng"
        except Exception: pass
        data_rows = pytesseract.image_to_data(img, lang=langs, output_type=pytesseract.Output.DICT)
        blocks = []
        words = []
        for i, word in enumerate(data_rows.get("text", [])):
            word = (word or "").strip()
            if not word:
                continue
            words.append(word)
            blocks.append({"text": word, "bbox": [data_rows["left"][i], data_rows["top"][i],
                                                   data_rows["width"][i], data_rows["height"][i]],
                           "confidence": float(data_rows["conf"][i]) if str(data_rows["conf"][i]).strip() not in ("", "-1") else None})
        text = pytesseract.image_to_string(img, lang=langs)
        return text, f"tesseract({langs})", [{"page": 1, "text": text, "blocks": blocks}]
    except Exception as e:
        return "", f"ocr-unavailable:{type(e).__name__}", []


def ocr_bytes(data: bytes, filename: str) -> tuple[str, str]:
    text, engine, _ = ocr_document(data, filename)
    return text, engine

DATE_RE = [(r"\b(\d{4})-(\d{2})-(\d{2})\b", "%Y-%m-%d"), (r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", "%d-%m-%Y")]
def find_date(text: str) -> str | None:
    for rx, fmt in DATE_RE:
        m = re.search(rx, text)
        if m:
            try:
                s = "-".join(m.groups())
                return datetime.strptime(s, fmt.replace("/", "-")).strftime("%Y-%m-%d")
            except ValueError: continue
    return None

def classify(text: str) -> str:
    t = text.lower()
    if re.search(r"discharge|admission|admitted|hospital course", t): return "discharge_summary"
    if re.search(r"\brx\b|\btab\b|\bcap\b|\bsyp\b|\bbd\b|\btds\b|\bod\b|prescription", t) and not re.search(r"reference range|ref\.? range", t): return "prescription"
    if re.search(r"reference|g/dl|mg/dl|report|pathology|lab", t): return "lab_report"
    return "other"

def _fact_source(text: str, start: int, end: int, source: dict[str, Any] | None, confidence: float = 0.8) -> SourceSpan:
    source = source or {}
    page = source.get("page")
    bbox = None
    pages = source.get("pages") or []
    if page is None and pages:
        offset = 0
        for item in pages:
            page_text = item.get("text", "")
            if start < offset + len(page_text) + 1:
                page = item.get("page")
                for block in item.get("blocks", []):
                    if block.get("text") and block["text"].lower() in text[start:end].lower():
                        bbox = block.get("bbox")
                        confidence = (block.get("confidence") or confidence * 100) / 100
                        break
                break
            offset += len(page_text) + 1
    return SourceSpan(source_type="document", source_id=(source or {}).get("source_id", "ocr-text"),
                      page=page, start=start, end=end, bbox=bbox, confidence=confidence * 100, text=text[start:end])


def _status(segment: str) -> str:
    if re.search(r"\b(unknown|unsure|uncertain|maybe|possibly|not sure|cannot remember)\b", segment, re.I):
        return "uncertain"
    if re.search(r"\b(no|not|never|none|without|denies|denied)\b", segment, re.I):
        return "negated"
    return "reported"


def _normalise_unit(unit: str | None, fallback: str) -> str:
    value = (unit or "").strip().replace("µ", "u").replace("μ", "u")
    value = re.sub(r"\s+", "", value)
    value = value.replace("X10^3", "x10^3").replace("x10^3", "x10^3")
    aliases = {"g/dl": "g/dL", "mg/dl": "mg/dL", "mmhg": "mmHg", "mm/hr": "mm/hr",
               "uiu/ml": "uIU/mL", "iu/l": "IU/L", "u/l": "U/L", "x10^3/ul": "x10^3/uL",
               "/ul": "/uL"}
    return aliases.get(value.lower(), value) or fallback


def _explicit_reference(segment: str) -> tuple[float, float] | None:
    """Read a laboratory-supplied interval; never infer it from a lone value."""
    match = re.search(
        r"(?:ref(?:erence)?(?:\s+range|\s*\.?\s*range)?|normal(?:\s+range)?|range)"
        r"\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:[.,]\d+)?)",
        segment,
        re.I,
    )
    if not match:
        return None
    return float(match.group(1).replace(",", "")), float(match.group(2).replace(",", ""))


def _interpret(value: float, low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return "unable_to_interpret"
    return "below" if value < low else "above" if value > high else "within"


def extract(text: str, provenance: dict[str, Any] | None = None) -> dict:
    t = text or ""
    low = t.lower()
    meds, facts = [], []
    for d in DRUGS:
        for m in re.finditer(rf"(?:tab(?:let)?\.?|cap(?:sule)?\.?|syp\.?|inj\.?)?\s*\b{d}\b[^\n]{{0,40}}", low):
            seg = m.group(0)
            dose = re.search(r"(\d+(?:\.\d+)?\s?(?:mg|mcg|g|ml|iu|units?))", seg)
            freq = re.search(r"\b(od|bd|tds|qid|hs|1-0-1|1-1-1|0-0-1|1-0-0|once daily|twice daily|sos)\b", seg)
            status = _status(t[max(0, m.start()-30):m.end()])
            item = {"name": d.title(), "dose": dose.group(1) if dose else None, "frequency": freq.group(1).upper() if freq else None,
                    "status": status, "confidence": 0.75 if dose else 0.6,
                    "source": _fact_source(t, m.start(), m.end(), provenance, 0.75 if dose else 0.6).model_dump()}
            meds.append(item)
            facts.append(ExtractedFact(field="medication", value=item, status=status, confidence=item["confidence"],
                                       source=SourceSpan.model_validate(item["source"]), review_required=status != "reported"))
            break
    labs = []
    for name, (rx, unit, lo, hi) in LABS.items():
        m = re.search(
            rf"(?:{rx})[^\n\d]{{0,25}}([<>]?\s*\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)"
            rf"(?:\s*/\s*(\d+))?"
            rf"(?:\s*(mg/dL|g/dL|uIU/mL|IU/L|U/L|mmHg|mm/hr|%|x10\^?3/uL|/uL))?",
            low,
        )
        if not m: continue
        try: val = float(m.group(1).replace(",", "").replace("<", "").replace(">", "").strip())
        except ValueError: continue
        context = t[max(0, m.start() - 20):min(len(t), m.end() + 80)]
        explicit_ref = _explicit_reference(context)
        effective_low, effective_high = explicit_ref or (lo, hi)
        explicit_critical = bool(re.search(r"\bcritical(?:ly)?\b", context, re.I))
        flag = "critical" if explicit_critical else "low" if val < effective_low else "high" if val > effective_high else "normal"
        if name == "Systolic BP" and m.group(2) is None and val < 60: continue
        status = _status(t[max(0, m.start()-25):m.end()])
        item = {"test": name, "value": val, "unit": _normalise_unit(m.group(3), unit),
                "ref": f"{effective_low:g}–{effective_high:g}", "flag": flag,
                "interpretation": _interpret(val, effective_low, effective_high),
                "reference_source": "document" if explicit_ref else "configured_baseline",
                "status": status, "confidence": 0.8,
                "source": _fact_source(t, m.start(), m.end(), provenance).model_dump()}
        labs.append(item)
        facts.append(ExtractedFact(field="lab", value=item, status=status, source=SourceSpan.model_validate(item["source"]),
                                   review_required=status != "reported"))
    dx = sorted({d.replace("anemia", "anaemia") for d in DX if re.search(rf"\b{d}\b", low)})
    symptoms = [term for term in ("chest pain", "fever", "cough", "breathlessness", "headache", "vomiting", "rash")
                if re.search(rf"\b{re.escape(term)}\b", low)]
    allergies = re.findall(r"(?:allerg(?:y|ic)|allergic to)\s*[:\-]?\s*([A-Za-z][A-Za-z ]{1,40})", t, re.I)
    date = find_date(t)
    if date:
        date_match = re.search(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", t)
        date_source = _fact_source(t, date_match.start(), date_match.end(), provenance) if date_match else None
    else:
        date_source = None
    for value in symptoms:
        match = re.search(re.escape(value), t, re.I)
        if match:
            facts.append(ExtractedFact(field="symptom", value=value, status=_status(t[max(0, match.start()-25):match.end()]),
                                       source=_fact_source(t, match.start(), match.end(), provenance)))
    for value in allergies:
        match = re.search(re.escape(value), t, re.I)
        if match:
            facts.append(ExtractedFact(field="allergy", value=value.strip(), source=_fact_source(t, match.start(), match.end(), provenance),
                                       review_required=True))
    return {"schema_version": "clinical-facts-v1", "doc_type": classify(t), "date": date,
            "date_source": date_source.model_dump() if date_source else None,
            "medications": meds, "labs": labs, "diagnoses": dx, "symptoms": symptoms,
            "allergies": [a.strip() for a in allergies], "facts": [fact.model_dump() for fact in facts],
            "provenance": provenance or {"source_type": "document", "source_id": "ocr-text"},
            "review_flags": [fact.field for fact in facts if fact.review_required]}

def interactions(med_names: list[str]) -> list[str]:
    s = {m.lower() for m in med_names}
    return [msg for pair, msg in _reference_interactions() if pair <= s]

def abnormal(labs: list[dict]) -> list[str]:
    return [f"{l['test']} {l['value']} {l['unit']} ({l['flag']}, ref {l['ref']})" for l in labs if l["flag"] != "normal"]
