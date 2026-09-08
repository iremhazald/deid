"""Reusable negative-evidence helpers. Shared across scored categories."""

from __future__ import annotations

import re

from app.detectors.legal.names import (
    is_legal_role_label,
    is_non_person_surface,
    is_procedural_notice_surface,
    is_workplace_or_job_title,
)
from app.detectors.textutil import fold_tr_identity

_DATE_LIKE = re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b")
_CASE_LIKE = re.compile(r"\b\d{4}\s*/\s*\d+\b")
_LIST_MARKER = re.compile(r"^\s*\d+\s*[-–.)]\s*$")
# Hierarchical paragraph / subparagraph markers: 67.8, 83.4., 102.4.1
# Components stay short so 1400945.2017 is not treated as structure.
_PARAGRAPH_NUMBER = re.compile(r"^\d{1,3}(?:\.\d{1,3}){1,3}\.?$")
_EXPLICIT_REF_SEP = re.compile(r"[:\-–]\s*$")
_LONG_DIGIT_RUN = re.compile(r"\d(?:[\s\-./]?\d){11,}")
_MONEY = re.compile(
    r"(?i)\b\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?\s*(?:TL|TRY|Türk\s+Liras[ıi])\b"
)
_FRACTION = re.compile(r"\b\d+\s*/\s*\d+\b")

_MONTHS = frozenset(
    {
        "ocak",
        "subat",
        "mart",
        "nisan",
        "mayis",
        "haziran",
        "temmuz",
        "agustos",
        "eylul",
        "ekim",
        "kasim",
        "aralik",
    }
)

_DATE_CONTEXT = frozenset(
    {
        "durusma",
        "karar tarihi",
        "teblig tarihi",
        "sozlesme tarihi",
        "basvuru tarihi",
        "olay tarihi",
        "suc tarihi",
        "islem tarihi",
        "duzenleme tarihi",
        "hearing date",
        "decision date",
        "order date",
        "filing date",
        "service date",
        "contract date",
        "execution date",
    }
)

_BIRTH_CONTEXT = frozenset(
    {
        "dogum",
        "dogumlu",
        "dogum tarihi",
        "nufus",
        "kimlik",
        "date of birth",
        "birth date",
        "dob",
        "d.o.b",
        "born",
        "birthplace",
        "place of birth",
    }
)

_COMPANY_SUFFIX_RE = re.compile(
    r"(?i)(?<!\w)(?:a\.?\s*[sş]\.?|ltd\.?(?:\s*[şs]ti\.?)?|limited(?:\s+şirketi)?|şirketi|"
    r"llc|llp|inc(?:orporated)?|corp(?:oration)?|p\.?l\.?c\.?)\b"
)

_INSTITUTION_STEMS = frozenset(
    {
        "mudurluk",
        "mudurlugu",
        "bakanlik",
        "bakanligi",
        "savcilik",
        "savciligi",
        "kaymakamlik",
        "valilik",
        "belediye",
        "emniyet",
        "jandarma",
        "adliye",
        "universite",
        "hastane",
        "bankasi",
        "ministry of justice",
        "department of justice",
        "legal department",
        "human rights act",
        "civil procedure rules",
        "united kingdom",
        "united states",
    }
)

_COURT_PHRASES = frozenset(
    {
        "mahkeme",
        "mahkemesi",
        "mahkemesine",
        "hakimligi",
        "hakimligine",
        "dairesi",
        "dairesine",
        "yargitay",
        "danistay",
        "anayasa mahkemesi",
        "nobetci mahkeme",
        "nobetci",
        "supreme court",
        "high court",
        "court of appeal",
        "court of appeals",
        "district court",
        "circuit court",
        "county court",
        "family court",
        "commercial court",
        "civil court",
        "criminal court",
        "employment tribunals",
        "employment tribunal",
        "employment court",
        "labour court",
        "administrative court",
        "constitutional court",
        "arbitration tribunal",
    }
)

_LEGAL_FIELD = frozenset(
    {
        "is hukuku",
        "hukuku",
        "hukukuna",
        "konu",
        "konusu",
        "teblig",
        "teblige",
        "tebellug",
        "tebellugu",
        "muvekkil",
        "vekili",
        "uets",
    }
)


def fold(value: str) -> str:
    return fold_tr_identity(value)


def is_date_like(value: str) -> bool:
    return bool(_DATE_LIKE.search(value))


def is_case_reference(value: str, nearby: str = "") -> bool:
    if not _CASE_LIKE.search(value) and not _CASE_LIKE.search(nearby):
        return False
    window = fold(f"{nearby} {value}")
    return any(
        token in window
        for token in ("esas", "karar", "dosya", "sorusturma", "talimat", "iddianame")
    )


def is_list_marker(value: str) -> bool:
    return bool(_LIST_MARKER.match(value.strip()))


def looks_like_paragraph_number(value: str) -> bool:
    """True for hierarchical decimal markers, not for dotted case/file values."""
    return bool(_PARAGRAPH_NUMBER.fullmatch(value.strip()))


