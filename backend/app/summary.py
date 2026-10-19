"""Structured physician-ready, source-linked summary generator."""
import re
from . import ocr

def _l(v):
    if isinstance(v, list): return ", ".join(x for x in v if x != "None") or "None reported"
    return v or "Not reported"

def _patient_ref(field: str) -> dict:
    return {"source_type": "patient_message", "source_id": field, "field": field}

def _doc_refs(docs: list[dict]) -> list[dict]:
    return [{"source_type": "document", "source_id": d.get("id"), "filename": d.get("filename"),
             "date": d.get("date"), "engine": d.get("engine")} for d in docs]

def build_sections(user: dict, a: dict, docs: list[dict]) -> list[dict]:
    S = []
    S.append({"title": "Patient", "text": f"{user.get('name') or 'Unnamed'}, {user.get('age') or 'age not reported'}" + (f" · ABHA {user['abha']}" if user.get("abha") else ""), "source_refs": []})
    cc = a.get("cc_text") if a.get("cc") == "Other" else a.get("cc")
    S.append({"title": "Chief complaint", "text": f"{cc or 'Not reported'} for {a.get('dur', 'Not reported').lower()}; severity {a.get('sev', 'Not reported').lower()}.",
              "source_refs": [_patient_ref(k) for k in ("cc", "cc_text", "dur", "sev") if a.get(k)]})
    hpi = []
    if a.get("cc") == "Chest pain":
        hpi.append(f"SOCRATES — Site: {a.get('cp_site','Not reported')}. Character: {a.get('cp_char','Not reported')}. Radiation: {a.get('cp_rad','Not reported')}. Exacerbating/relieving: {a.get('cp_agg','Not reported')}. Onset/time: {a.get('dur','Not reported')}. Severity: {a.get('sev','Not reported')}.")
    for k, lab in [("progression", "Progression"), ("fv_pat", "Fever pattern"), ("fv_exp", "Fever associations"), ("co_type", "Cough"), ("co_night", "Respiratory features"),
                   ("st_loc", "Abdominal site"), ("st_rel", "Abdominal features"), ("ha_type", "Headache"), ("ha_assoc", "Headache features"),
                   ("jt_site", "Joints/areas"), ("jt_stiff", "Morning stiffness")]:
        if k in a: hpi.append(f"{lab}: {_l(a[k])}.")
    if hpi: S.append({"title": "History of present illness", "text": " ".join(hpi),
                      "source_refs": [_patient_ref(k) for k in a if k in a and (k == "progression" or k.startswith(("cp_", "fv_", "co_", "st_", "ha_", "jt_")))]})
    S += [{"title": "Associated symptoms", "text": _l(a.get("assoc")), "source_refs": [_patient_ref("assoc")]},
          {"title": "Past medical / surgical", "text": _l(a.get("pmh")), "source_refs": [_patient_ref("pmh")]}]
    declared = (a.get("meds") or "").strip()
    S.append({"title": "Drug history & allergy", "text": f"Medicines (patient-reported): {declared or 'Not reported'}. Allergy: {a.get('allergy') or 'Not reported'}.",
              "source_refs": [_patient_ref(k) for k in ("meds", "allergy") if a.get(k)]})
    S += [{"title": "Family history", "text": _l(a.get("fam"))}, {"title": "Personal history", "text": _l(a.get("pers"))},
          {"title": "Review of systems", "text": _l(a.get("ros")), "source_refs": [_patient_ref("ros")]}]
    if a.get("_ay"):
        pairs = [("Prakriti", "ay_prak"), ("Vikriti", "ay_vik"), ("Sara", "ay_sara"), ("Samhanana", "ay_sam"), ("Pramana", "ay_pram"),
                 ("Satmya", "ay_sat"), ("Sattva", "ay_sattva"), ("Agni/Koshtha", "ay_agni"), ("Ahara/Vyayama Shakti", "ay_ahar"), ("Ahara-Vihara", "ay_vihara")]
        S.append({"title": "Dashavidha Pariksha (patient-reported)", "text": "; ".join(f"{n}: {a.get(k,'Not reported')}" for n, k in pairs)})
    # documents → timeline, labs, meds, interactions
    ds = sorted(docs, key=lambda d: d.get("date") or "9999")
    if ds:
        lines, labs, meds = [], [], []
        refs = _doc_refs(ds)
        review_flags = []
        for d in ds:
            e = d["entities"]
            bits = [e["doc_type"].replace("_", " ")]
            if e["diagnoses"]: bits.append("Dx: " + ", ".join(e["diagnoses"]))
            if e["medications"]: bits.append("Rx: " + ", ".join(f"{m['name']} {m['dose'] or ''} {m['frequency'] or ''}".strip() for m in e["medications"]))
            lines.append(f"{d.get('date') or 'undated'} — " + "; ".join(bits))
            labs += e["labs"]; meds += [m["name"] for m in e["medications"]]
            review_flags += e.get("review_flags", [])
        S.append({"title": "Prior records (timeline)", "text": "\n".join(lines), "source_refs": refs,
                  "review_flags": sorted(set(review_flags))})
        ab = ocr.abnormal(labs)
        S.append({"title": "Abnormal values (prior reports)", "text": "\n".join(ab) or "None detected",
                  "source_refs": refs, "review_flags": ["verify_against_original_report"] if ab else []})
        patient_medications = {x.strip().split()[0].lower() for x in re.split(r"[,;\n]", declared) if x.strip()}
        documented = {m["name"].lower(): m for d in ds for m in d["entities"].get("medications", [])}
        dose_conflicts = [f"{name}: patient reports '{declared}', document reports {m.get('dose') or 'dose not stated'}"
                          for name, m in documented.items() if name in patient_medications and m.get("dose") and
                          not re.search(re.escape(m["dose"]), declared, re.I)]
        if dose_conflicts:
            S.append({"title": "Conflicts requiring review", "text": "\n".join(dose_conflicts),
                      "source_refs": refs + [_patient_ref("meds")], "review_flags": ["conflicting_medication_information"]})
    all_meds = meds if ds else []
    all_meds = all_meds + [m for m in ocr.DRUGS if m in declared.lower()]
    ix = ocr.interactions(all_meds)
    if ix: S.append({"title": "Possible drug interactions (verify)", "text": "\n".join(ix)})
    S.append({"title": "Patient's own words", "text": a.get("free") or "—",
              "source_refs": [_patient_ref("free")] if a.get("free") else []})
    return S

def patient_confirmation(a: dict, lang: str) -> str:
    cc = a.get("cc_text") or a.get("cc") or ""
    if lang == "hi":
        return f"आपने बताया: मुख्य समस्या — {cc}। यह जानकारी आपके डॉक्टर तक पहुँचा दी गई है। कृपया अपनी बारी का इंतज़ार करें।"
    return f"You told us your main problem is: {cc}. This has been sent to your doctor. Please wait for your turn."
