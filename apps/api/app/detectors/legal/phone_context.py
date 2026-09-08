"""Contextual phone parser for OCR-ish legal phrasing."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate
from app.detectors.registry import PageText, TR_PHONE, TR_PHONE_GROUPED
from app.domain.models import EntityCandidate, EntityType

_CONTEXT = re.compile(
    r"(?:nolu\s+)?(?:gsm\s+hatt(?:ı|i|ına|ina|ını|ini)|telefon\s+numara(?:sı|si)|"
    r"irtibat\s+numara(?:sı|si)|cep\s+telefonu|hatt(?:a|ına|ina|ını|ini)\s+ait)",
    re.IGNORECASE,
)
# Relaxed mobile-like digit run: 10–13 digits with spaces/dashes/parens.
_LOOSE = re.compile(
    r"(?<!\d)(?P<num>(?:\+|00)?(?:90)?[\s()./-]*0?5(?:[\s()./-]*\d){9})(?!\d)"
)


def _compact_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _plausible_tr_mobile(value: str) -> bool:
    digits = _compact_digits(value)
    if digits.startswith("90"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    return len(digits) == 10 and digits.startswith("5")


def parse_phone_context(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()
    for ctx in _CONTEXT.finditer(page.text):
        window_start = max(0, ctx.start() - 40)
        window_end = min(len(page.text), ctx.end() + 40)
        window = page.text[window_start:window_end]
        match = TR_PHONE.search(window) or TR_PHONE_GROUPED.search(window) or _LOOSE.search(window)
        if match is None:
            continue
        raw = match.group(0)
        if not _plausible_tr_mobile(raw):
            continue
        local_start = window_start + match.start()
        local_end = window_start + match.end()
        key = (local_start, local_end)
        if key in seen:
            continue
        seen.add(key)
        found.append(
            make_candidate(
                page,
                text=raw,
                local_start=local_start,
                local_end=local_end,
                entity_type=EntityType.PHONE_NUMBER,
                detector="TR_PHONE_CONTEXT",
                reason="Phone number in GSM/telefon context.",
                validated=True,
                attributes={"source": "phone_context"},
            )
        )
    return found
