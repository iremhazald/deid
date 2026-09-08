"""Shared helpers for the English-General deterministic pack."""

from __future__ import annotations

import re
from typing import Iterable

from app.detectors.en.vocab import (
    COMPANY_SUFFIXES,
    COURT_HEAD_ADJECTIVES,
    COURT_PHRASES,
    DECISION_ROLE_LABELS,
    ENGLISH_FIRST_NAMES,
    INSTITUTION_PHRASES,
    LEGAL_HEADING_CUES,
    LEGAL_ROLE_WORDS,
    LITIGATION_ORDINALS,
    PARTY_ROLE_WORDS,
    PERSON_TITLES,
    REPRESENTATION_STATUS,
    STREET_TYPES,
    TRADING_AS_MARKERS,
)
from app.detectors.legal.common import make_candidate
from app.detectors.scoring.models import Evidence, EvidenceSource

# Title-case / ALLCAPS / hyphenated / O'Connor / D'Angelo / Mc'Donald.
# Intentionally excludes single-letter initials and McAuliffe-style internal
# capitals. Those belong only to the titled/legal-role grammar below.
EN_NAME_TOKEN = (
    r"(?:[A-Z][a-z]+(?:-[A-Z][a-z]+)?|[A-Z]{2,}|"
    r"(?:O|D|Mc|Mac)['’][A-Z][a-z]+)"
)
EN_FULL_NAME = rf"{EN_NAME_TOKEN}(?:[ \t]+{EN_NAME_TOKEN}){{1,3}}"
EN_NAME_RE = re.compile(rf"(?<![A-Za-z])({EN_FULL_NAME})(?![A-Za-z])")

# Bounded tokens for courtesy-title / legal-role grammar only.
EN_NAME_PARTICLE = r"(?:[Dd]e|[Vv]an|[Vv]on|[Dd]a|[Dd]i|[Dd]el|[Ll]a|[Ll]e)"
# Mc/Mac+Capital first so McAuliffe is not consumed as Mc + leftover.
EN_SURNAME_TOKEN = (
    r"(?:"
    r"(?:Mc|Mac)[A-Z][a-z]+|"
    r"(?:O|D|Mc|Mac)['’][A-Z][a-z]+|"
    r"[A-Z][a-z]+(?:-[A-Z][a-z]+)?|"
    r"[A-Z]{2,}"
    r")"
)
EN_INITIAL_TOKEN = r"(?:[A-Z]\.?)"
EN_COMPACT_INITIALS_TOKEN = r"(?:[A-Z](?:\.?[A-Z]){1,2}\.?)"
EN_INITIALS_GROUP = (
    rf"(?:{EN_COMPACT_INITIALS_TOKEN}|"
    rf"{EN_INITIAL_TOKEN}(?:[ \t]+{EN_INITIAL_TOKEN}){{1,2}}|"
    rf"{EN_INITIAL_TOKEN})"
)
EN_SURNAME_PHRASE = rf"(?:{EN_NAME_PARTICLE}[ \t]+)?{EN_SURNAME_TOKEN}"
# Longest first: initials+surname, then existing full names, then surname-only.
EN_TITLED_NAME_BODY = (
    rf"(?:{EN_INITIALS_GROUP}[ \t]+{EN_SURNAME_PHRASE}|"
    rf"{EN_FULL_NAME}|"
    rf"{EN_NAME_PARTICLE}[ \t]+{EN_SURNAME_TOKEN}|"
    rf"{EN_SURNAME_TOKEN})"
)
EN_TITLED_NAME_RE = re.compile(rf"(?<![A-Za-z])({EN_TITLED_NAME_BODY})(?![A-Za-z])")

_BLOCKED_TITLED_WORDS = frozenset(STREET_TYPES) | frozenset(COMPANY_SUFFIXES) | frozenset(
    {
        "court",
        "tribunal",
        "tribunals",
        "ministry",
        "department",
        "rules",
        "procedure",
        "salon",
        "corporation",
        "incorporated",
        "counsel",
        "solicitor",
        "barrister",
        "attorney",
        "lawyer",
        "advocate",
        "representative",
        "judgment",
        "judgement",
        "application",
        "notice",
        "hearing",
        "decision",
        "reasons",
    }
)

_HEADING_GLUE = frozenset({"on", "of", "the", "for", "by", "to", "in", "a", "an", "and"})
_GENERIC_COURT_TERMS = frozenset({"tribunal", "tribunals", "court", "courts"})
_LEADING_DETERMINERS = frozenset({"the", "a", "an", "this", "that"})

