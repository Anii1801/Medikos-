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

LABS = {  # name: (aliases regex, baseline unit, baseline low, baseline high); None bounds = never interpret without a printed interval
 "Haemoglobin": (r"h(?:a)?emoglobin|\bhb\b|\bhgb\b", "g/dL", 12.0, 17.0),
 "Fasting glucose": (r"fasting (?:blood )?(?:glucose|sugar)|\bfbs\b|\bfbg\b", "mg/dL", 70, 100),
 "Post-prandial glucose": (r"post[- ]?prandial(?: blood)?(?: sugar| glucose)?|\bppbs\b|\bppg\b", "mg/dL", 70, 140),
 "HbA1c": (r"hba[1li]c|glycosylated|glycated", "%", 4.0, 5.6),
 "Creatinine": (r"creatinine", "mg/dL", 0.6, 1.3),
 "Urea": (r"\burea\b|\bbun\b", "mg/dL", 15, 45),
 "TSH": (r"\btsh\b", "uIU/mL", 0.4, 4.5),
 "WBC": (r"\bwbc\b|total leu[ck]ocyte|\btlc\b", "/uL", 4000, 11000),
 "Platelets": (r"platelet|\bplt\b", "/uL", 150000, 450000),
 "Total cholesterol": (r"total cholesterol|\bcholesterol\b", "mg/dL", 0, 200),
 "LDL": (r"\bldl\b", "mg/dL", 0, 100),
 "SGPT (ALT)": (r"sgpt|\balt\b", "U/L", 7, 56),
 "Systolic BP": (r"\bbp\b|blood pressure", "mmHg", 90, 130),
 "ESR": (r"\besr\b|erythrocyte sedimentation", "mm/hr", None, None),
 "CRP": (r"\bcrp\b|c[- ]reactive protein", "mg/L", None, None),
 "Uric Acid": (r"uric acid", "mg/dL", None, None),
 "Triglycerides": (r"triglycerides?|\btg\b", "mg/dL", None, None),
 "Troponin I": (r"troponin[- ]?i\b|\bctn[- ]?i\b", "ng/mL", None, None),
}
_UNIT_RX = (r"x?10\^?3\s*/\s*u?l|x?10\^?9\s*/\s*l|lakhs?\s*/\s*cu\.?\s*mm|/\s*cu\.?\s*mm|/\s*u?l|mg\s*/\s*d?l|g\s*/\s*d?l|"
            r"u?iu\s*/\s*m?l|u\s*/\s*l|ng\s*/\s*m?l|mmhg|mm\s*/\s*h(?:r)?|%")
_PRINTED_FLAG = {"n": "N", "normal": "N", "h": "H", "high": "H", "l": "L", "low": "L", "hh": "HH", "ll": "LL",
                 "critical": "CRITICAL", "crit": "CRITICAL", "*": "ABNORMAL", "abnormal": "ABNORMAL"}
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

MAX_PDF_PAGES = 20          # cap on PDF pages and multi-frame raster images (bounds OCR work per upload)


def _ocr_pil_image(image) -> tuple[str, str, list[dict[str, Any]]]:
    """Tesseract on one Pillow image -> (text, engine, word blocks with bbox and confidence)."""
    from PIL import ImageOps
    import pytesseract
    img = ImageOps.autocontrast(ImageOps.grayscale(image.convert("RGB")))
    langs = "eng"
    try:
        have = pytesseract.get_languages(config="")
        langs = "+".join(l for l in ("eng", "hin") if l in have) or "eng"
    except Exception: pass
    # --psm 6 keeps each printed ROW together. Tesseract's default layout analysis reads a results table as separate
    # columns (names / values / intervals), which detaches a value from its test name.
    cfg = "--psm 6 -c preserve_interword_spaces=1"
    rows = pytesseract.image_to_data(img, lang=langs, config=cfg, output_type=pytesseract.Output.DICT)
    blocks = []
    for i, word in enumerate(rows.get("text", [])):
        word = (word or "").strip()
        if not word:
            continue
        blocks.append({"text": word, "bbox": [rows["left"][i], rows["top"][i], rows["width"][i], rows["height"][i]],
                       "confidence": float(rows["conf"][i]) if str(rows["conf"][i]).strip() not in ("", "-1") else None})
    return pytesseract.image_to_string(img, lang=langs, config=cfg), f"tesseract({langs})", blocks


def _ocr_image(data: bytes) -> tuple[str, str, list[dict[str, Any]]]:
    """Tesseract on one raster image -> (text, engine, word blocks with bbox and confidence)."""
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        return _ocr_pil_image(image)


