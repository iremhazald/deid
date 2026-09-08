"""Authoritative document-language resolver for detector-pack routing."""

from __future__ import annotations

from typing import Any, Literal

from app.language.detect import AMBIGUOUS_FALLBACK, detect_document_language

RequestedLanguage = Literal["auto", "tr", "en"]
ResolvedLanguage = Literal["tr", "en"]

_TURKISH_ALIASES = frozenset({"tr", "tr-tr", "turkish", "turkce", "türkçe"})
_ENGLISH_ALIASES = frozenset(
    {
        "en",
        "en-us",
        "en-gb",
        "en-ca",
        "en-au",
        "english",
    }
)
_AUTO_ALIASES = frozenset({"auto", "automatic", "detect"})


def normalize_requested_language(raw: str | None) -> RequestedLanguage | None:
    """Map API / job aliases to ``auto`` | ``tr`` | ``en``.

    ``en-GB`` / ``en-US`` still become English-General (``en``). They do not
    select a UK or US jurisdiction pack.

    Unknown or empty values return ``None`` so callers can apply the legacy
    omitted-language default.
    """
    if raw is None:
        return None
    value = raw.strip().lower()
    if not value:
        return None
    if value in _AUTO_ALIASES:
        return "auto"
    if value in _TURKISH_ALIASES:
        return "tr"
    if value in _ENGLISH_ALIASES:
        return "en"
    return None


def resolve_document_language(requested: str | None, pages_or_text: Any) -> ResolvedLanguage:
    """Resolve a requested language to ``tr`` or ``en``.

    * ``tr`` / Turkish aliases → ``tr`` (no heuristic)
    * ``en`` / English aliases → ``en`` (no heuristic; English-General)
    * ``auto`` → local heuristic; ambiguous samples use ``tr``
    * omitted / invalid → ``tr`` (legacy default; not Auto)
    """
    normalized = normalize_requested_language(requested)
    if normalized == "en":
        return "en"
    if normalized == "tr":
        return "tr"
    if normalized == "auto":
        detected = detect_document_language(pages_or_text)
        return "en" if detected == "en" else AMBIGUOUS_FALLBACK
    return "tr"
