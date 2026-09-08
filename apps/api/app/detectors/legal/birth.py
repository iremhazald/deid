"""Birth info parser: DATE + PLACE + 'doğumlu'."""

from __future__ import annotations

import re

from app.detectors.gazetteers import TURKISH_CITIES, TURKISH_DISTRICTS
from app.detectors.legal.common import fold_tr, make_candidate, relation
from app.detectors.legal.names import _TOKEN
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

BIRTH_INFO_RE = re.compile(
    rf"\b(?P<date>\d{{1,2}}[./]\d{{1,2}}[./]\d{{4}})\s+"
    rf"(?P<place>{_TOKEN}(?:\s+{_TOKEN})?)\s+"
    rf"(?P<word>doğumlu|dogumlu)\b",
    re.IGNORECASE,
)

_PLACE_OK = {fold_tr(name) for name in TURKISH_CITIES | TURKISH_DISTRICTS}
_PLACE_STOP = frozenset(
    {
        "olan",
        "ise",
        "dava",
        "karar",
        "sanık",
        "davacı",
        "tarih",
        "kimlik",
    }
)


def _place_ok(value: str) -> bool:
    folded = fold_tr(value)
    if folded in _PLACE_STOP:
        return False
    if folded in _PLACE_OK:
        return True
    tokens = value.split()
    if not 1 <= len(tokens) <= 2:
        return False
    return all(token[0].isupper() or token.isupper() for token in tokens if token)


def parse_birth(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    for match in BIRTH_INFO_RE.finditer(page.text):
        place = match.group("place")
        if not _place_ok(place):
            continue
        dob = make_candidate(
            page,
            text=match.group("date"),
            local_start=match.start("date"),
            local_end=match.end("date"),
            entity_type=EntityType.DATE_OF_BIRTH,
            detector="TR_BIRTH_INFO",
            reason="Date attached to 'doğumlu'.",
            attributes={"kind": "DATE_OF_BIRTH"},
        )
        birthplace = make_candidate(
            page,
            text=place,
            local_start=match.start("place"),
            local_end=match.end("place"),
            entity_type=EntityType.BIRTH_PLACE,
            detector="TR_BIRTH_INFO",
            reason="Place attached to 'doğumlu'.",
            attributes={"kind": "BIRTH_PLACE"},
        )
        found.extend(
            (
                dob.model_copy(
                    update={"relations": [relation("BORN_IN", target=birthplace)]}
                ),
                birthplace.model_copy(
                    update={"relations": [relation("BIRTH_OF", target=dob)]}
                ),
            )
        )
    return found
