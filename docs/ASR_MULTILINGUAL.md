# Configurable ASR and multilingual clinical interaction

## Implemented contract

The ASR boundary is [`backend/app/asr.py`](../backend/app/asr.py). It supports
the requested input labels `en`, `hi`, and `hinglish`, but a label is not a
claim of clinical language support. Every result preserves:

- the original transcript;
- requested and provider-detected language;
- provider/model identity;
- whether the provider was available and evaluated;
- failure reason and safe fallback state.

Browser Web Speech results are persisted through `POST /api/asr/transcripts`.
Audio can be sent to `POST /api/asr/transcribe`. Users may correct a transcript
with `PUT /api/asr/transcripts/{id}`. The corrected text is then re-extracted
by the same clinical extraction service and stored as an evidence-linked
`asr_transcript` document. The existing history UI makes its text answer
editable before continuing and persists that correction. An applied transcript
can also be sent to a stateful interview session with
`POST /api/asr/transcripts/{id}/apply` and a `session_id` plus question `field`.
Thus the corrected text reaches the adaptive history agent, extraction, and
source-linked summary through the same paths as typed text.

If no ASR provider is configured, audio transcription returns a structured
failure and the UI must fall back to typing or browser speech. No empty
transcript is treated as a clinical negative. Original audio is not stored.

The patient interface offers Click/Tap Mode and Hands-Free Voice Mode. The
hands-free flow requests microphone permission only after consent and an
explicit start action. It speaks each question when a suitable browser voice
is available, then listens using the selected `en-IN` or `hi-IN` recognition
locale. It does not switch locale automatically. Browser recognition API
presence does not guarantee that the browser's speech service, microphone
permission, network, or selected locale will work; runtime errors are shown
and the patient can switch to Click/Tap Mode. Browser support cannot be
reliably inferred in advance.

Recognized option answers are accepted only on an exact match to a displayed
option. The interface reads the interpreted answer back, requires explicit
confirmation, and lets the patient repeat or correct it. Unmatched speech
requires clarification; it is not silently converted into a clinical answer.
Text answers remain editable. Transcript persistence and interview-answer
persistence are separate operations; if either fails, the patient is told to
retry before proceeding. Raw microphone audio is not retained.

Any browser automation that stubs `SpeechRecognition` validates UI state
transitions only. It does not test real microphone capture, browser speech
services, language availability, recognition accuracy, or text-to-speech
quality. Those require manual checks on each supported browser/device and
language, with permissioned test speech.

## Provider status and integration requirements

The configurable providers are:

- `whisper-local`: requires the optional `whisper` and audio-decoding
  dependencies plus locally available model weights. The model name and
  checkpoint licence must be verified by the deployment owner. OpenAI's
  official Whisper repository is MIT-licensed, but its model weights and
  runtime still require deployment review. The repository does not bundle
  weights or claim a trained checkpoint.
- `bhashini`: requires a permitted Bhashini endpoint, credentials, provider
  contract, and the specific ASR service's language/licence terms.
- `ai4bharat`: requires a permitted per-resource AI4Bharat checkpoint or
  endpoint, its exact licence, compatible runtime, and access credentials.
  The verified `ai4bharat/indic-conformer-600m-multilingual` model card states
  MIT licensing and 22 Indian-language coverage, including Hindi, and requires
  Transformers, Torch/Torchaudio, remote model code, and 16 kHz audio. It
  does not provide English or Hinglish support, so it is not treated as a
  complete English/Hindi/Hinglish solution. The organization page is not
  treated as a single licence.

Set `MEDIKIOSK_ASR_PROVIDER`, `MEDIKIOSK_ASR_MODEL`, and, for HTTP providers,
`MEDIKIOSK_ASR_ENDPOINT` and `MEDIKIOSK_ASR_TOKEN`. `GET /api/asr/status`
reports configuration only; it does not certify language quality.

At the time of implementation no local Whisper weights, Bhashini credentials,
or AI4Bharat checkpoint with verified deployment terms were available. No ASR
model was trained or fine-tuned.

## Evaluation

From the backend directory, `scripts/evaluate_asr.py` reports WER and
clinical-entity precision/recall separately for each language. It accepts the
bundled CSV smoke format
or a JSONL manifest. The bundled `local_asr_text` resource has simulated
transcripts and no audio, so its results are text-pair smoke results only and
cannot measure microphone quality, Indian accents, code-switching, or clinical
deployment performance.

A deployment evaluation must contain speaker-disjoint, permissioned audio and
references for English, Hindi, and Hinglish, including medical terminology,
numbers, durations, negation, code-switching, and relevant Indian-accented
speech. Report WER and clinical-entity transcription accuracy by language,
with audio availability and model/provider identity. Successful model loading
alone is insufficient evidence.

The bundled text-only smoke file was run on 2026-10-14:

| Language | Rows | WER | Clinical-entity recall | Clinical-entity precision | Audio |
|---|---:|---:|---:|---:|---|
| Hindi | 765 | 0.0910 | 0.0000 | 0.0000 | No |
| English | 135 | 0.1397 | 0.4593 | 0.4667 | No |

These are measured text-pair results, not ASR model results: the file contains
simulated transcripts and no audio, Hindi clinical extraction is not yet
covered by the current English-oriented extractor, and no Hinglish rows are
present. They must not be used as evidence of clinical language support.
