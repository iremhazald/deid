"""Plain-text copy of a transformed document.

Visual review may still draw block characters. The string the user copies
uses a fixed REDACT token so the pasted text does not leak source length.
Secure PDF redaction does not use this module.
"""

from __future__ import annotations

from dataclasses import replace

from app.domain.models import TransformationStrategy
from app.transforms.planner import apply_operations
from app.transforms.strategies import TransformOp, redact_value
from app.transforms.tag_taxonomy import normalize_tag_locale

REDACT_COPY_TOKEN_TR = "[GİZLENDİ]"
REDACT_COPY_TOKEN_EN = "[REDACTED]"


def redact_copy_token(document_language: str | None) -> str:
    """Token follows the document language, the same locale as placeholder tags."""
    if normalize_tag_locale(document_language) == "en":
        return REDACT_COPY_TOKEN_EN
    return REDACT_COPY_TOKEN_TR


def replacement_for_copy(operation: TransformOp, document_language: str | None) -> str:
    """Swap length-preserving block redaction for the semantic token.

    Custom replacements and every other strategy stay as planned.
    """
    if operation.strategy != TransformationStrategy.REDACT:
        return operation.replacement
    if operation.replacement != redact_value(operation.original):
        return operation.replacement
    return redact_copy_token(document_language)


def apply_copy_operations(
    text: str,
    operations: list[TransformOp],
    document_language: str | None,
) -> str:
    """Return transformed text. ``text`` is not modified."""
    adjusted = [
        replace(operation, replacement=replacement_for_copy(operation, document_language))
        for operation in operations
        if operation.strategy != TransformationStrategy.KEEP
    ]
    return apply_operations(text, adjusted)
