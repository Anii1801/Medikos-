"""Laboratory extraction: dataset benchmark regression, layout-variation tests and a real scanned-PDF test.

Software tests on SYNTHETIC reports; they do not establish accuracy on real laboratory documents.
"""
import shutil
import io

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas

from app import ocr, summary
from app.datasets import DATASET_ROOT

LAB = DATASET_ROOT / "02_ocr_handwriting" / "lab_result_entities.csv"


def lab(text, name):
    return next(l for l in ocr.extract(text)["labs"] if l["test"] == name)


@pytest.mark.skipif(not LAB.exists(), reason="dataset not present")
def test_dataset_benchmark_does_not_regress():
    from training.lab_extraction_eval import evaluate
    r = evaluate("ground_truth_text", ocr.extract)
    assert r["labelled_results"] == 1238
    assert r["test_name_recall"] >= 0.99 and r["test_name_precision"] >= 0.99
    assert r["exact_value_accuracy"] >= 0.99 and r["unit_accuracy"] >= 0.99
    assert r["printed_reference_interval_accuracy"] >= 0.99
    assert r["false_abnormal_rate_on_printed_normal"] <= 0.005


@pytest.mark.skipif(not LAB.exists(), reason="dataset not present")
def test_noisy_ocr_text_failures_are_mostly_surfaced_not_silent():
    from training.lab_extraction_eval import canon, load
    labels, docs = load()
    wrong = silent = 0
    for rid, gold in labels.items():
        by = {canon(i["test"]): i for i in ocr.extract(docs[rid]["simulated_ocr_text"])["labs"]}
        for g in gold:
            it = by.get(canon(g["test"]))
            if it and (abs(it["value"] - float(g["value"])) > 1e-6 or it["reference_source"] != "document"
                       or (it["ref_low"], it["ref_high"]) != (float(g["ref_low"]), float(g["ref_high"]))):
                wrong += 1
                silent += not it["ambiguity"]
    assert wrong > 0 and silent / wrong < 0.10          # <10% of wrong results carry no confirmation flag (measured: 3/71)


def test_printed_interval_without_keyword_is_read_and_flag_captured():
    l = lab("Hemoglobin      9.8 g/dL     (13-17) L", "Haemoglobin")
    assert (l["ref_low"], l["ref_high"], l["reference_source"]) == (13.0, 17.0, "document")
    assert l["flag"] == "low" and l["printed_flag"] == "L" and not l["ambiguity"]


def test_unit_scale_mismatch_is_never_compared_or_converted():
    l = lab("WBC   10.16 x10^3/uL", "WBC")                      # baseline is /uL (4000-11000): 10.16 would look 'low'
    assert l["flag"] == "unable_to_interpret" and l["unit"] == "x10^3/uL"
    assert any("differs from baseline unit" in a for a in l["ambiguity"])
    assert "WBC" not in " ".join(ocr.abnormal([l]))


def test_with_printed_interval_the_scale_is_irrelevant():
    assert lab("WBC   10.16 x10^3/uL  (4-11) N", "WBC")["flag"] == "normal"


def test_no_interval_and_no_baseline_is_not_invented():
    l = lab("CRP 7.8 mg/L", "CRP")
    assert l["ref"] is None and l["flag"] == "unable_to_interpret" and l["reference_source"] == "configured_baseline"


def test_missing_unit_is_not_filled_from_configured_baseline():
    explicit_interval = lab("Haemoglobin 9.8 (13-17)", "Haemoglobin")
    assert explicit_interval["unit"] is None
    assert explicit_interval["reference_source"] == "document"
    assert any("unit not printed" in item for item in explicit_interval["ambiguity"])
    no_interval = lab("CRP 7.8", "CRP")
    assert no_interval["unit"] is None
    assert no_interval["reference_source"] == "unavailable"
    assert no_interval["flag"] == "unable_to_interpret"


def test_missing_measurement_is_not_extracted_from_the_reference_interval():
    extracted = ocr.extract("Haemoglobin g/dL reference range 12-16")
    assert extracted["labs"] == []
    assert not any(fact["field"] == "lab" for fact in extracted["facts"])


def test_repeated_lab_measurements_are_not_collapsed():
    extracted = ocr.extract(
        "Haemoglobin 10 g/dL (12-16) 2025-02-10\n"
        "Haemoglobin 11 g/dL (12-16) 2025-03-10"
    )
    hemoglobin = [item for item in extracted["labs"] if item["test"] == "Haemoglobin"]
    assert [(item["value"], item["measurement_date"]) for item in hemoglobin] == [
        (10.0, "2025-02-10"), (11.0, "2025-03-10")]


