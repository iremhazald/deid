"""Bounded English NER-only LOCATION contradiction cues.

These are contextual or closed legal/structural classes, not a surface
blacklist. They apply only to LOCAL_NER_EN LOCATION candidates.
PERSON scoring, Turkish NER, and deterministic detectors are unchanged.
"""

from __future__ import annotations

import re

from app.detectors.scoring.context import DocumentIndex
from app.detectors.scoring.exclusions import is_legal_role_word

_WS = re.compile(r"[\s\u00a0\u00ad\u2000-\u200d\u202f]+")
_GEO_SHORT = frozenset({"uk", "us", "eu", "gb"})
_PROPERTY_ROLES = frozenset({"landlord", "tenant"})
_DOCUMENT_PARTICIPLES = frozenset({"exhibited", "attached", "enclosed", "appended"})
_EXHIBIT_RIGHT = re.compile(
    r"^(?:d\s+)?(?:documents?|exhibits?|bundle|appendix|annex)\b",
    re.IGNORECASE,
)
_PRODUCT_RIGHT = re.compile(
    r"^\s*(?:&|and)\s+[A-Z][A-Za-z0-9'’&.-]+(?:\s+\w+){0,3}\s+"
    r"(?:[Pp]roducts?|[Bb]ooks?|[Rr]ange|[Ss]eries|[Ww]ebsites?|"
    r"[Ss]ales|[Pp]ublications?|[Rr]esources?)\b"
)
_CASE_V_RIGHT = re.compile(r"^\s+v(?:s)?\.?[\sA-Z]")
_REPORT_NEAR = re.compile(
    r"\[\s*[12]\d{3}\s*\]|\b(?:UKEAT|UKSC|EWCA|EWHC|ICR|IRLR|WLR)\b"
)
_JUDGE_IN_LEFT = re.compile(r"(?i)(?:\bLJ|\bJ\.?|Lord Justice|Lady Justice)\s+in\s+$")
_STATUTE_LEFT = re.compile(r"(?i)(?:protection|provisions?|regulations?)\s+of\s+$")
_TEMPORAL_OF_LEFT = re.compile(r"(?i)(?:months?|years?|weeks?|days?)\s+of\s+$")
_INITIALS = re.compile(r"^[A-Z]{2}$")
_LOWER_WORD = re.compile(r"^[a-z][a-z\-]+$")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip()


def legal_role_location_surface(surface: str) -> bool:
    """Closed litigation / property-role labels are not geographic places."""
    folded = _norm(surface).casefold()
    if folded in _PROPERTY_ROLES:
        return True
    return is_legal_role_word(surface)


def exhibit_document_context(surface: str, right: str) -> bool:
    """'Exhibited documents (E15)' is an evidence label, not a place."""
    if _norm(surface).casefold() not in _DOCUMENT_PARTICIPLES:
        return False
    return bool(_EXHIBIT_RIGHT.match(_norm(right)))


def product_title_context(right: str) -> bool:
    """'Barney & Echo product' is a work/product title, not a GPE."""
    return bool(_PRODUCT_RIGHT.match(right))


def case_citation_context(surface: str, left: str, right: str) -> bool:
    """Case-name / report structure around the span, not live geography."""
    folded = f" {surface} "
    if re.search(r"\sv(?:s)?\.?\s", folded, re.IGNORECASE):
        return True
    if _CASE_V_RIGHT.match(right):
        return True
    if _JUDGE_IN_LEFT.search(left):
        return True
    near_right = right[:40]
    if _REPORT_NEAR.search(near_right):
        return True
    return False


def statute_or_event_context(surface: str, left: str) -> bool:
    """Uppercase statute short-forms and temporal events are not places."""
    if _STATUTE_LEFT.search(left) and surface.isupper() and 3 <= len(surface) <= 6:
        return True
    if _TEMPORAL_OF_LEFT.search(left):
        return True
    return False


def short_initials_not_geo(surface: str) -> bool:
    """Two-letter party/locator initials, excluding closed geo codes."""
    if not _INITIALS.match(surface.strip()):
        return False
    return surface.casefold() not in _GEO_SHORT


def lowercase_common_noun(surface: str) -> bool:
    """English place names in these documents are proper nouns."""
    return bool(_LOWER_WORD.match(surface.strip()))


def english_ner_location_contradiction(
    index: DocumentIndex, start: int, end: int, surface: str
) -> list[str]:
    """Return category-specific negative codes for one English NER LOCATION."""
    left = index.left_window(start, 48)
    right = index.right_window(end, 48)
    codes: list[str] = []
    if legal_role_location_surface(surface):
        codes.append("location_legal_role")
    if exhibit_document_context(surface, right):
        codes.append("location_exhibit_document")
    if product_title_context(right):
        codes.append("location_product_title")
    if case_citation_context(surface, left, right):
        codes.append("location_case_citation")
    if statute_or_event_context(surface, left):
        codes.append("location_statute_or_event")
    if short_initials_not_geo(surface):
        codes.append("location_party_initials")
    if lowercase_common_noun(surface):
        codes.append("location_lowercase_common")
    if index.overlaps_any(start, end, index.person_spans):
        codes.append("location_overlaps_person")
    if index.overlaps_any(start, end, index.org_spans):
        codes.append("location_overlaps_org")
    return codes
