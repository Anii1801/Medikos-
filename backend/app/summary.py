"""Structured physician-ready, source-linked summary generator."""
import re
from . import ocr

def _l(v):
    if isinstance(v, list): return ", ".join(x for x in v if x != "None") or "None reported"
    return v or "Not reported"

def _patient_ref(field: str) -> dict:
    return {"source_type": "patient_message", "source_id": field, "field": field}

def _doc_refs(docs: list[dict]) -> list[dict]:
    return [{"source_type": "document", "source_id": d.get("id"), "document_id": d.get("id"),
             "filename": d.get("filename"), "date": d.get("date"), "engine": d.get("engine"),
             "processing_status": d.get("processing_status", "needs_review")} for d in docs]


def _laboratory_findings(docs: list[dict]) -> list[dict]:
    findings = []
    for document in docs:
        entities = document.get("entities") or {}
        for lab in entities.get("labs", []):
            source = lab.get("source") or {}
            flag = lab.get("flag")
            status = {
                "low": "below_reference_interval",
                "high": "above_reference_interval",
                "normal": "within_reference_interval",
                "critical": "critical_result",
            }.get(flag, "unable_to_interpret")
            uncertainty = []
            if lab.get("reference_source") == "configured_baseline":
                uncertainty.append("The report did not provide a reference interval; configured baseline used.")
            elif lab.get("reference_source") == "unavailable":
                uncertainty.append("No reference interval was available for comparison.")
            uncertainty += [str(x) for x in lab.get("ambiguity") or []]
            if lab.get("status") != "reported":
                uncertainty.append(f"Extraction status: {lab.get('status')}.")
            if lab.get("confidence", 1) < 0.8:
                uncertainty.append("Extraction confidence is below the review threshold.")
            if not source.get("source_type") or source.get("start") is None or source.get("end") is None:
                uncertainty.append("Source span provenance is missing; verify the value against the original.")
            explanation = {
                "below_reference_interval": "The value is below the supplied comparison interval.",
                "above_reference_interval": "The value is above the supplied comparison interval.",
                "within_reference_interval": "The value is within the supplied comparison interval; this is not a clearance.",
                "critical_result": "The report marks this result as critical; urgent clinician review is needed.",
                "unable_to_interpret": "The result cannot be interpreted without a valid reference interval.",
            }[status]
            extracted_date = entities.get("date")
            document_date = document.get("date")
            if extracted_date and document_date and extracted_date != document_date:
                uncertainty.append("The entered document date differs from the date extracted from its text.")
            findings.append({
                "test_name": lab.get("test"),
                "result": lab.get("value"),
                "unit": lab.get("unit"),
                "reference_interval": lab.get("ref"),
                "reference_source": lab.get("reference_source"),
                "printed_flag": lab.get("printed_flag"),
                "status": status,
                "report_date": lab.get("measurement_date") or extracted_date or document_date,
                "measurement_date": lab.get("measurement_date"),
                "entered_document_date": document_date,
                "extracted_report_date": extracted_date,
                "date_conflict": bool(extracted_date and document_date and extracted_date != document_date),
                "source_document": document.get("filename"),
                "source_document_id": document.get("id"),
                "source": source,
                "explanation": explanation,
                "uncertainty": uncertainty,
                "clinician_review_status": "pending",
            })
    return findings


