"""English-General composite address candidates. Court context beats street 'Court'."""

from __future__ import annotations

import re

from app.detectors.en.common import (
    alt_pattern,
    fold_en,
    is_court_surface,
    make_candidate,
    seed,
)
from app.detectors.en.vocab import ADDRESS_LABELS, POSTAL_LABELS, STREET_TYPES, UNIT_TYPES
from app.detectors.registry import PageText
from app.detectors.scoring.exclusions import is_at_line_start
from app.domain.models import EntityCandidate, EntityType

_STREET = alt_pattern(STREET_TYPES)
_UNIT = alt_pattern(UNIT_TYPES)
_LABEL = alt_pattern(ADDRESS_LABELS)
_POSTAL_LABEL = alt_pattern(POSTAL_LABELS)
# Title-case / ALLCAPS street words. Must not use IGNORECASE: otherwise
# "did not place" and "in which the Court" look like numbered streets.
_STREET_WORD = r"(?:[A-Z][a-z0-9'’.\-]+|[A-Z]{2,})"
_NUMBERED = re.compile(
    rf"(?<!\w)(?P<span>(?:(?P<unit>(?i:{_UNIT}))\s+\d+[A-Za-z]?,?\s+)?"
    rf"(?P<num>\d+[A-Za-z]?)"
    rf"[ \t]+"
    rf"(?P<street>{_STREET_WORD}(?:[ \t]+{_STREET_WORD}){{0,3}})"
    rf"[ \t]+"
    rf"(?P<type>(?i:{_STREET}))"
    rf"(?:,\s*{_STREET_WORD}(?:[ \t]+{_STREET_WORD}){{0,2}})?"
    rf")(?!\w)"
)
_LABELED = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_LABEL})\s*[:\-–]\s*(?P<value>[^\n]{{6,160}})"
)
_POSTAL = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_POSTAL_LABEL})\s*[:\-–]?\s*(?P<value>[A-Za-z0-9][A-Za-z0-9 \-]{{2,12}})"
)
_COURT_STREET = frozenset({"court", "ct"})


def _house_number_is_paragraph_layout(page: PageText, match: re.Match[str]) -> bool:
    """True when a line-start 1–3 digit marker is joined to the next prose line."""
    num = match.group("num")
    if not re.fullmatch(r"\d{1,3}", num):
        return False
    if not is_at_line_start(page.text, match.start("num")):
        return False
    between = page.text[match.end("num") : match.start("street")]
    return any(ch in between for ch in "\n\r")


def _court_token_is_institution(street: str, stype: str) -> bool:
    if fold_en(stype) not in _COURT_STREET:
        return False
    return is_court_surface(f"{street} {stype}") or fold_en(street) in {
        "high",
        "supreme",
        "district",
        "county",
        "family",
        "crown",
        "appeal",
    }


def parse_addresses(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()

    def take(item: EntityCandidate) -> None:
        key = (item.start, item.end)
        if key in seen:
            return
        seen.add(key)
        found.append(item)

    for match in _NUMBERED.finditer(page.text):
        if _house_number_is_paragraph_layout(page, match):
            continue
        if _court_token_is_institution(match.group("street"), match.group("type")):
            continue
        span = match.group("span").strip(" ,")
        extra = seed(("en_address_structure", 5))
        if match.group("unit"):
            extra = extra + seed(("en_address_unit", 2))
        take(
            make_candidate(
                page,
                text=span,
                local_start=match.start("span"),
                local_end=match.start("span") + len(span),
                entity_type=EntityType.ADDRESS,
                detector="EN_ADDRESS",
                reason="English house-number + street-type address.",
                validated=False,
                attributes={"source": "en_address", "evidence": extra},
            )
        )
    for match in _LABELED.finditer(page.text):
        value = match.group("value").strip()
        if len(value) < 6 or is_court_surface(value):
            continue
        extra = seed(("en_address_label", 5), ("en_address_structure", 2))
        take(
            make_candidate(
                page,
                text=value,
                local_start=match.start("value"),
                local_end=match.start("value") + len(value),
                entity_type=EntityType.ADDRESS,
                detector="EN_ADDRESS",
                reason="English address label with a structured value.",
                validated=False,
                attributes={"source": "en_address", "evidence": extra},
            )
        )
    for match in _POSTAL.finditer(page.text):
        value = match.group("value").strip()
        if re.fullmatch(r"\d{1,3}", value):
            continue
        take(
            make_candidate(
                page,
                text=value,
                local_start=match.start("value"),
                local_end=match.end("value"),
                entity_type=EntityType.POSTAL_CODE,
                detector="EN_POSTAL_CODE",
                reason="Postal-code-like value under an English postcode/ZIP label.",
                validated=False,
                attributes={
                    "source": "en_postal",
                    "evidence": seed(("en_address_label", 6)),
                },
            )
        )
    return found