def test_reference_interval_is_never_borrowed_from_a_neighbouring_line():
    text = "Total Cholesterol   180 mg/dL   (0-200) N\nLDL   182.7 mg/dL\n"       # LDL row has no legible interval
    l = lab(text, "LDL")
    assert l["reference_source"] == "configured_baseline" and l["ref"] == "0–100" and l["flag"] == "high"
    assert any("no legible reference interval" in a for a in l["ambiguity"])


def test_critical_word_is_not_borrowed_from_a_neighbouring_line():
    text = "Creatinine 6.1 mg/dL (0.6-1.3) CRITICAL\nHaemoglobin 13 g/dL (12-16) N\n"
    assert lab(text, "Creatinine")["flag"] == "critical"
    assert lab(text, "Haemoglobin")["flag"] == "normal"


def test_printed_flag_disagreement_is_surfaced():
    l = lab("Haemoglobin 14 g/dL (12-16) L", "Haemoglobin")
    assert any("disagrees" in a for a in l["ambiguity"])


@pytest.mark.parametrize("text,name,value,lo,hi", [
    ("Hb: 11.2 g/dL (Ref: 12.0-15.5) L", "Haemoglobin", 11.2, 12.0, 15.5),
    ("Serum Creatinine 1.9 mg/dL Reference range 0.6 – 1.3 H", "Creatinine", 1.9, 0.6, 1.3),
    ("TSH 6.1 uIU/mL (0.4-4.0) H", "TSH", 6.1, 0.4, 4.0),
])
def test_layout_variations_other_than_the_dataset_template(text, name, value, lo, hi):
    l = lab(text, name)
    assert (l["value"], l["ref_low"], l["ref_high"], l["reference_source"]) == (value, lo, hi, "document")


def test_one_sided_printed_limit():
    l = lab("CRP 7.8 mg/L (<5.0) H", "CRP")
    assert l["ref_high"] == 5.0 and l["ref_low"] is None and l["flag"] == "high"


def _edit_distance(left, right):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def _synthetic_raster(format_name):
    image = Image.new("RGB", (1400, 280), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 64)
    except OSError:
        font = ImageFont.load_default(size=64)
    draw.text((40, 70), "Haemoglobin 12.4 g/dL (12-16)", fill="black", font=font)
    stream = io.BytesIO()
    image.save(stream, format=format_name)
    return stream.getvalue()


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed; real raster OCR is blocked")
@pytest.mark.parametrize(("format_name", "extension"), [
    ("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp"), ("TIFF", "tiff"),
])
def test_synthetic_raster_ocr_field_accuracy_and_error_rates(format_name, extension):
    expected = "Haemoglobin 12.4 g/dL (12-16)"
    text, engine, pages = ocr.ocr_document(_synthetic_raster(format_name), f"synthetic.{extension}")
    assert engine.startswith("tesseract(") and pages
    normalise = lambda value: " ".join(value.lower().split())
    actual = normalise(text)
    reference = normalise(expected)
    cer = _edit_distance(reference, actual) / max(1, len(reference))
    expected_words, actual_words = reference.split(), actual.split()
    wer = _edit_distance(expected_words, actual_words) / max(1, len(expected_words))
    assert cer <= 0.20 and wer <= 0.50
    finding = next(item for item in ocr.extract(text)["labs"] if item["test"] == "Haemoglobin")
    assert finding["value"] == pytest.approx(12.4)
    assert finding["unit"] == "g/dL"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed; real multiframe OCR is blocked")
def test_synthetic_multiframe_tiff_keeps_page_text_and_provenance():
    frames = []
    for line in ("Haemoglobin 12.4 g/dL (12-16)", "Creatinine 1.0 mg/dL (0.6-1.3)"):
        image = Image.new("RGB", (1400, 280), "white")
        ImageDraw.Draw(image).text((40, 70), line, fill="black",
                                  font=ImageFont.load_default(size=64))
        frames.append(image)
    stream = io.BytesIO()
    frames[0].save(stream, format="TIFF", save_all=True, append_images=frames[1:])
    text, engine, pages = ocr.ocr_document(stream.getvalue(), "synthetic-multipage.tiff")
    assert engine.startswith("tesseract(")
    assert [page["page"] for page in pages] == [1, 2]
    assert "Haemoglobin" in pages[0]["text"] and "Creatinine" in pages[1]["text"]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed; real multiframe OCR is blocked")
