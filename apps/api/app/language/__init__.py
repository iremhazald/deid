"""Document-language routing (not UI locale, not PII evidence scoring)."""

from app.language.detect import detect_document_language
from app.language.resolve import (
    AMBIGUOUS_FALLBACK,
    normalize_requested_language,
    resolve_document_language,
)

__all__ = [
    "AMBIGUOUS_FALLBACK",
    "detect_document_language",
    "normalize_requested_language",
    "resolve_document_language",
]
