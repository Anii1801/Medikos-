"""Configurable speech recognition boundary with truthful capability reporting."""
from __future__ import annotations

import io
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}


class ASRResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transcript_id: str
    original_transcript: str
    language: str
    language_detected: str | None = None
    provider: str
    model: str
    available: bool
    evaluated: bool = False
    fallback: bool = False
    error: str | None = None
    created: float = Field(default_factory=time.time)


class ASRAdapter(Protocol):
    name: str
    model: str

    def transcribe(self, audio: bytes, language: str, filename: str) -> tuple[str, str | None]:
        ...

    def status(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class UnavailableAdapter:
    name: str = "unavailable"
    model: str = "none"

    def transcribe(self, audio: bytes, language: str, filename: str) -> tuple[str, str | None]:
        raise RuntimeError("No ASR provider is configured; use browser transcript or type the answer")

    def status(self) -> dict[str, Any]:
        return {"provider": self.name, "model": self.model, "available": False,
                "evaluated_languages": [], "reason": "No provider configured"}


class WhisperAdapter:
    name = "whisper-local"

    def __init__(self, model: str):
        self.model = model
        self._engine = None
        self._error = None
        try:
            import whisper  # type: ignore
            self._engine = whisper.load_model(model)
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"

    def transcribe(self, audio: bytes, language: str, filename: str) -> tuple[str, str | None]:
        if self._engine is None:
            raise RuntimeError(f"Whisper is unavailable: {self._error}")
        # openai-whisper accepts a file path or a decoded waveform. Avoid
        # writing patient audio to disk; ffmpeg decoding is provider-specific.
        try:
            import soundfile as sf  # type: ignore
            waveform, sample_rate = sf.read(io.BytesIO(audio), dtype="float32")
            result = self._engine.transcribe(waveform, language=None if language == "hinglish" else language,
                                             fp16=False, without_timestamps=True)
        except Exception as exc:
            raise RuntimeError(f"Whisper audio decoding failed: {type(exc).__name__}: {exc}") from exc
        return (result.get("text") or "").strip(), result.get("language")

    def status(self) -> dict[str, Any]:
        return {"provider": self.name, "model": self.model, "available": self._engine is not None,
                "evaluated_languages": [], "reason": self._error}


@dataclass(frozen=True)
class HTTPIndicAdapter:
    """Provider boundary for a configured Bhashini/AI4Bharat deployment.

    Endpoint and token are deliberately required at runtime. The repository
    does not bundle credentials, weights, or a provider licence.
    """

    provider: str
    endpoint: str
    token: str
    model: str

    @property
    def name(self) -> str:
        return self.provider

    def transcribe(self, audio: bytes, language: str, filename: str) -> tuple[str, str | None]:
        if language == "hinglish":
            raise RuntimeError("Configured Indic providers must demonstrate code-switching support before Hinglish use")
        try:
            import httpx
            response = httpx.post(self.endpoint, headers={"Authorization": f"Bearer {self.token}"},
                                  files={"audio": (filename, audio)}, data={"language": language}, timeout=60)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(f"{self.provider} request failed: {type(exc).__name__}: {exc}") from exc
        text = payload.get("transcript") or payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"{self.provider} returned no transcript")
        return text.strip(), payload.get("language")

    def status(self) -> dict[str, Any]:
        return {"provider": self.provider, "model": self.model, "available": True,
                "evaluated_languages": [], "reason": "Configured endpoint; language evaluation still required"}


def configured_adapter() -> ASRAdapter:
    provider = os.environ.get("MEDIKIOSK_ASR_PROVIDER", "unavailable").lower()
    if provider == "whisper":
        return WhisperAdapter(os.environ.get("MEDIKIOSK_ASR_MODEL", "base"))
    if provider in {"bhashini", "ai4bharat"}:
        endpoint = os.environ.get("MEDIKIOSK_ASR_ENDPOINT", "")
        token = os.environ.get("MEDIKIOSK_ASR_TOKEN", "")
        if endpoint and token:
            return HTTPIndicAdapter(provider, endpoint, token, os.environ.get("MEDIKIOSK_ASR_MODEL", "provider-default"))
        return UnavailableAdapter(name=provider, model=os.environ.get("MEDIKIOSK_ASR_MODEL", "unconfigured"))
    return UnavailableAdapter()


def validate_language(language: str) -> str:
    language = (language or "").lower().strip()
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("language must be one of: en, hi, hinglish")
    return language


def transcribe(audio: bytes, language: str, filename: str, adapter: ASRAdapter | None = None) -> ASRResult:
    language = validate_language(language)
    adapter = adapter or configured_adapter()
    try:
        text, detected = adapter.transcribe(audio, language, filename)
        return ASRResult(transcript_id=str(uuid.uuid4()), original_transcript=text, language=language,
                         language_detected=detected, provider=adapter.name, model=adapter.model,
                         available=True)
    except Exception as exc:
        return ASRResult(transcript_id=str(uuid.uuid4()), original_transcript="", language=language,
                         provider=adapter.name, model=adapter.model, available=False, fallback=True,
                         error=str(exc))
