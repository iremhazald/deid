"""spaCy en_core_web_sm provider. Heavy imports stay inside load()."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.core.config import get_settings
from app.ner.chunking import predict_chunked
from app.ner.instrumentation import timed_ms
from app.ner.labels import mapped_entity_type
from app.ner.models import LocalNERError, LocalNERErrorCode, NERPrediction

logger = logging.getLogger(__name__)

DEFAULT_EN_NER_MODEL = "en_core_web_sm"
_SAFE_MAX_LENGTH = 1_000_000


def _spacy_installed() -> bool:
    import importlib.util

    return importlib.util.find_spec("spacy") is not None


class EnglishSpacyNERProvider:
    language = "en"
    provider_name = "SPACY"

    def __init__(self, model_id: str | None = None) -> None:
        settings = get_settings()
        self.model_id = model_id or settings.deid_en_ner_model
        self._max_chars = settings.deid_ner_max_chars_per_chunk
        self._chunk_overlap = settings.deid_ner_chunk_overlap_chars
        self._lock = threading.Lock()
        self._nlp: Any = None
        self.loaded = False
        self.last_load_ms: float | None = None
        self.predict_calls = 0
        self.chunks_seen = 0

    def metadata(self) -> dict[str, str]:
        return {
            "language": self.language,
            "provider": self.provider_name,
            "model_id": self.model_id,
        }

    def is_available(self) -> bool:
        if not _spacy_installed():
            return False
        if self.loaded:
            return True
        try:
            import spacy
        except ImportError:
            return False
        return bool(spacy.util.is_package(self.model_id))

    def unload(self) -> None:
        with self._lock:
            self._nlp = None
            self.loaded = False

    def load(self) -> None:
        if self.loaded and self._nlp is not None:
            return
        with self._lock:
            if self.loaded and self._nlp is not None:
                return
            if not _spacy_installed():
                raise LocalNERError(
                    LocalNERErrorCode.LOCAL_NER_DEPENDENCY_MISSING,
                    "English local NER requires the local-ner-en extra (spaCy).",
                )
            try:
                import spacy
            except ImportError as exc:
                raise LocalNERError(
                    LocalNERErrorCode.LOCAL_NER_DEPENDENCY_MISSING,
                    "English local NER requires the local-ner-en extra (spaCy).",
                ) from exc
            with timed_ms() as elapsed:
                try:
                    nlp = spacy.load(
                        self.model_id,
                        disable=["parser", "lemmatizer", "textcat", "attribute_ruler"],
                    )
                except OSError as exc:
                    raise LocalNERError(
                        LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
                        "English spaCy model is not installed. "
                        "Run: python -m spacy download en_core_web_sm",
                    ) from exc
                except Exception as exc:
                    raise LocalNERError(
                        LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                        "English NER model failed to load.",
                    ) from exc
                if getattr(nlp, "max_length", 0) < _SAFE_MAX_LENGTH:
                    nlp.max_length = _SAFE_MAX_LENGTH
                self._nlp = nlp
                self.loaded = True
            self.last_load_ms = elapsed[0]
            logger.info("local_ner loaded provider=SPACY load_ms=%.1f", self.last_load_ms)

    def predict(self, text: str, language: str) -> list[NERPrediction]:
        self.predict_calls += 1
        if language != "en":
            return []
        if not text:
            return []
        self.load()
        return predict_chunked(
            text,
            self._predict_window,
            max_chars=self._max_chars,
            overlap=self._chunk_overlap,
        )

    def _predict_window(self, text: str) -> list[NERPrediction]:
        assert self._nlp is not None
        self.chunks_seen += 1
        try:
            doc = self._nlp(text)
        except Exception as exc:
            raise LocalNERError(
                LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                "English NER inference failed.",
            ) from exc
        found: list[NERPrediction] = []
        for ent in doc.ents:
            label = str(ent.label_)
            if mapped_entity_type(label) is None:
                continue
            start = int(ent.start_char)
            end = int(ent.end_char)
            if start < 0 or end > len(text) or end <= start:
                continue
            surface = text[start:end]
            if surface != ent.text:
                continue
            score = None
            found.append(
                NERPrediction(
                    start=start,
                    end=end,
                    text=surface,
                    label=label,
                    score=score,
                    language=self.language,
                    provider=self.provider_name,
                    model_id=self.model_id,
                )
            )
        return found
