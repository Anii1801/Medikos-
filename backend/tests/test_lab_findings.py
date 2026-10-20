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
