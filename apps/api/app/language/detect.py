"""Bounded, model-free heuristic for Auto document-language routing.

This module chooses between ``tr`` and ``en`` for detector-pack selection.
Scores stay internal. They are not PII evidence and must not be shown as
confidence percentages.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

# First N non-empty page/segment texts, then a hard character cap.
SAMPLE_MAX_PAGES = 8
SAMPLE_MAX_CHARS = 20_000
MIN_ALPHA_CHARS = 40
MIN_WORD_TOKENS = 8
MIN_WINNING_SCORE = 3.0
SCORE_MARGIN = 3.5
AMBIGUOUS_FALLBACK = "tr"

_TURKISH_CHARS = frozenset("çğıöşüÇĞİÖŞÜ")
_FOLD = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
    }
)
_TOKEN_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü]+")
_SPACED_LETTERS_RE = re.compile(
    r"\b(?:[A-Za-zÇĞİÖŞÜçğıöşü]\s+){2,}[A-Za-zÇĞİÖŞÜçğıöşü]\b"
)

# Function / legal words. Weights are routing-only. One token never decides.
_TURKISH_WORDS: dict[str, float] = {
    "ve": 1.0,
    "ile": 1.0,
    "icin": 2.0,
    "tarafindan": 3.0,
    "mahkeme": 3.0,
    "mahkemesi": 3.0,
    "davaci": 3.0,
    "davali": 3.0,
    "sanik": 3.0,
    "karar": 2.0,
    "esas": 2.0,
    "dosya": 2.0,
    "vekil": 2.0,
    "mudafi": 3.0,
    "basvuru": 2.0,
    "hukum": 2.0,
}

# Proper nouns and company suffixes are excluded so "Ltd" / "Limited"
# cannot flip a names-only header block to English.
_ENGLISH_WORDS: dict[str, float] = {
    "the": 1.0,
    "and": 1.0,
    "of": 1.0,
    "for": 1.0,
    "court": 2.0,
    "claimant": 3.0,
    "plaintiff": 3.0,
    "defendant": 3.0,
    "applicant": 2.0,
    "respondent": 3.0,
    "witness": 2.0,
    "counsel": 2.0,
    "judgment": 2.0,
    "judgement": 2.0,
    "order": 1.0,
    "case": 1.0,
    "claim": 1.0,
    "address": 1.0,
    "signed": 2.0,
}

_ENGLISH_BLOCKLIST = frozenset(
    {
        "limited",
        "ltd",
        "llc",
        "llp",
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "plc",
        "company",
        "street",
        "road",
        "avenue",
        "lane",
    }
)


def detect_document_language(pages_or_text: Any) -> str:
    """Return ``tr`` or ``en`` from a bounded sample of extracted text.

    Ambiguous, short, numeric, or names-only samples fall back to ``tr``
    (legacy Turkish/global path). UI language is never consulted.
    """
    sample = sample_document_text(pages_or_text)
    turkish_score, english_score, usable = _score_sample(sample)
    if not usable:
        return AMBIGUOUS_FALLBACK
    if (
        turkish_score >= MIN_WINNING_SCORE
        and turkish_score >= english_score + SCORE_MARGIN
    ):
        return "tr"
    if (
        english_score >= MIN_WINNING_SCORE
        and english_score >= turkish_score + SCORE_MARGIN
    ):
        return "en"
    return AMBIGUOUS_FALLBACK


def sample_document_text(pages_or_text: Any) -> str:
    """Collect a bounded, non-numeric sample for routing only."""
    chunks: list[str] = []
    used = 0
    pages_seen = 0
    for raw in _iter_segments(pages_or_text):
        cleaned = _usable_lines(raw)
        if not cleaned.strip():
            continue
        pages_seen += 1
        remaining = SAMPLE_MAX_CHARS - used
        piece = cleaned if len(cleaned) <= remaining else cleaned[:remaining]
        chunks.append(piece)
        used += len(piece)
        if pages_seen >= SAMPLE_MAX_PAGES or used >= SAMPLE_MAX_CHARS:
            break
    sample = "\n".join(chunks)
    return _collapse_spaced_letters(sample)


def _iter_segments(pages_or_text: Any) -> Iterable[str]:
    if pages_or_text is None:
        return []
    if isinstance(pages_or_text, str):
        return [pages_or_text]
    if isinstance(pages_or_text, Sequence) and not isinstance(pages_or_text, (str, bytes)):
        texts: list[str] = []
        for item in pages_or_text:
            if isinstance(item, str):
                texts.append(item)
            else:
                texts.append(str(getattr(item, "text", "") or ""))
        return texts
    return [str(pages_or_text)]


def _usable_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _is_mostly_numeric(stripped):
            continue
        kept.append(stripped)
    return "\n".join(kept)


def _is_mostly_numeric(line: str) -> bool:
    letters = sum(1 for char in line if char.isalpha())
    digits = sum(1 for char in line if char.isdigit())
    if letters == 0:
        return True
    return digits > letters * 2 and letters < 6


def _collapse_spaced_letters(text: str) -> str:
    return _SPACED_LETTERS_RE.sub(lambda match: re.sub(r"\s+", "", match.group(0)), text)


def _fold(token: str) -> str:
    return token.translate(_FOLD).lower()


def _score_sample(sample: str) -> tuple[float, float, bool]:
    alpha_chars = sum(1 for char in sample if char.isalpha())
    tokens = _TOKEN_RE.findall(sample)
    if alpha_chars < MIN_ALPHA_CHARS or len(tokens) < MIN_WORD_TOKENS:
        return 0.0, 0.0, False

    turkish_words, english_words = _count_signal_words(tokens)
    turkish_word_score, turkish_distinct = _weighted_score(turkish_words, _TURKISH_WORDS)
    english_word_score, english_distinct = _weighted_score(english_words, _ENGLISH_WORDS)
    char_score = _turkish_char_score(sample)

    # Characters alone (a name with ı/ş) must not classify the document.
    # A single function/legal token is also insufficient.
    turkish_ready = turkish_distinct >= 2 or (
        char_score >= 2.5 and turkish_distinct >= 1
    )
    english_ready = english_distinct >= 2
    turkish_score = turkish_word_score + (char_score if turkish_ready else 0.0)
    english_score = english_word_score if english_ready else 0.0
    usable = turkish_ready or english_ready
    return turkish_score, english_score, usable


def _count_signal_words(tokens: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    turkish: dict[str, int] = {}
    english: dict[str, int] = {}
    for token in tokens:
        folded = _fold(token)
        if folded in _ENGLISH_BLOCKLIST:
            continue
        if folded in _TURKISH_WORDS:
            turkish[folded] = turkish.get(folded, 0) + 1
        if folded in _ENGLISH_WORDS:
            english[folded] = english.get(folded, 0) + 1
    return turkish, english


def _weighted_score(hits: dict[str, int], weights: dict[str, float]) -> tuple[float, int]:
    score = 0.0
    for word, count in hits.items():
        # Cap a single repeated token so it cannot dominate.
        score += weights[word] * min(1.0 + 0.35 * (count - 1), 2.0)
    return score, len(hits)


def _turkish_char_score(sample: str) -> float:
    found = {char.casefold() for char in sample if char in _TURKISH_CHARS}
    if not found:
        return 0.0
    count = sum(1 for char in sample if char in _TURKISH_CHARS)
    return min(len(found) * 1.6 + min(count, 16) * 0.12, 6.0)