def build_sections(user: dict, a: dict, docs: list[dict]) -> list[dict]:
    S = []
    S.append({"title": "Patient", "text": f"{user.get('name') or 'Unnamed'}, {user.get('age') or 'age not reported'}" + (f" · ABHA {user['abha']}" if user.get("abha") else ""), "source_refs": []})
    cc = (a.get("cc_text") or "Other (details not reported)") if a.get("cc") == "Other" else (a.get("cc") or a.get("cc_text"))
    complaint_parts = [str(cc).strip()] if cc else []
    if a.get("dur"):
        complaint_parts.append(f"Duration: {a['dur']}")
    if a.get("sev"):
        complaint_parts.append(f"Severity: {a['sev']}")
    if complaint_parts:
        S.append({"title": "Chief complaint", "text": "; ".join(complaint_parts),
                  "source_refs": [_patient_ref(k) for k in ("cc", "cc_text", "dur", "sev") if a.get(k)]})
    hpi = []
    if a.get("cc") == "Chest pain":
        labels = (("cp_site", "Site"), ("cp_char", "Character"), ("cp_rad", "Radiation"),
                  ("cp_agg", "Exacerbating/relieving factors"))
        hpi.extend(f"{label}: {_l(a[key])}" for key, label in labels if a.get(key))
    for k, lab in [("progression", "Progression"), ("hpi_char", "Character"), ("hpi_mod", "Aggravating/relieving factors"), ("fv_pat", "Fever pattern"), ("fv_exp", "Fever associations"), ("co_type", "Cough"), ("co_night", "Respiratory features"),
                   ("st_loc", "Abdominal site"), ("st_rel", "Abdominal features"), ("ha_type", "Headache"), ("ha_assoc", "Headache features"),
                   ("jt_site", "Joints/areas"), ("jt_stiff", "Morning stiffness")]:
        if k in a: hpi.append(f"{lab}: {_l(a[k])}.")
    if hpi: S.append({"title": "History of present illness", "text": " ".join(hpi),
                      "source_refs": [_patient_ref(k) for k in a if k in a and (k == "progression" or k.startswith(("cp_", "fv_", "co_", "st_", "ha_", "jt_", "hpi_")))]})
    if a.get("assoc"):
        S.append({"title": "Important positive and negative findings", "text": _l(a["assoc"]),
                  "source_refs": [_patient_ref("assoc")]})
    histories = [(k, label) for k, label in (("pmh", "Medical/surgical"), ("fam", "Family"),
                ("pers", "Personal"), ("ros", "Review of systems")) if a.get(k)]
    if histories:
        S.append({"title": "Relevant history", "text": "; ".join(f"{label}: {_l(a[k])}" for k, label in histories),
                  "source_refs": [_patient_ref(k) for k, _ in histories]})
    declared = (a.get("meds") or "").strip()
    document_medication_findings = []
    medication_document_refs = []
    for document in docs:
        entities = document.get("entities") or {}
        has_medication_finding = False
        medication_facts = []
        for fact in entities.get("facts") or []:
            if fact.get("field") not in ("medication", "allergy"):
                continue
            has_medication_finding = True
            medication_facts.append(fact)
        if not medication_facts:
            medication_facts = [
                {"field": "medication", "value": item, "status": item.get("status", "uncertain"),
                 "source": item.get("source") or {}}
                for item in entities.get("medications") or []
            ]
            medication_facts += [
                {"field": "allergy", "value": item, "status": "reported", "source": {}}
                for item in entities.get("allergies") or []
            ]
            has_medication_finding = bool(medication_facts)
        for fact in medication_facts:
            source = fact.get("source") or {}
            source_present = bool(source.get("source_type") and source.get("start") is not None and source.get("end") is not None)
            extracted_date = entities.get("date")
            document_date = document.get("date")
            document_medication_findings.append({
                "field": fact.get("field"),
                "value": fact.get("value"),
                "status": fact.get("status", "uncertain"),
                "source": source,
                "source_document": document.get("filename"),
                "source_document_id": document.get("id"),
                "report_date": extracted_date or document_date,
                "entered_document_date": document_date,
                "date_conflict": bool(extracted_date and document_date and extracted_date != document_date),
                "verification_status": "unverified_document_extraction" if source_present else "missing_provenance_needs_review",
            })
        if has_medication_finding:
            medication_document_refs.append(document)
    drug_history = []
    if declared:
        drug_history.append(f"Medicines (patient-reported): {declared}")
    if a.get("allergy"):
        drug_history.append(f"Allergy (patient-reported): {_l(a['allergy'])}")
    if document_medication_findings:
        drug_history.append("Document-derived medication/allergy details require confirmation against the source.")
    if drug_history or document_medication_findings:
        S.append({"title": "Current medications and allergies", "text": "; ".join(drug_history),
                  "findings": document_medication_findings,
                  "source_refs": ([_patient_ref(k) for k in ("meds", "allergy") if a.get(k)]
                                  + _doc_refs(medication_document_refs)),
                  "review_flags": ["clinician_confirmation_required"] if document_medication_findings else []})
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
            bits = [e.get("doc_type", "other").replace("_", " ")]
            if d.get("processing_status", "needs_review") != "extracted":
                bits.append("extraction status: " + d.get("processing_status", "needs_review"))
                review_flags.append("document_extraction_requires_review")
            diagnoses = e.get("diagnoses") or []
            document_meds = e.get("medications") or []
            if diagnoses: bits.append("Dx: " + ", ".join(diagnoses))
            if document_meds: bits.append("Rx: " + ", ".join(f"{m['name']} {m.get('dose') or ''} {m.get('frequency') or ''}".strip() for m in document_meds))
            lines.append(f"{d.get('date') or 'undated'} — " + "; ".join(bits))
            labs += e.get("labs") or []
            meds += [m["name"] for m in document_meds]
            review_flags += e.get("review_flags", [])
        S.append({"title": "Prior records (timeline)", "text": "\n".join(lines), "source_refs": refs,
                  "review_flags": sorted(set(review_flags))})
        ab = ocr.abnormal(labs)
        if ab:
            S.append({"title": "Values outside comparison intervals (not a diagnosis)", "text": "\n".join(ab),
                      "source_refs": refs, "review_flags": ["verify_against_original_report"]})
        lab_findings = _laboratory_findings(ds)
        if lab_findings:
            S.append({
                "title": "Laboratory and Investigation Findings",
                "text": "Document-extracted measurements; comparison intervals do not establish a diagnosis.",
                "findings": lab_findings,
                "source_refs": refs,
                "review_flags": ["clinician_confirmation_required"],
            })
        doc_facts = []
        for document in ds:
            entities = document.get("entities") or {}
            facts = entities.get("facts") or []
            for fact in facts:
                if fact.get("field") in ("lab", "medication", "allergy"):
                    continue
                source = fact.get("source") or {}
                extracted_date = entities.get("date")
                document_date = document.get("date")
                doc_facts.append({
                    "field": fact.get("field", "unknown"),
                    "value": fact.get("value"),
                    "status": fact.get("status", "uncertain"),
                    "source": source,
                    "source_document": document.get("filename"),
                    "source_document_id": document.get("id"),
                    "report_date": extracted_date or document_date,
                    "entered_document_date": document_date,
                    "date_conflict": bool(extracted_date and document_date and extracted_date != document_date),
                    "verification_status": ("unverified_document_extraction" if source.get("source_type")
                                             and source.get("start") is not None and source.get("end") is not None
                                             else "missing_provenance_needs_review"),
                })
        if doc_facts:
            S.append({"title": "Other document-derived findings",
                      "text": "Unverified extraction; confirm each item against its source document.",
                      "findings": doc_facts, "source_refs": refs,
                      "review_flags": ["clinician_confirmation_required"]})
        verification_findings = lab_findings + document_medication_findings + doc_facts
        for document in ds:
            entities = document.get("entities") or {}
            if document.get("processing_status", "needs_review") != "extracted" or not entities.get("facts"):
                verification_findings.append({
                    "field": "document extraction",
                    "value": document.get("processing_error") or document.get("processing_status") or "No extracted findings",
                    "status": "needs_review",
                    "source": {},
                    "source_document": document.get("filename"),
                    "source_document_id": document.get("id"),
                    "verification_status": "manual_source_review_required",
                })
        if verification_findings:
            S.append({"title": "Items requiring clinician verification",
                      "text": "Document-derived information is unverified; compare each item with its source.",
                      "findings": verification_findings, "source_refs": refs,
                      "review_flags": ["clinician_confirmation_required"]})
        conflict_details = []
        patient_medications = {x.strip().split()[0].lower() for x in re.split(r"[,;\n]", declared) if x.strip()}
        documented = {m["name"].lower(): m for d in ds for m in d["entities"].get("medications", [])}
        dose_conflicts = [f"{name}: patient reports '{declared}', document reports {m.get('dose') or 'dose not stated'}"
                          for name, m in documented.items() if name in patient_medications and m.get("dose") and
                          not re.search(re.escape(m["dose"]), declared, re.I)]
        if dose_conflicts:
            conflict_details.extend(dose_conflicts)
        grouped_labs = {}
        for finding in lab_findings:
            key = (finding["test_name"], finding["report_date"])
            grouped_labs.setdefault(key, []).append(finding)
        for (test_name, report_date), measures in grouped_labs.items():
            values = {(measure["result"], measure["unit"]) for measure in measures}
            if len(values) > 1:
                when = f" on {report_date}" if report_date else " with no measurement date"
                reported = ", ".join(f"{value} {unit or '(unit not reported)'}" for value, unit in sorted(values, key=str))
                conflict_details.append(f"{test_name}{when}: multiple differing document measurements ({reported}); clinician to reconcile.")
        if conflict_details:
            flags = ["conflicting_medication_information"] if dose_conflicts else []
            if any("measurements" in detail for detail in conflict_details):
                flags.append("conflicting_laboratory_measurements")
            S.append({"title": "Conflicts requiring review", "text": "\n".join(conflict_details),
                      "source_refs": refs + ([_patient_ref("meds")] if dose_conflicts else []),
                      "review_flags": flags or ["conflicting_clinical_information"]})
    all_meds = meds if ds else []
    all_meds = all_meds + [m for m in ocr.DRUGS if m in declared.lower()]
    ix = ocr.interactions(all_meds)
    if ix: S.append({"title": "Possible drug interactions (verify)", "text": "\n".join(ix)})
    if a.get("free"):
        S.append({"title": "Patient's own words", "text": a["free"],
                  "source_refs": [_patient_ref("free")]})
    return S

def patient_confirmation(a: dict, lang: str) -> str:
    cc = a.get("cc_text") or a.get("cc") or ""
    if lang == "hi":
        return f"आपने बताया: मुख्य समस्या — {cc}। यह जानकारी आपके डॉक्टर तक पहुँचा दी गई है। कृपया अपनी बारी का इंतज़ार करें।"
    return f"You told us your main problem is: {cc}. This has been sent to your doctor. Please wait for your turn."
