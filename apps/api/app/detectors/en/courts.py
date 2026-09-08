"""English-General court / tribunal institution names. No jurisdiction claim."""

from __future__ import annotations

import re

from app.detectors.en.common import (
    alt_pattern,
    court_followed_by_street,
    fold_en,
    make_candidate,
    seed,
)
from app.detectors.en.vocab import COURT_HEAD_ADJECTIVES, COURT_PHRASES
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_PHRASE_BODY = alt_pattern(COURT_PHRASES)
_KNOWN = re.compile(rf"(?i)(?<![A-Za-z])(?P<span>(?:the\s+)?(?:{_PHRASE_BODY}))(?![A-Za-z])")
_HEADING = re.compile(
    r"(?i)(?<![A-Za-z])(?P<span>(?:in\s+the|before\s+the)\s+"
    r"(?:[A-Z][A-Za-z]+\s+){0,4}(?:court|tribunal)(?:\s+of\s+[A-Z][A-Za-z]+){0,3})"
)
_TYPED = re.compile(
    r"(?i)(?<![A-Za-z])(?P<span>(?:the\s+)?(?P<head>[A-Z][A-Za-z]+)"
    r"(?:\s+[A-Z][A-Za-z]+){0,2}\s+(?P<kind>court|tribunal))(?![A-Za-z])"
)
_STOP_HEAD = frozenset(
    {
        "the",
        "this",
        "that",
        "any",
        "each",
        "said",
        "present",
        "trial",
        "open",
        "closed",
        "lower",
        "upper",
        "tennis",
        "food",
        "basket",
    }
)


def _emit(page: PageText, span: str, start: int, end: int) -> EntityCandidate | None:
    if court_followed_by_street(page.text, end):
        return None
    text = re.sub(r"^the\s+", "", span, flags=re.IGNORECASE).strip()
    lead = span.lower().find(text.lower())
    local_start = start + max(lead, 0)
    return make_candidate(
        page,
        text=page.text[local_start:end],
        local_start=local_start,
        local_end=end,
        entity_type=EntityType.COURT_NAME,
        detector="EN_COURT",
        reason="English court or tribunal structure.",
        attributes={
            "org_kind": "COURT",
            "source": "en_court",
            "evidence": seed(("en_court_structure", 6)),
        },
    )


def parse_courts(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()

    def take(item: EntityCandidate | None) -> None:
        if item is None:
            return
        key = (item.start, item.end)
        if key in seen:
            return
        for existing_start, existing_end in list(seen):
            if item.start < existing_end and item.end > existing_start:
                if (item.end - item.start) <= (existing_end - existing_start):
                    return
        seen.add(key)
        found.append(item)

    for match in _KNOWN.finditer(page.text):
        take(_emit(page, match.group("span"), match.start("span"), match.end("span")))
    for match in _HEADING.finditer(page.text):
        take(_emit(page, match.group("span"), match.start("span"), match.end("span")))
    for match in _TYPED.finditer(page.text):
        head = fold_en(match.group("head"))
        if head in _STOP_HEAD:
            continue
        if head not in COURT_HEAD_ADJECTIVES and not re.search(
            r"(?i)\b(?:in\s+the|before\s+the)\b",
            page.text[max(0, match.start() - 24) : match.start()],
        ):
            continue
        take(_emit(page, match.group("span"), match.start("span"), match.end("span")))
    return found
