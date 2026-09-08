"""Normalized local NER types. No tensors, no probability-as-confidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.models import EntityCandidate, LocalNERStatus


class LocalNERLanguage(StrEnum):
    TR = "tr"
    EN = "en"


class LocalNERProviderName(StrEnum):
    BERTURK = "BERTURK"
    SPACY = "SPACY"


class LocalNERErrorCode(StrEnum):
    LOCAL_NER_MODEL_UNAVAILABLE = "LOCAL_NER_MODEL_UNAVAILABLE"
    LOCAL_NER_LANGUAGE_UNSUPPORTED = "LOCAL_NER_LANGUAGE_UNSUPPORTED"
    LOCAL_NER_INFERENCE_FAILED = "LOCAL_NER_INFERENCE_FAILED"
    LOCAL_NER_DEPENDENCY_MISSING = "LOCAL_NER_DEPENDENCY_MISSING"


@dataclass(frozen=True)
class NERPrediction:
    start: int
    end: int
    text: str
    label: str
    score: float | None
    language: str
    provider: str
    model_id: str


@dataclass(frozen=True)
class LocalNERMetrics:
    """Safe timing counters. Never include document text."""

    load_ms: float | None = None
    inference_ms: float | None = None
    characters: int = 0
    tokens: int | None = None
    raw_prediction_count: int = 0
    candidate_count: int = 0
    chunk_count: int = 0
    converted_candidate_count: int = 0
    accept_count: int = 0
    review_count: int = 0
    ignore_count: int = 0
    survived_merge_count: int = 0
    predict_called: bool = False
    model_loaded: bool = False
    provider_class: str | None = None


@dataclass
class LocalNERRun:
    status: LocalNERStatus
    language: str | None = None
    provider: str | None = None
    model_id: str | None = None
    candidates: list[EntityCandidate] = field(default_factory=list)
    candidate_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    metrics: LocalNERMetrics | None = None
    detectors: list[str] = field(default_factory=list)


class LocalNERError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
