"""Hard structural validators. Invalid results cannot be rescued by score."""

from __future__ import annotations

import re

from app.detectors.checksum import looks_like_tr_iban, validate_iban, validate_luhn, validate_tckn, validate_vkn
from app.domain.models import EntityCandidate, EntityType

from app.detectors.scoring.models import HardValidation

_DIGITS = re.compile(r"\D")


def _compact_alnum(value: str) -> str:
    return "".join(char for char in value.upper() if char.isalnum())


def _digits(value: str) -> str:
    return _DIGITS.sub("", value)


def validate_ipv4(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


def hard_validate(candidate: EntityCandidate) -> HardValidation:
    entity_type = candidate.type
    text = candidate.text
    if entity_type == EntityType.NATIONAL_ID:
        if candidate.detector.startswith("EN_"):
            return HardValidation.NOT_APPLICABLE
        return HardValidation.VALID if validate_tckn(_digits(text)) else HardValidation.INVALID
    if entity_type == EntityType.IBAN:
        compact = _compact_alnum(text)
        if validate_iban(compact):
            return HardValidation.VALID
        if looks_like_tr_iban(compact):
            return HardValidation.INVALID
        return HardValidation.INVALID
    if entity_type == EntityType.CREDIT_CARD:
        return HardValidation.VALID if validate_luhn(text) else HardValidation.INVALID
    if entity_type == EntityType.TAX_IDENTIFIER:
        digits = _digits(text)
        if len(digits) != 10:
            return HardValidation.INVALID
        if validate_vkn(digits):
            return HardValidation.VALID
        return HardValidation.UNKNOWN
    if entity_type == EntityType.IP_ADDRESS:
        return HardValidation.VALID if validate_ipv4(text) else HardValidation.INVALID
    if entity_type == EntityType.EMAIL:
        return HardValidation.VALID if "@" in text and "." in text.split("@")[-1] else HardValidation.INVALID
    if entity_type == EntityType.PORT_NUMBER:
        try:
            port = int(_digits(text) or text)
        except ValueError:
            return HardValidation.INVALID
        return HardValidation.VALID if 0 <= port <= 65535 else HardValidation.INVALID
    return HardValidation.NOT_APPLICABLE