def ocr_document(data: bytes, filename: str) -> tuple[str, str, list[dict[str, Any]]]:
    """Return (text, engine, pages). A PDF with a text layer is read directly; a scanned PDF (image-only pages) is
    OCR'd page by page from its embedded images. TIFF and animated WebP frames retain page provenance; unavailable OCR
    returns an explicit engine status."""
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages, used_ocr = [], False
            for page_number, page in enumerate(reader.pages, 1):
                if page_number > MAX_PDF_PAGES:
                    pages.append({"page": page_number, "text": "", "blocks": [], "skipped": "page limit"})
                    continue
                page_text = (page.extract_text() or "").strip()
                blocks: list[dict[str, Any]] = []
                if not page_text:
                    parts = []
                    for image in page.images:
                        try:
                            text, _, blk = _ocr_image(image.data)
                        except Exception:
                            continue
                        parts.append(text); blocks += blk
                    page_text, used_ocr = "\n".join(parts).strip(), used_ocr or bool(parts)
                pages.append({"page": page_number, "text": page_text, "blocks": blocks})
            txt = "\n".join(p["text"] for p in pages).strip()
            if txt:
                return txt, ("pdf-scanned-ocr(tesseract)" if used_ocr else "pdf-text"), pages
            return "", "pdf-scanned-unsupported", pages
        if name.endswith((".tif", ".tiff", ".webp")):
            from PIL import Image
            pages, engines = [], []
            with Image.open(io.BytesIO(data)) as image:
                frame_count = min(getattr(image, "n_frames", 1), MAX_PDF_PAGES)
                for frame_number in range(frame_count):
                    image.seek(frame_number)
                    text, engine, blocks = _ocr_pil_image(image.copy())
                    pages.append({"page": frame_number + 1, "text": text, "blocks": blocks})
                    engines.append(engine)
                if getattr(image, "n_frames", 1) > MAX_PDF_PAGES:
                    pages.append({"page": MAX_PDF_PAGES + 1, "text": "", "blocks": [], "skipped": "frame limit"})
            text = "\n".join(page["text"] for page in pages if not page.get("skipped")).strip()
            engine = engines[0] if engines and len(set(engines)) == 1 else "tesseract(mixed)" if engines else "ocr-unavailable"
            return text, engine, pages
        text, engine, blocks = _ocr_image(data)
        return text, engine, [{"page": 1, "text": text, "blocks": blocks}]
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
    value = re.sub(r"\s+", "", (unit or "").replace("µ", "u").replace("μ", "u")).lower().replace("^", "")
    aliases = {"g/dl": "g/dL", "mg/dl": "mg/dL", "mmhg": "mmHg", "mm/hr": "mm/hr", "mm/h": "mm/hr", "uiu/ml": "uIU/mL",
               "iu/l": "IU/L", "u/l": "U/L", "x103/ul": "x10^3/uL", "103/ul": "x10^3/uL", "x109/l": "x10^9/L", "109/l": "x10^9/L",
               "/ul": "/uL", "/l": "/L", "mg/l": "mg/L", "ng/ml": "ng/mL", "%": "%", "/cumm": "/cumm", "lakh/cumm": "lakh/cumm",
               "lakhs/cumm": "lakh/cumm", "/cu.mm": "/cumm", "lakh/cu.mm": "lakh/cumm"}
    return aliases.get(value, value) or fallback


def _printed_interval(tail: str) -> tuple[float | None, float | None] | None:
    """Reference interval printed on the report right after the value/unit: '(13-17)', '(<5.0)', 'ref 12-16', 'normal: 4–11'.
    Returns (low, high); one bound may be None for '<x' / '>x'. Never inferred from the value itself."""
    t = tail[:70]
    num = r"(\d+(?:[.,]\d+)?)"
    m = (re.search(rf"(?:ref(?:erence)?(?:\s+range|\s*\.?\s*range)?|normal(?:\s+range)?|range)\s*[:=]?\s*\(?\s*{num}\s*(?:-|–|—|to)\s*{num}", t, re.I)
         or re.search(rf"\(\s*{num}\s*(?:-|–|—|to)\s*{num}\s*\)", t))
    if m:
        lo, hi = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
        return (lo, hi) if lo <= hi else None
    m = re.search(rf"(?:ref(?:erence)?|normal|range)?\s*[:=]?\s*\(?\s*(<|>|≤|≥)\s*{num}\s*\)?", t, re.I)
    if m:
        v = float(m.group(2).replace(",", "."))
        return (None, v) if m.group(1) in ("<", "≤") else (v, None)
    return None


def _explicit_reference(segment: str) -> tuple[float, float] | None:
    """Back-compat wrapper: a fully two-sided interval printed on the report, else None."""
    r = _printed_interval(segment)
    return r if r and r[0] is not None and r[1] is not None else None


def _interpret(value: float, low: float | None, high: float | None) -> str:
    if low is None and high is None:
        return "unable_to_interpret"
    if low is not None and value < low:
        return "below"
    if high is not None and value > high:
        return "above"
    return "within"


