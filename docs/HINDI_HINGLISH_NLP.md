# Hindi / Hinglish clinical text

Rule-based layer in `backend/app/hindi_nlp.py`, hooked into `clinical_nlp.py` and `history_agent.classify_answer`. **Text only. No speech accuracy is claimed**: the bundled ASR data is simulated text and no audio exists.

**Covered:** Devanagari and romanised negation (नहीं, nahi, बिना), uncertainty (पता नहीं, शायद, pata nahi), declining; uncertainty is checked before negation because "पता नहीं" contains "नहीं";
numbers (digits, Devanagari digits, words such as सात/डेढ़/saat); durations (दिन/हफ्ते/महीने/साल/घंटे, din/hafte/mahine/saal, "करीब", "पहले", "कल से"); ~35 symptom/condition terms mapped to the English
concept names so existing red-flag rules fire on Hindi; family experiencer (पिताजी को शुगर); "no allergy / no medicine" statements; spelling normalisation (nukta, chandrabindu) with provenance spans mapped
back to the original text. English gaps found on the way were also fixed ("nothing helps", "About 2 weeks.").

**Not covered / known limits:** word-based answer polarity (a positive sentence containing नहीं, e.g. "दर्द कभी नहीं रुकता", is read as negative); medicine names written in Devanagari; Hindi medication
frequencies; allergy *agents* in Hindi; severity words in free speech beyond simple numbers; dialects and heavy code-mixing; any negation scope longer than the clause. Everything was measured only on synthetic
templated answers plus ~50 hand-written cases. Clinical review of the lexicon and question wording by Hindi-speaking clinicians is required before use.
