"""Labeled English identity / contact / financial candidates. No universal validators."""

from __future__ import annotations

import re

from app.detectors.en.common import alt_pattern, make_candidate, seed
from app.detectors.en.vocab import (
    BIRTH_DATE_LABELS,
    BIRTH_PLACE_LABELS,
    FINANCIAL_LABELS,
    MONTHS,
    NATIONAL_ID_LABELS,
    NON_BIRTH_DATE_LABELS,
    PASSPORT_LABELS,
    PHONE_LABELS,
)
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_DATE = (
    r"(?P<date>\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|"
    r"Oct|Nov|Dec)\.?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{2,4})"
)
_BIRTH_LABEL = alt_pattern(BIRTH_DATE_LABELS)
_BIRTH_PLACE_LABEL = alt_pattern(BIRTH_PLACE_LABELS)
_NON_BIRTH = alt_pattern(NON_BIRTH_DATE_LABELS)
_PASSPORT_LABEL = alt_pattern(PASSPORT_LABELS)
_NID_LABEL = alt_pattern(NATIONAL_ID_LABELS)
_PHONE_LABEL = alt_pattern(PHONE_LABELS)
_FIN_LABEL = alt_pattern(label for label, _kind in FINANCIAL_LABELS)
_FIN_KIND = {label: kind for label, kind in FINANCIAL_LABELS}

_DOB = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_BIRTH_LABEL})\s*[:\-–]?\s*(?:on\s+)?{_DATE}"
)
_BORN_ON = re.compile(rf"(?i)\bborn\s+on\s+{_DATE}")
_POB = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_BIRTH_PLACE_LABEL})\s*[:\-–]?\s*"
    rf"(?P<place>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){{0,3}})"
)
_PASSPORT = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_PASSPORT_LABEL})\s*[:\-–#]?\s*"
    rf"(?P<value>[A-Z0-9][A-Z0-9\-]{{4,14}})"
)
_NID = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_NID_LABEL})\s*[:\-–]?\s*"
    rf"(?P<value>[A-Za-z0-9][A-Za-z0-9\-\s]{{4,24}})"
)
_PHONE = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_PHONE_LABEL})\s*[:\-–]?\s*"
    rf"(?P<value>\+?\d[\d\s()./\-]{{6,20}}\d)"
)
_FIN = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_FIN_LABEL})\s*[:\-–]?\s*"
    rf"(?P<value>[A-Za-z0-9][A-Za-z0-9\-\s]{{3,34}})"
)
_NON_BIRTH_NEAR = re.compile(rf"(?i)(?<![A-Za-z])(?:{_NON_BIRTH})\s*[:\-–]?\s*$")


def parse_identifiers(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []

    for match in _DOB.finditer(page.text):
        left = page.text[max(0, match.start() - 24) : match.start()]
        if _NON_BIRTH_NEAR.search(left):
            continue
        found.append(
            make_candidate(
                page,
                text=match.group("date"),
                local_start=match.start("date"),
                local_end=match.end("date"),
                entity_type=EntityType.DATE_OF_BIRTH,
                detector="EN_BIRTH",
                reason="Date under an English birth-date label.",
                attributes={
                    "kind": "DATE_OF_BIRTH",
                    "source": "en_birth",
                    "evidence": seed(("en_birth_context", 6)),
                },
            )
        )
    for match in _BORN_ON.finditer(page.text):
        found.append(
            make_candidate(
                page,
                text=match.group("date"),
                local_start=match.start("date"),
                local_end=match.end("date"),
                entity_type=EntityType.DATE_OF_BIRTH,
                detector="EN_BIRTH",
                reason="Date attached to 'born on'.",
                attributes={
                    "kind": "DATE_OF_BIRTH",
                    "source": "en_birth",
                    "evidence": seed(("en_birth_context", 6)),
                },
            )
        )
    for match in _POB.finditer(page.text):
        place = match.group("place").strip()
        if place.casefold() in MONTHS:
            continue
        found.append(
            make_candidate(
                page,
                text=place,
                local_start=match.start("place"),
                local_end=match.end("place"),
                entity_type=EntityType.BIRTH_PLACE,
                detector="EN_BIRTH",
                reason="Place under an English birthplace label.",
                attributes={
                    "kind": "BIRTH_PLACE",
                    "source": "en_birth",
                    "evidence": seed(("en_birth_context", 5)),
                },
            )
        )
    for match in _PASSPORT.finditer(page.text):
        found.append(
            make_candidate(
                page,
                text=match.group("value"),
                local_start=match.start("value"),
                local_end=match.end("value"),
                entity_type=EntityType.PASSPORT_NUMBER,
                detector="EN_PASSPORT",
                reason="Value under an English passport label.",
                validated=False,
                attributes={
                    "source": "en_passport",
                    "evidence": seed(("en_passport_label", 6)),
                },
            )
        )
    for match in _NID.finditer(page.text):
        value = match.group("value").strip()
        found.append(
            make_candidate(
                page,
                text=value,
                local_start=match.start("value"),
                local_end=match.start("value") + len(value),
                entity_type=EntityType.NATIONAL_ID,
                detector="EN_NATIONAL_ID",
                reason="Labeled English national/identity number without format validation.",
                validated=False,
                attributes={
                    "source": "en_national_id",
                    "evidence": seed(("en_national_id_label", 4)),
                },
            )
        )
    for match in _PHONE.finditer(page.text):
        found.append(
            make_candidate(
                page,
                text=match.group("value").strip(),
                local_start=match.start("value"),
                local_end=match.end("value"),
                entity_type=EntityType.PHONE_NUMBER,
                detector="EN_PHONE_CONTEXT",
                reason="Phone-like value under an English contact label.",
                validated=False,
                attributes={
                    "source": "en_phone",
                    "evidence": seed(("en_phone_label", 4)),
                },
            )
        )
    for match in _FIN.finditer(page.text):
        kind = _FIN_KIND.get(match.group("label").casefold(), "ACCOUNT")
        if kind == "IBAN":
            continue
        value = match.group("value").strip()
        entity_type = (
            EntityType.BANK_ACCOUNT if kind == "ACCOUNT" else EntityType.FINANCIAL_IDENTIFIER
        )
        found.append(
            make_candidate(
                page,
                text=value,
                local_start=match.start("value"),
                local_end=match.start("value") + len(value),
                entity_type=entity_type,
                detector="EN_ACCOUNT",
                reason="Labeled English financial identifier without format validation.",
                validated=False,
                attributes={
                    "source": "en_financial",
                    "financial_kind": kind,
                    "evidence": seed(("en_financial_label", 4)),
                },
            )
        )
    return found