def _lab_item(text: str, match: re.Match, name: str, baseline_unit: str,
              low: float | None, high: float | None, provenance: dict[str, Any] | None) -> dict | None:
    try:
        value = float(match.group(1).replace(",", "").replace("<", "").replace(">", "").strip())
    except ValueError:
        return None
    if name == "Systolic BP" and match.group(2) is None and value < 60:
        return None

    line_end = text.find("\n", match.end())
    line_start = text.rfind("\n", 0, match.start()) + 1
    line = text[line_start: line_end if line_end != -1 else len(text)]
    prefix = text[line_start:match.start(1)].lower()
    if re.search(r"\b(?:ref(?:erence)?(?:\s+range|\s*\.?\s*range)?|normal(?:\s+range)?|range)\s*[:=]?\s*$", prefix):
        return None

    tail = text[match.end(): line_end if line_end != -1 else len(text)]
    printed = _printed_interval(tail)
    printed_unit = _normalise_unit(match.group(3), "") if match.group(3) else ""
    flag_m = re.search(r"(?:\)|\s)\s*(HH|LL|H|L|N|High|Low|Normal|Critical|Abnormal|\*)\s*$",
                       tail.strip(), re.I) if tail.strip() else None
    printed_flag = _PRINTED_FLAG.get(flag_m.group(1).lower()) if flag_m else None
    ambiguity: list[str] = []
    if printed is not None:
        effective_low, effective_high = printed
        ref_source = "document"
        if not printed_unit:
            ambiguity.append("unit not printed next to the value; the printed interval is used as given")
    elif not printed_unit:
        ref_source = "unavailable"
        effective_low = effective_high = None
        ambiguity.append("unit and reference interval are not printed; no comparison was made")
    else:
        ref_source = "configured_baseline"
        effective_low, effective_high = low, high
        if low is None and high is None:
            ambiguity.append("no reference interval printed and no baseline configured")
        elif printed_unit != baseline_unit:
            effective_low = effective_high = None
            ambiguity.append(f"unit '{printed_unit}' differs from baseline unit '{baseline_unit}'; not compared")
        else:
            ambiguity.append("no legible reference interval on the report; generic configured baseline used - confirm against the original")

    explicit_critical = bool(re.search(r"\bcritical(?:ly)?\b", line, re.I)) or printed_flag in ("CRITICAL", "HH", "LL")
    interpretation = _interpret(value, effective_low, effective_high)
    if explicit_critical:
        flag = "critical"
    elif interpretation == "unable_to_interpret":
        flag = "unable_to_interpret"
    else:
        flag = {"below": "low", "above": "high", "within": "normal"}[interpretation]
    computed = {"low": "L", "high": "H", "normal": "N"}.get(flag)
    if printed_flag in ("N", "H", "L") and computed and computed != printed_flag:
        ambiguity.append(f"printed flag '{printed_flag}' disagrees with comparison against the interval ({computed}); confirm")
    status = _status(text[max(0, match.start()-25):match.end()])
    source = _fact_source(text, match.start(), match.end(), provenance).model_dump()
    return {
        "test": name, "value": value, "unit": printed_unit or None,
        "measurement_date": find_date(line),
        "ref": (f"{effective_low:g}–{effective_high:g}" if effective_low is not None and effective_high is not None
                else f"<{effective_high:g}" if effective_high is not None else f">{effective_low:g}" if effective_low is not None else None),
        "ref_low": effective_low, "ref_high": effective_high, "flag": flag, "printed_flag": printed_flag,
        "interpretation": interpretation if flag != "unable_to_interpret" else "unable_to_interpret",
        "reference_source": ref_source, "ambiguity": ambiguity,
        "status": status, "confidence": 0.9 if (ref_source == "document" and printed_unit and not ambiguity) else 0.7,
        "source": source,
    }


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
        matches = re.finditer(
            rf"(?:{rx})[^\n\d(]{{0,40}}([<>]?\s*\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)"
            rf"(?:\s*/\s*(\d+))?"
            rf"(?:[ \t]*({_UNIT_RX}))?",
            low,
        )
        for match in matches:
            item = _lab_item(t, match, name, unit, lo, hi, provenance)
            if item is None:
                continue
            labs.append(item)
            facts.append(ExtractedFact(field="lab", value=item, status=item["status"], confidence=item["confidence"],
                                       source=SourceSpan.model_validate(item["source"]),
                                       review_required=item["status"] != "reported" or bool(item["ambiguity"])))
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
    """Results outside the interval used for comparison. Results that could not be interpreted are not listed here
    (they appear, with the reason, under Laboratory and Investigation Findings)."""
    return [f"{l['test']} {l['value']} {l['unit']} ({l['flag']}, ref {l['ref']})" for l in labs
            if l["flag"] not in ("normal", "unable_to_interpret")]
