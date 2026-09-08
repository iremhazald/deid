"""Map provider NER labels onto existing DeID entity types.

V1 maps only PERSON / ORGANISATION / LOCATION (and GPE). Other model
labels are ignored so DATE, LAW, MONEY, NORP, etc. never become PII.
"""

from __future__ import annotations

from app.domain.models import EntityType

_PERSON = frozenset({"PER", "PERSON"})
_ORG = frozenset({"ORG", "ORGANISATION", "ORGANIZATION"})
_LOC = frozenset({"LOC", "LOCATION", "GPE"})


def normalize_ner_label(raw: str) -> str:
    label = raw.strip().upper()
    for prefix in ("B-", "I-", "E-", "S-", "L-", "U-"):
        if label.startswith(prefix):
            label = label[len(prefix) :]
            break
    if label.endswith("-PER"):
        return "PER"
    if label.endswith("-ORG"):
        return "ORG"
    if label.endswith("-LOC") or label.endswith("-GPE"):
        return "LOC"
    return label


def mapped_entity_type(raw_label: str) -> EntityType | None:
    label = normalize_ner_label(raw_label)
    if label in _PERSON:
        return EntityType.PERSON_NAME
    if label in _ORG:
        return EntityType.ORGANISATION
    if label in _LOC:
        return EntityType.LOCATION
    return None
