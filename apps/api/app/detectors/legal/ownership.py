"""Ownership / registered-to relation parser."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate, relation
from app.detectors.legal.names import BARE_NAME_TOKEN, clipped_name_span
from app.detectors.registry import PageText, IBAN, TR_PHONE, _fit_iban
from app.domain.models import EntityCandidate, EntityType

_NAME_GAP = r"[\s\u00a0\u00ad\u2000-\u200d\u202f]{0,40}"
_NAME_CHUNK = rf"{BARE_NAME_TOKEN}(?:{_NAME_GAP}{BARE_NAME_TOKEN}){{1,3}}"
_OBJECT = (
    r"(?P<object>iban(?:\s+numara(?:sı|si))?|banka\s+hesab(?:ı|i)|hesap|"
    r"gsm(?:\s+hattı|\s+hatti)?|telefon(?:\s+numara(?:sı|si))?|"
    r"ödeme\s+kartı|odeme\s+karti|kredi\s+kartı|kredi\s+karti|kart|"
    r"plaka|araç|arac|abone(?:\s+no(?:su)?)?|müşteri\s+no(?:su)?|musteri\s+no(?:su)?)"
)

_PERSON_REGISTERED = re.compile(
    rf"(?P<name>{_NAME_CHUNK})\s+(?i:adına\s+kayıtlı)\s+(?i:{_OBJECT})"
)
_OBJECT_REGISTERED = re.compile(
    rf"(?i:{_OBJECT})\s+(?P<name>{_NAME_CHUNK})\s+(?i:adına\s+kayıtlı)"
)
_PERSON_AIT = re.compile(
    rf"(?P<name>{_NAME_CHUNK})['’](?P<suf>ye|ya|e|a)\s+(?i:ait)\s+(?i:{_OBJECT})"
)
_HOLDER = re.compile(
    rf"(?i:(?P<kind>hesap|hat|kart))\s+(?i:sahibi)\s+(?P<name>{_NAME_CHUNK})"
)

_OBJECT_TYPE = {
    "iban": EntityType.IBAN,
    "hesap": EntityType.BANK_ACCOUNT,
    "banka": EntityType.BANK_ACCOUNT,
    "gsm": EntityType.PHONE_NUMBER,
    "telefon": EntityType.PHONE_NUMBER,
    "kart": EntityType.CREDIT_CARD,
    "plaka": EntityType.VEHICLE_PLATE,
    "araç": EntityType.VEHICLE_PLATE,
    "arac": EntityType.VEHICLE_PLATE,
    "abone": EntityType.CUSTOMER_ID,
    "müşteri": EntityType.CUSTOMER_ID,
    "musteri": EntityType.CUSTOMER_ID,
}

_REL_KIND = {
    EntityType.IBAN: "REGISTERED_TO",
    EntityType.BANK_ACCOUNT: "ACCOUNT_HOLDER",
    EntityType.PHONE_NUMBER: "PHONE_HOLDER",
    EntityType.CREDIT_CARD: "OWNS",
    EntityType.VEHICLE_PLATE: "OWNS",
    EntityType.CUSTOMER_ID: "ACCOUNT_HOLDER",
}


def _object_type(label: str) -> EntityType:
    folded = label.casefold()
    for key, entity_type in _OBJECT_TYPE.items():
        if folded.startswith(key) or key in folded:
            return entity_type
    return EntityType.OTHER_IDENTIFIER


def _nearby_object(text: str, center: int, entity_type: EntityType) -> tuple[int, int, str] | None:
    shift = max(0, center - 80)
    window = text[shift : center + 80]
    if entity_type in {EntityType.IBAN, EntityType.BANK_ACCOUNT}:
        match = IBAN.search(window)
        if match:
            fitted = _fit_iban(match)
            if fitted:
                value, start, end = fitted
                return shift + start, shift + end, value
    if entity_type == EntityType.PHONE_NUMBER:
        match = TR_PHONE.search(window)
        if match:
            return shift + match.start(), shift + match.end(), match.group(0)
    return None


def _emit_person(page: PageText, name_raw: str, start: int, rel: str, obj_type: EntityType) -> EntityCandidate | None:
    clipped = clipped_name_span(name_raw, start)
    if clipped is None:
        return None
    name, local_start, local_end = clipped
    return make_candidate(
        page,
        text=name,
        local_start=local_start,
        local_end=local_end,
        entity_type=EntityType.PERSON_NAME,
        detector="TR_OWNERSHIP",
        reason="Ownership / registered-to grammar.",
        attributes={"relationship": rel, "object_type": obj_type.value, "source": "ownership"},
    )


def parse_ownership(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int, str]] = set()

    def add(person: EntityCandidate | None, obj_type: EntityType, center: int, rel: str) -> None:
        if person is None:
            return
        key = (person.start, person.end, person.detector)
        if key in seen:
            return
        seen.add(key)
        nearby = _nearby_object(page.text, center, obj_type)
        if nearby:
            local_start, local_end, raw = nearby
            obj = make_candidate(
                page,
                text=raw,
                local_start=local_start,
                local_end=local_end,
                entity_type=obj_type,
                detector="TR_OWNERSHIP",
                reason="Object linked by ownership grammar.",
                attributes={"relationship": rel, "source": "ownership"},
                relations=[relation(rel, target=person)],
            )
            found.append(obj)
            found.append(
                person.model_copy(update={"relations": [relation(rel, target=obj)]})
            )
            return
        found.append(
            person.model_copy(update={"relations": [relation(rel, label=obj_type.value)]})
        )

    for match in _PERSON_REGISTERED.finditer(page.text):
        obj_type = _object_type(match.group("object"))
        add(
            _emit_person(page, match.group("name"), match.start("name"), "REGISTERED_TO", obj_type),
            obj_type,
            match.start(),
            "REGISTERED_TO",
        )
    for match in _OBJECT_REGISTERED.finditer(page.text):
        obj_type = _object_type(match.group("object"))
        add(
            _emit_person(page, match.group("name"), match.start("name"), "REGISTERED_TO", obj_type),
            obj_type,
            match.start(),
            "REGISTERED_TO",
        )
    for match in _PERSON_AIT.finditer(page.text):
        obj_type = _object_type(match.group("object"))
        add(
            _emit_person(page, match.group("name"), match.start("name"), "OWNS", obj_type),
            obj_type,
            match.start(),
            "OWNS",
        )
    for match in _HOLDER.finditer(page.text):
        kind = match.group("kind").casefold()
        obj_type = _OBJECT_TYPE.get(kind, EntityType.OTHER_IDENTIFIER)
        rel = _REL_KIND.get(obj_type, "ACCOUNT_HOLDER")
        add(
            _emit_person(page, match.group("name"), match.start("name"), rel, obj_type),
            obj_type,
            match.start(),
            rel,
        )
    return found