def is_at_line_start(text: str, start: int) -> bool:
    if start <= 0:
        return True
    index = start - 1
    while index >= 0 and text[index] in " \t":
        index -= 1
    return index < 0 or text[index] in "\n\r"


def has_same_line_explicit_ref_separator(text: str, start: int) -> bool:
    left = text[max(0, start - 16) : start]
    if "\n" in left or "\r" in left:
        return False
    return bool(_EXPLICIT_REF_SEP.search(left))


def is_paragraph_number_marker(value: str, text: str = "", start: int | None = None) -> bool:
    """Paragraph structure, not a sensitive identifier.

    Line-start / paragraph-start hierarchical decimals are document markers.
    The same digits remain a legal reference only when an explicit same-line
    label separator (``Case No: 67.8``) introduces them. This is positional:
    the exact surfaces 67.8 / 83.4 are not blacklisted.
    """
    if not looks_like_paragraph_number(value):
        return False
    if start is None or not text:
        return True
    if is_at_line_start(text, start):
        return True
    return not has_same_line_explicit_ref_separator(text, start)


def starts_with_paragraph_number(value: str) -> bool:
    token = value.lstrip()
    # Judgment paragraphs are often "19." / "44." — one integer and a full stop.
    if re.fullmatch(r"\d{1,3}\.", token.strip()):
        return True
    match = re.match(r"\d{1,3}(?:\.\d{1,3}){1,3}\.?", token)
    if not match:
        return False
    end = match.end()
    return end == len(token) or token[end] in " \t."


def is_long_numeric_run(value: str) -> bool:
    compact = re.sub(r"\D", "", value)
    return len(compact) >= 12 or bool(_LONG_DIGIT_RUN.search(value))


def is_month_name(value: str) -> bool:
    tokens = fold(value).replace(".", "").split()
    return any(token in _MONTHS for token in tokens)


def is_money_context(value: str) -> bool:
    return bool(_MONEY.search(value))


def is_fraction_or_math(value: str, nearby: str = "") -> bool:
    window = f"{nearby} {value}"
    if is_case_reference(value, nearby):
        return False
    return bool(_FRACTION.search(window)) and not is_date_like(window)


_EN_HEADING_CUES = frozenset(
    {
        "judgment",
        "judgement",
        "reasons",
        "notice",
        "order",
        "decision",
        "application",
        "hearing",
        "directions",
        "ruling",
    }
)
_EN_HEADING_GLUE = frozenset({"on", "of", "the", "for", "by", "to", "in", "a", "an", "and"})
_EN_ROLE_WORDS = frozenset(
    {
        "counsel",
        "solicitor",
        "barrister",
        "attorney",
        "lawyer",
        "advocate",
        "representative",
    }
)


def is_legal_heading_surface(value: str) -> bool:
    tokens = [token.strip(",.;:") for token in value.split() if token.strip(",.;:")]
    if len(tokens) < 2:
        return False
    folded = [fold(token) for token in tokens]
    if not any(token in _EN_HEADING_CUES for token in folded):
        return False
    return all(
        token.isupper() or fold(token) in _EN_HEADING_GLUE or token[:1].isupper()
        for token in tokens
    )


def is_legal_role_word(value: str) -> bool:
    if is_legal_role_label(value):
        return True
    try:
        from app.detectors.en.common import is_representation_status, is_standalone_legal_role
    except ImportError:
        is_representation_status = None  # type: ignore[assignment]
        is_standalone_legal_role = None  # type: ignore[assignment]
    if is_standalone_legal_role is not None and is_standalone_legal_role(value):
        return True
    if is_representation_status is not None and is_representation_status(value):
        return True
    tokens = fold(value).replace(".", "").split()
    return len(tokens) == 1 and tokens[0] in _EN_ROLE_WORDS


def is_court_phrase(value: str) -> bool:
    folded = fold(value)
    return any(phrase in folded for phrase in _COURT_PHRASES)


def is_company_phrase(value: str) -> bool:
    return bool(_COMPANY_SUFFIX_RE.search(value))


def is_institution_phrase(value: str) -> bool:
    folded = fold(value)
    if is_workplace_or_job_title(value) or is_non_person_surface(value):
        return True
    return any(stem in folded for stem in _INSTITUTION_STEMS)


def is_legal_field_phrase(value: str) -> bool:
    if is_procedural_notice_surface(value):
        return True
    folded = fold(value)
    return bool(
        re.search(
            r"(?<!\w)(?:is\s+hukuku|hukuku|hukukuna|konusu|konu|"
            r"teblig|teblige|tebellug|tebellugu|"
            r"muvekkil|vekili|uets)(?!\w)",
            folded,
        )
    )


def is_birth_context(value: str) -> bool:
    folded = fold(value)
    return any(cue in folded for cue in _BIRTH_CONTEXT)


def is_non_birth_date_context(value: str) -> bool:
    folded = fold(value)
    if is_birth_context(folded):
        return False
    return any(cue in folded for cue in _DATE_CONTEXT)


def looks_like_hearing_date(nearby: str) -> bool:
    folded = fold(nearby)
    return "durusma" in folded and "dogum" not in folded