_EN_POSSESSIVE = re.compile(r"^(.+[^'’])['’]s$", re.IGNORECASE)
_WS = re.compile(r"\s+")

_STREET_AFTER_COURT = re.compile(
    r"(?i)^\s+(?:road|rd|street|st|avenue|ave|lane|ln|drive|way|place|pl)\b"
)


def fold_en(value: str) -> str:
    return _WS.sub(" ", value.casefold().strip())


def strip_en_possessive(value: str) -> str:
    """Strip a trailing English 's only. Leaves O'Connor / Anne-Marie intact."""
    stripped = value.strip()
    match = _EN_POSSESSIVE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def evidence(*pairs: tuple[str, int]) -> list[dict]:
    return [
        {"code": code, "weight": weight, "source": EvidenceSource.CONTEXT}
        for code, weight in pairs
    ]


def seed(
    *pairs: tuple[str, int],
    source: str = EvidenceSource.STRUCTURE,
) -> list[dict]:
    return [{"code": code, "weight": weight, "source": source} for code, weight in pairs]


def alt_pattern(labels: Iterable[str]) -> str:
    parts = sorted((re.escape(item) for item in labels), key=len, reverse=True)
    return "|".join(parts)


_TRADE_MARKER_BODY = alt_pattern(TRADING_AS_MARKERS)
_TRADE_LEFT = re.compile(rf"(?i)(?:{_TRADE_MARKER_BODY})[ \t]+(?:the[ \t]+)?$")
_TRADE_IN_VALUE = re.compile(rf"(?i)(?<![A-Za-z])(?:{_TRADE_MARKER_BODY})(?![A-Za-z])")


def is_determiner_plus_court_head(value: str) -> bool:
    """True for 'the Employment' / 'the High' — not a standalone person name.

    Does not blacklist the court-head token itself (Mr Employment still stands).
    """
    tokens = fold_en(value).split()
    return (
        len(tokens) == 2
        and tokens[0] in _LEADING_DETERMINERS
        and tokens[1] in COURT_HEAD_ADJECTIVES
    )


def looks_like_person_name(value: str) -> bool:
    surface = strip_en_possessive(value.strip().strip(",.;:"))
    if not EN_NAME_RE.fullmatch(surface):
        return False
    folded = fold_en(surface)
    if is_determiner_plus_court_head(surface):
        return False
    if is_court_surface(folded) or is_institution_surface(folded) or is_company_surface(surface):
        return False
    if is_generic_court_term(surface) or looks_like_legal_heading(surface):
        return False
    if is_standalone_legal_role(surface) or is_representation_status(surface):
        return False
    tokens = surface.split()
    if any(fold_en(token).rstrip(".") in PERSON_TITLES for token in tokens):
        return False
    return 2 <= len(tokens) <= 4


def titled_name_has_initials(value: str) -> bool:
    surface = strip_en_possessive(value.strip().strip(",.;:"))
    if not surface:
        return False
    return bool(
        re.fullmatch(rf"{EN_INITIALS_GROUP}[ \t]+{EN_SURNAME_PHRASE}", surface)
    )


def looks_like_titled_name_body(value: str) -> bool:
    """True for title/role name bodies, including initials and a single surname.

    Not a bare-capitalization detector. Callers must already have title or
    legal-role evidence.
    """
    surface = strip_en_possessive(value.strip().strip(",.;:"))
    if not surface:
        return False
    if looks_like_person_name(surface):
        return True
    if not re.fullmatch(EN_TITLED_NAME_BODY, surface):
        return False
    if is_determiner_plus_court_head(surface):
        return False
    if is_court_surface(surface) or is_institution_surface(surface) or is_company_surface(surface):
        return False
    if is_generic_court_term(surface) or looks_like_legal_heading(surface):
        return False
    if is_standalone_legal_role(surface) or is_representation_status(surface):
        return False
    tokens = surface.split()
    if any(fold_en(token).rstrip(".") in PERSON_TITLES for token in tokens):
        return False
    if any(fold_en(token).rstrip(".") in _BLOCKED_TITLED_WORDS for token in tokens):
        return False
    return 1 <= len(tokens) <= 5


def is_known_en_first_name(value: str) -> bool:
    return fold_en(value).rstrip(".") in ENGLISH_FIRST_NAMES


def is_generic_court_term(value: str) -> bool:
    tokens = [token for token in fold_en(value).split() if token not in {"the", "this", "that", "a", "an"}]
    return len(tokens) == 1 and tokens[0] in _GENERIC_COURT_TERMS