def test_synthetic_multiframe_webp_ocr_preserves_each_frame_and_finding():
    frames = []
    for line in ("Haemoglobin 12.4 g/dL (12-16)", "Creatinine 1.0 mg/dL (0.6-1.3)"):
        image = Image.new("RGB", (1400, 280), "white")
        ImageDraw.Draw(image).text((40, 70), line, fill="black",
                                  font=ImageFont.load_default(size=64))
        frames.append(image)
    stream = io.BytesIO()
    frames[0].save(stream, format="WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)
    text, engine, pages = ocr.ocr_document(stream.getvalue(), "synthetic-multiframe.webp")
    assert engine.startswith("tesseract(")
    assert [page["page"] for page in pages] == [1, 2]
    assert "Haemoglobin" in pages[0]["text"] and "Creatinine" in pages[1]["text"]
    findings = {item["test"]: item for item in ocr.extract(text)["labs"]}
    assert findings["Haemoglobin"]["value"] == pytest.approx(12.4)
    assert findings["Creatinine"]["value"] == pytest.approx(1.0)


def test_synthetic_multipage_pdf_text_extraction_keeps_page_provenance():
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(48, 780, "Laboratory Report 2025-03-12")
    pdf.drawString(48, 750, "Haemoglobin 9.1 g/dL (13-17) L")
    pdf.showPage()
    pdf.drawString(48, 780, "Creatinine 1.0 mg/dL (0.6-1.3) N")
    pdf.showPage()
    pdf.save()
    text, engine, pages = ocr.ocr_document(stream.getvalue(), "synthetic-multipage.pdf")
    assert engine == "pdf-text"
    assert [page["page"] for page in pages] == [1, 2]
    results = ocr.extract(text, {"source_id": "synthetic-pdf", "pages": pages})
    assert {item["test"] for item in results["labs"]} >= {"Haemoglobin", "Creatinine"}
    assert all(item["source"]["page"] in (1, 2) for item in results["labs"])


def test_critical_result_is_never_downgraded_in_the_summary():
    doc = {"filename": "r.pdf", "date": "2026-01-01", "entities": ocr.extract("Creatinine 6.1 mg/dL (0.6-1.3) CRITICAL")}
    f = summary._laboratory_findings([doc])[0]
    assert f["status"] == "critical_result" and "urgent" in f["explanation"]


def test_uncertain_findings_carry_their_reasons_into_the_summary():
    doc = {"filename": "r.pdf", "entities": ocr.extract("WBC 10.16 x10^3/uL")}
    f = summary._laboratory_findings([doc])[0]
    assert f["status"] == "unable_to_interpret" and any("differs from baseline" in u for u in f["uncertainty"])


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not installed")
def test_scanned_image_only_pdf_is_ocrd_and_parsed():
    from training.lab_scan_eval import render, to_scanned_pdf
    gt = ("District Hospital Agra  -  LABORATORY REPORT\nDate: 2025-03-05\nPanel: CBC\n"
          "------------------------------------------------------\n"
          "Hemoglobin                      9.80 g/dL       (13-17) L\n"
          "Creatinine                      1.90 mg/dL      (0.6-1.1) H\n")
    pdf = to_scanned_pdf(render(gt, "good", 1), 95)
    text, engine, pages = ocr.ocr_document(pdf, "scan.pdf")
    assert engine == "pdf-scanned-ocr(tesseract)" and pages[0]["blocks"]
    e = ocr.extract(text)
    by = {l["test"]: l for l in e["labs"]}
    assert by["Haemoglobin"]["value"] == 9.8 and by["Haemoglobin"]["flag"] == "low"
    assert by["Creatinine"]["value"] == 1.9 and by["Creatinine"]["flag"] == "high"


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not installed")
def test_multipage_scanned_pdf_ocr_preserves_page_findings():
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from training.lab_scan_eval import render

    images = [
        render("Haemoglobin 12.4 g/dL (12-16)", "good", 10),
        render("Creatinine 1.0 mg/dL (0.6-1.3)", "good", 11),
    ]
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(images[0].width, images[0].height))
    for image in images:
        pdf.setPageSize((image.width, image.height))
        pdf.drawImage(ImageReader(image), 0, 0, image.width, image.height)
        pdf.showPage()
    pdf.save()

    text, engine, pages = ocr.ocr_document(stream.getvalue(), "synthetic-multipage-scan.pdf")
    assert engine == "pdf-scanned-ocr(tesseract)"
    assert [page["page"] for page in pages] == [1, 2]
    assert "Haemoglobin" in pages[0]["text"] and "Creatinine" in pages[1]["text"]
    findings = {item["test"]: item for item in ocr.extract(text)["labs"]}
    assert findings["Haemoglobin"]["value"] == pytest.approx(12.4)
    assert findings["Creatinine"]["value"] == pytest.approx(1.0)


def test_blank_scanned_pdf_reports_unsupported_not_fabricated_text():
    from reportlab.pdfgen import canvas
    import io
    b = io.BytesIO(); c = canvas.Canvas(b); c.showPage(); c.save()
    text, engine, _ = ocr.ocr_document(b.getvalue(), "blank.pdf")
    assert text == "" and engine == "pdf-scanned-unsupported"
