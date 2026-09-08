"""Replicate already-detected IBANs, phones, and ports across the document.

Once a structured identifier is validated, later copies with different spacing,
line wraps, or glued labels must still be covered. This does not invent new
values — it only searches for compact forms already found.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.detectors.checksum import looks_like_tr_iban, validate_iban
from app.detectors.legal.merge import detector_rank
from app.detectors.scoring.derived import inherit_scoring_provenance
from app.domain.models import DetectionMethod, EntityCandidate, EntityType, VerificationLevel

if TYPE_CHECKING:
    from app.detectors.registry import PageText

IBAN_REPEAT = "TR_IBAN_REPEAT"
PHONE_REPEAT = "TR_PHONE_REPEAT"
PORT_REPEAT = "TR_PORT_REPEAT"

_ALNUM_GAP = r"[\s\u00a0\u00ad\u2000-\u200d\u202f\-]*"


def _overlaps(start: int, end: int, other: EntityCandidate) -> bool:
    return other.page >= 0 and start < other.end and other.start < end


def _compact_alnum(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def _digit_key(value: str) -> str:
    return re.sub(r"\D", "", value)


def _alnum_pattern(compact: str) -> re.Pattern[str] | None:
    if len(compact) < 6:
        return None
    body = _ALNUM_GAP.join(re.escape(char) for char in compact)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])")


def _digit_pattern(digits: str) -> re.Pattern[str] | None:
    if not 7 <= len(digits) <= 13:
        return None
    body = _ALNUM_GAP.join(re.escape(char) for char in digits)
    return re.compile(rf"(?<!\d){body}(?!\d)")


def _port_pattern(digits: str) -> re.Pattern[str] | None:
    if not digits.isdigit() or not 1 <= int(digits) <= 65535:
        return None
    if len(digits) < 4:
        return None
    return re.compile(
        rf"(?<!\d){re.escape(digits)}(?!\d)(?:\s*(?i:portu\.?|port))?"
    )


def _iban_seeds(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    seeds: list[EntityCandidate] = []
    seen: set[str] = set()
    ordered = sorted(candidates, key=lambda item: detector_rank(item.detector), reverse=True)
    for item in ordered:
        if item.type not in {EntityType.IBAN, EntityType.BANK_ACCOUNT}:
            continue
        compact = _compact_alnum(item.text)
        if not (15 <= len(compact) <= 34):
            continue
        if not (validate_iban(compact) or looks_like_tr_iban(compact)):
            continue
        if compact in seen:
            continue
        seen.add(compact)
        seeds.append(item)
    return seeds


def _phone_seeds(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    seeds: list[EntityCandidate] = []
    seen: set[str] = set()
    for item in candidates:
        if item.type != EntityType.PHONE_NUMBER:
            continue
        digits = _digit_key(item.text)
        if digits.startswith("00"):
            digits = digits[2:]
        if digits.startswith("90") and len(digits) >= 12:
            digits = digits[2:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) != 10 or not digits.startswith("5"):
            continue
        if digits in seen:
            continue
        seen.add(digits)
        seeds.append(item)
    return seeds


def _port_seeds(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    seeds: list[EntityCandidate] = []
    seen: set[str] = set()
    for item in candidates:
        if item.type != EntityType.PORT_NUMBER:
            continue
        digits = _digit_key(item.text)
        if not digits or digits in seen:
            continue
        if not 1 <= int(digits) <= 65535:
            continue
        seen.add(digits)
        seeds.append(item)
    return seeds


def _emit(
    *,
    page: "PageText",
    match: re.Match[str],
    prototype: EntityCandidate,
    detector: str,
    entity_type: EntityType,
    reason: str,
    method: str,
) -> EntityCandidate:
    start = page.document_offset + match.start()
    end = page.document_offset + match.end()
    return inherit_scoring_provenance(
        EntityCandidate(
            text=match.group(0),
            type=entity_type,
            start=start,
            end=end,
            page=page.page,
            detector=detector,
            method=DetectionMethod.DETERMINISTIC,
            validated=True,
            role=prototype.role,
            reason=reason,
            verification_level=VerificationLevel.REVIEW_RECOMMENDED,
            verification_method=method,
            attributes={
                "source": "identifier_repeat",
                "seed_text": prototype.text,
                "seed_detector": prototype.detector,
            },
        ),
        prototype,
    )


def propagate_identifier_repeats(
    pages: list["PageText"],
    seeds: list[EntityCandidate],
) -> list[EntityCandidate]:
    """Emit extra candidates for later / variant mentions of known identifiers."""
    found: list[EntityCandidate] = []

    def occupied(start: int, end: int) -> bool:
        return any(_overlaps(start, end, item) for item in seeds) or any(
            _overlaps(start, end, item) for item in found
        )

    for page in pages:
        for prototype in _iban_seeds(seeds):
            pattern = _alnum_pattern(_compact_alnum(prototype.text))
            if pattern is None:
                continue
            for match in pattern.finditer(page.text):
                start = page.document_offset + match.start()
                end = page.document_offset + match.end()
                if occupied(start, end):
                    continue
                found.append(
                    _emit(
                        page=page,
                        match=match,
                        prototype=prototype,
                        detector=IBAN_REPEAT,
                        entity_type=EntityType.IBAN,
                        reason="Later mention of an IBAN already found in this document.",
                        method="iban_repeat",
                    )
                )
        for prototype in _phone_seeds(seeds):
            digits = _digit_key(prototype.text)
            if digits.startswith("00"):
                digits = digits[2:]
            if digits.startswith("90") and len(digits) >= 12:
                digits = digits[2:]
            if digits.startswith("0") and len(digits) == 11:
                digits = digits[1:]
            for needle in (digits, "0" + digits):
                pattern = _digit_pattern(needle)
                if pattern is None:
                    continue
                for match in pattern.finditer(page.text):
                    start = page.document_offset + match.start()
                    end = page.document_offset + match.end()
                    if occupied(start, end):
                        continue
                    found.append(
                        _emit(
                            page=page,
                            match=match,
                            prototype=prototype,
                            detector=PHONE_REPEAT,
                            entity_type=EntityType.PHONE_NUMBER,
                            reason="Later mention of a phone number already found in this document.",
                            method="phone_repeat",
                        )
                    )
        for prototype in _port_seeds(seeds):
            pattern = _port_pattern(_digit_key(prototype.text))
            if pattern is None:
                continue
            for match in pattern.finditer(page.text):
                port_text = re.match(r"\d+", match.group(0))
                if port_text is None:
                    continue
                local_start = match.start()
                local_end = match.start() + len(port_text.group(0))
                start = page.document_offset + local_start
                end = page.document_offset + local_end
                if occupied(start, end):
                    continue
                found.append(
                    inherit_scoring_provenance(
                        EntityCandidate(
                            text=port_text.group(0),
                            type=EntityType.PORT_NUMBER,
                            start=start,
                            end=end,
                            page=page.page,
                            detector=PORT_REPEAT,
                            method=DetectionMethod.DETERMINISTIC,
                            validated=True,
                            reason="Later mention of a port number already found in this document.",
                            verification_level=VerificationLevel.REVIEW_RECOMMENDED,
                            verification_method="port_repeat",
                            attributes={
                                "source": "identifier_repeat",
                                "seed_text": prototype.text,
                                "seed_detector": prototype.detector,
                            },
                        ),
                        prototype,
                    )
                )
    return found