def looks_like_legal_heading(value: str) -> bool:
    """True for procedural heading lines, not for ordinary ALLCAPS company names."""
    tokens = [token.strip(",.;:") for token in value.split() if token.strip(",.;:")]
    if len(tokens) < 2:
        return False
    folded = [fold_en(token) for token in tokens]
    if not any(token in LEGAL_HEADING_CUES for token in folded):
        return False
    heading_like = all(
        token.isupper() or fold_en(token) in _HEADING_GLUE or token[:1].isupper()
        for token in tokens
    )
    return heading_like


_LEADING_ROLE_DETERMINERS = frozenset({"the", "a", "an"})


def is_representation_status(value: str) -> bool:
    """True for a complete representation-status surface such as 'in person'."""
    return fold_en(value).replace(".", "") in REPRESENTATION_STATUS


def is_standalone_legal_role(value: str) -> bool:
    """True for a complete litigation-role surface, not a token blacklist.

    Matches Claimant, the claimant, First Respondent, the first respondent,
    2nd Respondent, and Employment Judge. Does not match First, Respondent,
    or First Smith standing alone.
    """
    tokens = fold_en(value).replace(".", "").split()
    if not tokens:
        return False
    if tokens[0] in _LEADING_ROLE_DETERMINERS:
        tokens = tokens[1:]
        if not tokens:
            return False
    had_ordinal = tokens[0] in LITIGATION_ORDINALS
    if had_ordinal:
        tokens = tokens[1:]
        if not tokens:
            return False
    surface = " ".join(tokens)
    if had_ordinal:
        return surface in PARTY_ROLE_WORDS
    return (
        surface in PARTY_ROLE_WORDS
        or surface in LEGAL_ROLE_WORDS
        or surface in DECISION_ROLE_LABELS
    )


def contains_trading_as(value: str) -> bool:
    return bool(_TRADE_IN_VALUE.search(value))


def in_trading_as_context(text: str, start: int) -> bool:
    left = text[max(0, start - 48) : start]
    return bool(_TRADE_LEFT.search(left))


def is_court_surface(value: str) -> bool:
    folded = fold_en(value)
    if is_generic_court_term(folded):
        return True
    return any(phrase == folded or folded.endswith(f" {phrase}") for phrase in COURT_PHRASES)


def is_institution_surface(value: str) -> bool:
    folded = fold_en(value)
    return any(phrase in folded for phrase in INSTITUTION_PHRASES)


def is_company_surface(value: str) -> bool:
    folded = fold_en(value)
    return any(
        re.search(rf"(?<![a-z]){re.escape(suffix)}(?:[.]|$)", folded)
        for suffix in COMPANY_SUFFIXES
    )


def court_followed_by_street(text: str, end: int) -> bool:
    return bool(_STREET_AFTER_COURT.match(text[end:end + 24]))


def plausible_ref_value(value: str) -> bool:
    compact = value.strip().rstrip(".,;:")
    if not compact or compact in {"1", "2", "3"}:
        return False
    if re.fullmatch(r"\d{1,2}\.", value.strip()):
        return False
    if re.fullmatch(r"\d{4}", compact):
        return False
    if re.fullmatch(r"\d{1,2}/\d{1,2}", compact):
        return False
    if re.fullmatch(r"\d{1,3}", compact):
        return False
    # Ordinary English words are not legal references.
    if re.fullmatch(r"[A-Za-z]+", compact):
        return False
    if not re.search(r"\d", compact) and not re.search(r"[./\-]", compact):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9./\-]{2,40}", compact))


__all__ = [
    "EN_COMPACT_INITIALS_TOKEN",
    "EN_FULL_NAME",
    "EN_INITIALS_GROUP",
    "EN_INITIAL_TOKEN",
    "EN_NAME_PARTICLE",
    "EN_NAME_RE",
    "EN_NAME_TOKEN",
    "EN_SURNAME_PHRASE",
    "EN_SURNAME_TOKEN",
    "EN_TITLED_NAME_BODY",
    "EN_TITLED_NAME_RE",
    "Evidence",
    "alt_pattern",
    "court_followed_by_street",
    "evidence",
    "contains_trading_as",
    "fold_en",
    "in_trading_as_context",
    "is_company_surface",
    "is_court_surface",
    "is_determiner_plus_court_head",
    "is_generic_court_term",
    "is_institution_surface",
    "is_known_en_first_name",
    "is_representation_status",
    "is_standalone_legal_role",
    "looks_like_legal_heading",
    "looks_like_person_name",
    "looks_like_titled_name_body",
    "make_candidate",
    "plausible_ref_value",
    "seed",
    "strip_en_possessive",
    "titled_name_has_initials",
]
