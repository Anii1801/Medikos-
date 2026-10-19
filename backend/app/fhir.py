"""FHIR R4 bundle builder + ABDM adapter (mock by default)."""
import os, uuid, time
from datetime import datetime, timezone

ABHA_SYSTEM = "https://healthid.ndhm.gov.in"

def build_bundle(user: dict, sections: list[dict], flags: list[dict], docs: list[dict], record_id: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    pid = f"patient-{user['id']}"
    ents = [{"fullUrl": f"urn:uuid:{pid}", "resource": {"resourceType": "Patient", "id": pid, "name": [{"text": user.get("name") or ""}],
            "identifier": ([{"system": ABHA_SYSTEM, "value": user["abha"]}] if user.get("abha") else [])}}]
    comp = {"resourceType": "Composition", "id": f"comp-{record_id}", "status": "preliminary",
            "type": {"text": "Patient-reported clinical history (draft for physician review)"},
            "subject": {"reference": f"Patient/{pid}"}, "date": now, "title": "Clinical history intake",
            "author": [{"display": "MediKiosk (AI-assisted intake)"}],
            "section": [{"title": s["title"], "text": {"status": "generated", "div": "<div>" + s["text"].replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br/>") + "</div>"}} for s in sections]}
    ents.append({"resource": comp})
    for d in docs:
        for l in d["entities"]["labs"]:
            ents.append({"resource": {"resourceType": "Observation", "id": uuid.uuid4().hex, "status": "preliminary", "code": {"text": l["test"]},
                         "subject": {"reference": f"Patient/{pid}"}, "effectiveDateTime": d.get("date"),
                         "valueQuantity": {"value": l["value"], "unit": l["unit"]},
                         "interpretation": [{"text": l["flag"]}]}})
        for m in d["entities"]["medications"]:
            ents.append({"resource": {"resourceType": "MedicationStatement", "id": uuid.uuid4().hex, "status": "unknown",
                         "medicationCodeableConcept": {"text": m["name"]}, "subject": {"reference": f"Patient/{pid}"},
                         "dosage": [{"text": f"{m['dose'] or ''} {m['frequency'] or ''}".strip()}]}})
    for f in flags:
        ents.append({"resource": {"resourceType": "Flag", "id": uuid.uuid4().hex, "status": "active", "code": {"text": f["msg"]}, "subject": {"reference": f"Patient/{pid}"}}})
    return {"resourceType": "Bundle", "type": "document", "timestamp": now, "entry": ents}

def abdm_push(bundle: dict, abha: str | None) -> dict:
    """ABDM_MODE=mock (default) simulates HIP data push. 'live' requires HIP registration, gateway client id/secret,
    consent-artefact flow and HIU callbacks per ABDM sandbox docs — implement here."""
    mode = os.environ.get("ABDM_MODE", "mock")
    if mode != "mock":
        raise NotImplementedError("Live ABDM gateway integration requires HIP onboarding; see README → ABDM.")
    return {"mode": "mock", "ref": "MOCK-" + uuid.uuid4().hex[:10].upper(), "linked_abha": abha, "ts": time.time()}
