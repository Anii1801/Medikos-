from app import ocr, summary


def test_report_reference_interval_wins_and_is_source_linked():
    entities = ocr.extract("Pathology report 2026-01-02\nHaemoglobin 10 g/dL (ref range 12-16)")
    lab = entities["labs"][0]
    assert lab["ref"] == "12–16"
    assert lab["reference_source"] == "document"
    assert lab["interpretation"] == "below"
    assert lab["source"]["start"] is not None

    sections = summary.build_sections(
        {"name": "A", "age": "40"},
        {"cc": "Fatigue"},
        [{"id": 7, "filename": "lab.pdf", "date": "2026-01-02", "engine": "pdf-text",
          "entities": entities}],
    )
    section = next(item for item in sections if item["title"] == "Laboratory and Investigation Findings")
    finding = section["findings"][0]
    assert finding["test_name"] == "Haemoglobin"
    assert finding["status"] == "below_reference_interval"
    assert finding["source_document"] == "lab.pdf"
    assert finding["clinician_review_status"] == "pending"


def test_missing_report_interval_is_disclosed_in_summary():
    entities = ocr.extract("Haemoglobin 14 g/dL")
    sections = summary.build_sections(
        {"name": "A"},
        {"cc": "Fatigue"},
        [{"id": 8, "filename": "missing-range.txt", "date": "", "engine": "typed",
          "entities": entities}],
    )
    finding = next(item for item in sections if item["title"] == "Laboratory and Investigation Findings")["findings"][0]
    assert finding["uncertainty"]
    assert "configured baseline" in finding["uncertainty"][0]


def test_multiple_measurements_and_conflicting_document_dates_are_preserved():
    older = ocr.extract("Laboratory report 2025-02-10\nHaemoglobin 10 g/dL (12-16)")
    newer = ocr.extract("Laboratory report 2025-03-10\nHaemoglobin 11 g/dL (12-16)")
    sections = summary.build_sections(
        {"name": "A"},
        {"cc": "Fatigue"},
        [
            {"id": 10, "filename": "older.pdf", "date": "2025-02-11", "engine": "pdf-text", "entities": older},
            {"id": 11, "filename": "newer.pdf", "date": "2025-03-10", "engine": "pdf-text", "entities": newer},
        ],
    )
    findings = next(item for item in sections if item["title"] == "Laboratory and Investigation Findings")["findings"]
    assert [(item["result"], item["report_date"]) for item in findings] == [
        (10.0, "2025-02-10"), (11.0, "2025-03-10")]
    assert findings[0]["date_conflict"] is True
    assert findings[0]["entered_document_date"] == "2025-02-11"
    assert findings[1]["date_conflict"] is False


def test_different_lab_values_for_the_same_date_are_flagged_not_resolved():
    entities = ocr.extract(
        "Haemoglobin 9.1 g/dL (13-17) 2025-03-12\n"
        "Haemoglobin 10.0 g/dL (13-17) 2025-03-12"
    )
    sections = summary.build_sections(
        {"name": "A"}, {"cc": "Fatigue"},
        [{"id": 12, "filename": "same-day.pdf", "date": "2025-03-12",
          "engine": "pdf-text", "entities": entities}],
    )
    conflict = next(item for item in sections if item["title"] == "Conflicts requiring review")
    assert "conflicting_laboratory_measurements" in conflict["review_flags"]
    assert "multiple differing document measurements" in conflict["text"]


def test_findings_without_provenance_remain_visible_and_require_source_review():
    sections = summary.build_sections(
        {"name": "A"}, {"cc": "Fatigue"},
        [{"id": 13, "filename": "legacy.txt", "date": "", "engine": "legacy",
          "processing_status": "needs_review",
          "entities": {"labs": [{"test": "Haemoglobin", "value": 12.0, "unit": None, "ref": None,
                                  "flag": "unable_to_interpret", "reference_source": "unavailable"}],
                       "medications": [{"name": "Aspirin", "dose": None, "frequency": None}],
                       "diagnoses": [], "symptoms": [], "allergies": [], "facts": []}}],
    )
    lab = next(section for section in sections if section["title"] == "Laboratory and Investigation Findings")
    assert any("provenance is missing" in warning for warning in lab["findings"][0]["uncertainty"])
    medication = next(section for section in sections if section["title"] == "Current medications and allergies")
    assert medication["findings"][0]["verification_status"] == "missing_provenance_needs_review"
    verify = next(section for section in sections if section["title"] == "Items requiring clinician verification")
    assert verify["findings"]
