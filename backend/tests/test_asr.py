import os
import tempfile

os.environ["MEDIKIOSK_DB"] = os.path.join(tempfile.mkdtemp(), "asr.db")

from app import asr
from app.asr_metrics import evaluate, wer


class FakeAdapter:
    name = "fake"
    model = "test"

    def transcribe(self, audio, language, filename):
        return "chest pain for two days", "en"

    def status(self):
        return {"available": True}


def test_language_validation_and_truthful_unavailable_fallback():
    assert asr.validate_language("Hinglish") == "hinglish"
    result = asr.transcribe(b"audio", "en", "a.wav", asr.UnavailableAdapter())
    assert not result.available and result.fallback and result.original_transcript == ""


def test_transcription_contract_preserves_detected_language():
    result = asr.transcribe(b"audio", "en", "a.wav", FakeAdapter())
    assert result.original_transcript == "chest pain for two days"
    assert result.language_detected == "en"
    assert not result.evaluated


def test_language_metrics_include_clinical_entities_and_text_only_warning():
    report = evaluate([{"language": "hi", "reference_text": "fever for 2 days", "simulated_asr_text": "fever for two days"}])
    assert report["hi"]["rows"] == 1
    assert report["hi"]["audio_present"] is False
    assert report["hi"]["clinical_entity_recall"] == 1
    assert "not measure" in report["hi"]["note"]
    assert wer("no chest pain", "chest pain") > 0
