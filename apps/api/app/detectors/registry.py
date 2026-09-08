from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

from app.detectors.checksum import (
    looks_like_tr_iban,
    validate_iban,
    validate_luhn,
    validate_tckn,
    validate_vkn,
)
from app.detectors.gazetteers import TURKISH_AREA_CODES
from app.detectors.legal.merge import merge_rule_candidates, promote_counsel_titles
from app.detectors.scoring import apply_scoring
from app.detectors.legal.identifier_repeats import (
    IBAN_REPEAT,
    PHONE_REPEAT,
    PORT_REPEAT,
    propagate_identifier_repeats,
)
from app.detectors.legal.repeats import DETECTOR_NAME as NAME_REPEAT
from app.detectors.legal.repeats import pair_adjacent_person_name_tokens
from app.detectors.legal.repeats import propagate_person_name_repeats
from app.detectors.verification import apply_verification
from app.domain.models import DetectionMethod, EntityCandidate, EntityType, VerificationLevel

RETIRED_DETECTION_TYPES = frozenset(
    {
        EntityType.MONEY_AMOUNT,
        EntityType.SALARY_INFORMATION,
        EntityType.POLITICAL_INFORMATION,
    }
)


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    document_offset: int


Detector = Callable[[PageText], Iterable[EntityCandidate]]


def _candidate(
    page: PageText,
    match: re.Match[str],
    entity_type: EntityType,
    detector: str,
    *,
    value: str | None = None,
    group: int | str = 0,
    validated: bool = True,
    start: int | None = None,
    end: int | None = None,
) -> EntityCandidate:
    return EntityCandidate(
        text=value or match.group(group),
        type=entity_type,
        start=page.document_offset + (start if start is not None else match.start(group)),
        end=page.document_offset + (end if end is not None else match.end(group)),
        page=page.page,
        detector=detector,
        method=DetectionMethod.DETERMINISTIC,
        validated=validated,
    )


_IBAN_CUE = re.compile(
    r"(?i)(?:iban|ibana|hesap\s+no|hesap\s+numara|nezdinde|"
    r"ad[ıi]na\s+kay[ıi]tl[ıi]|banka|havale|eft)"
)
_TR_IBAN_GROUPED = re.compile(
    r"^TR[\s\-]+\d{2}(?:[\s\-]+\d{4}){5}[\s\-]+\d{2}$"
)
_IBAN_SEP = frozenset(
    " \t\r\n-./\\\u00a0\u00ad\u2000\u2001\u2002\u2003\u2004\u2005"
    "\u2006\u2007\u2008\u2009\u200a\u200b\u202f\u2060\ufeff"
)
_TR_HEAD = re.compile(r"(?<![A-Za-z0-9])T[\s\-\u00ad\u200b\u2060\ufeff]*R(?=[\s\-\u00ad\u200b]*\d)")


def _tr_iban_prefix(raw: str) -> tuple[str, int] | None:
    """Take the leading TR + 24 digits out of a match that also swallowed 'Ibana'."""
    compact: list[str] = []
    end = 0
    for index, char in enumerate(raw):
        if char.isalnum():
            compact.append(char.upper())
            end = index + 1
            if len(compact) == 26:
                candidate = "".join(compact)
                if looks_like_tr_iban(candidate):
                    return raw[:end].rstrip(" \t\r\n-"), end
                return None
        elif compact and (char in _IBAN_SEP or not char.isalpha()):
            continue
        elif compact:
            break
    return None


def _iban_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 48) : min(len(text), end + 24)]
    return bool(_IBAN_CUE.search(window))


def _trivial_tr_digits(compact: str) -> bool:
    digits = compact[2:]
    return len(digits) == 24 and len(set(digits)) <= 1


def _accept_iban(compact: str, surface: str, text: str, start: int, end: int) -> bool:
    """Hard IBAN gate: country + official length + MOD-97. No checksum bypass."""
    if not (15 <= len(compact) <= 34):
        return False
    return validate_iban(compact)


def iter_tr_iban_spans(text: str) -> list[tuple[str, int, int]]:
    """Find TR + 24 digits even when T/R or digit groups are oddly spaced."""
    found: list[tuple[str, int, int]] = []
    for head in _TR_HEAD.finditer(text):
        digits: list[str] = []
        end = head.end()
        index = head.end()
        while index < len(text) and len(digits) < 24:
            char = text[index]
            if char.isdigit():
                digits.append(char)
                end = index + 1
                index += 1
                continue
            if char in _IBAN_SEP or char in "()[]":
                index += 1
                continue
            break
        if len(digits) != 24:
            continue
        if index < len(text) and text[index].isdigit():
            continue
        surface = text[head.start() : end]
        compact = "TR" + "".join(digits)
        if not _accept_iban(compact, surface, text, head.start(), end):
            continue
        found.append((surface, head.start(), end))
    return found


def _fit_iban(match: re.Match[str]) -> tuple[str, int, int] | None:
    """Shrink a greedy IBAN match so a following word is not swallowed."""
    raw = match.group(0)
    start = match.start()
    source = match.string
    prefix = _tr_iban_prefix(raw)
    if prefix:
        surface, length = prefix
        compact = re.sub(r"[\s\-]", "", surface).upper()
        if _accept_iban(compact, surface, source, start, start + length):
            return surface, start, start + len(surface)
    while raw:
        compact = re.sub(r"[\s\-]", "", raw).upper()
        trimmed = raw.rstrip(" \t\r\n-")
        if _accept_iban(compact, trimmed, source, start, start + len(trimmed)):
            return trimmed, start, start + len(trimmed)
        next_raw = re.sub(r"[\s\-]+\S+$", "", raw)
        if next_raw == raw:
            next_raw = raw[:-1].rstrip()
        if not next_raw or next_raw == raw:
            break
        raw = next_raw
    return None


EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@(?:[\w-]+\.)+[A-Za-z]{2,63}(?![\w.-])")
URL = re.compile(r"\bhttps?://[^\s<>{}\[\]]+", re.IGNORECASE)
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
# Do not use IGNORECASE: Turkish İ would be treated as [A-Z] and swallow "İbana".
# Continuous body, or separator-grouped 1–4 char chunks. Inter-character
# whitespace must not consume ordinary English words / date prose.
IBAN = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"[A-Za-z]{2}[\s\-]*\d{2}[\s\-]*[A-Za-z0-9]{11,30}"
    r"|"
    r"[A-Za-z]{2}[\s\-]*\d{2}(?:[\s\-]+[A-Za-z0-9]{1,4}){3,8}"
    r")(?![A-Za-z0-9])"
)
CARD = re.compile(r"(?<![A-Za-z0-9])(?:\d[ -]?){13,19}(?![A-Za-z0-9])")
_PHONE_SEP = (
    r"[\s()./\u00a0\u00ad\u1680\u180e\u2000-\u200d\u2028\u2029\u202f"
    r"\u205f\u3000\u2010-\u2015\u2212\ufeff-]*"
)
TR_PHONE = re.compile(
    rf"(?<!\d)(?:(?:\+|00)90{_PHONE_SEP}|0{_PHONE_SEP})?5(?:{_PHONE_SEP}\d){{9}}(?!\d)"
)
# 0XXX XXX XX XX and 0XXX XXX XXXX — common in Turkish legal PDFs.
TR_PHONE_GROUPED = re.compile(
    r"(?<!\d)(?:(?:\+|00)90[\s./-]*)?0?5\d{2}[\s./-]+\d{3}[\s./-]+\d{2}(?:[\s./-]+\d{2})?(?!\d)"
)
TR_LANDLINE = re.compile(
    r"(?<!\d)(?:(?:\+|00)90[\s().-]*|0)?\(?[2-4]\d{2}\)?[\s().-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2}(?!\d)"
)
TR_TCKN = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
TR_UETS = re.compile(r"(?i)(?:UETS\s*[:.\-]?\s*)?(?<!\d)(\d{5}-\d{5}-\d{5})(?!\d)")
TR_VKN_DIGITS = re.compile(r"(?<!\d)\d{10}(?!\d)")
VKN_LABEL = re.compile(
    r"(?i)(?:vergi\s+kimlik\s+(?:numaras[ıi]|no\.?)|vergi\s+(?:numaras[ıi]|no\.?)|"
    r"v\.?\s*k\.?\s*n\.?|vkn)\s*:?\s*$"
)


def _valid_ipv4(value: str) -> bool:
    return all(0 <= int(part) <= 255 for part in value.split("."))


def _national_digits(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("90") and len(digits) >= 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits


_PHONE_NEIGHBOR = frozenset(" \t\r\n-./()[]\u00a0\u00ad\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u202f\u2060\ufeff")


def _is_tr_mobile(value: str) -> bool:
    digits = _national_digits(value)
    return len(digits) == 10 and digits.startswith("5")


def _isolated_from_digit_run(text: str, start: int, end: int) -> bool:
    """Reject a phone taken from the middle of a longer spaced number (IBAN digits)."""
    left = start - 1
    while left >= 0 and text[left] in _PHONE_NEIGHBOR:
        left -= 1
    if left >= 0 and text[left].isdigit():
        return False
    right = end
    while right < len(text) and text[right] in _PHONE_NEIGHBOR:
        right += 1
    if right < len(text) and text[right].isdigit():
        return False
    return True


def _is_tr_landline(value: str) -> bool:
    digits = _national_digits(value)
    return len(digits) == 10 and digits[:3] in TURKISH_AREA_CODES


def _vkn_has_label(text: str, start: int) -> bool:
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start]
    if VKN_LABEL.search(prefix):
        return True
    if start > 0 and text[start - 1] == "\n":
        previous_end = start - 1
        previous_start = text.rfind("\n", 0, previous_end) + 1
        return bool(VKN_LABEL.search(text[previous_start:previous_end]))
    return False


def detect_global(page: PageText) -> Iterable[EntityCandidate]:
    iban_spans: list[tuple[int, int]] = []
    for match in EMAIL.finditer(page.text):
        yield _candidate(page, match, EntityType.EMAIL, "GLOBAL_EMAIL")
    for match in URL.finditer(page.text):
        yield _candidate(page, match, EntityType.URL, "GLOBAL_URL")
    for match in IPV4.finditer(page.text):
        if _valid_ipv4(match.group(0)):
            yield _candidate(page, match, EntityType.IP_ADDRESS, "GLOBAL_IPV4")
    for match in IBAN.finditer(page.text):
        fitted = _fit_iban(match)
        if fitted:
            value, start, end = fitted
            iban_spans.append((start, end))
            yield _candidate(
                page, match, EntityType.IBAN, "GLOBAL_IBAN",
                value=value, start=start, end=end,
                validated=validate_iban(re.sub(r"[\s\-]", "", value).upper()),
            )
    for value, start, end in iter_tr_iban_spans(page.text):
        if any(start < other_end and end > other_start for other_start, other_end in iban_spans):
            continue
        iban_spans.append((start, end))
        yield EntityCandidate(
            text=value,
            type=EntityType.IBAN,
            start=page.document_offset + start,
            end=page.document_offset + end,
            page=page.page,
            detector="GLOBAL_IBAN",
            method=DetectionMethod.DETERMINISTIC,
            validated=validate_iban(re.sub(r"[\s\-]", "", value).upper()),
        )
    for match in CARD.finditer(page.text):
        if any(match.start() < end and match.end() > start for start, end in iban_spans):
            continue
        if validate_luhn(match.group(0)):
            yield _candidate(page, match, EntityType.CREDIT_CARD, "GLOBAL_LUHN_CARD")


def _tr_iban_hits(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()
    for match in IBAN.finditer(page.text):
        fitted = _fit_iban(match)
        if not fitted:
            continue
        value, start, end = fitted
        compact = re.sub(r"[\s-]", "", value).upper()
        if not compact.startswith("TR") or len(compact) != 26:
            continue
        seen.add((start, end))
        found.append(
            _candidate(
                page, match, EntityType.IBAN, "TR_IBAN",
                value=value, start=start, end=end,
                validated=validate_iban(compact),
            )
        )
    for value, start, end in iter_tr_iban_spans(page.text):
        if any(start < other_end and end > other_start for other_start, other_end in seen):
            continue
        seen.add((start, end))
        compact = re.sub(r"[\s\-]", "", value).upper()
        found.append(
            EntityCandidate(
                text=value,
                type=EntityType.IBAN,
                start=page.document_offset + start,
                end=page.document_offset + end,
                page=page.page,
                detector="TR_IBAN",
                method=DetectionMethod.DETERMINISTIC,
                validated=validate_iban(compact),
            )
        )
    return found


def detect_tr(page: PageText) -> Iterable[EntityCandidate]:
    for match in TR_TCKN.finditer(page.text):
        if validate_tckn(match.group(0)):
            yield _candidate(page, match, EntityType.NATIONAL_ID, "TR_TCKN")
    for match in TR_UETS.finditer(page.text):
        yield _candidate(page, match, EntityType.UETS, "TR_UETS", group=1)
    ibans = _tr_iban_hits(page)
    iban_spans = [
        (item.start - page.document_offset, item.end - page.document_offset)
        for item in ibans
    ]
    seen_phones: set[tuple[int, int]] = set()
    for pattern, detector_name in (
        (TR_PHONE, "TR_MOBILE_PHONE"),
        (TR_PHONE_GROUPED, "TR_MOBILE_PHONE"),
    ):
        for match in pattern.finditer(page.text):
            if not _is_tr_mobile(match.group(0)):
                continue
            if not _isolated_from_digit_run(page.text, match.start(), match.end()):
                continue
            if any(match.start() < end and match.end() > start for start, end in iban_spans):
                continue
            key = (match.start(), match.end())
            if key in seen_phones:
                continue
            seen_phones.add(key)
            yield _candidate(page, match, EntityType.PHONE_NUMBER, detector_name)
    for match in TR_LANDLINE.finditer(page.text):
        if not _is_tr_landline(match.group(0)):
            continue
        if not _isolated_from_digit_run(page.text, match.start(), match.end()):
            continue
        if any(match.start() < end and match.end() > start for start, end in iban_spans):
            continue
        yield _candidate(page, match, EntityType.PHONE_NUMBER, "TR_LANDLINE_PHONE")
    for match in TR_VKN_DIGITS.finditer(page.text):
        if not _vkn_has_label(page.text, match.start()):
            continue
        value = match.group(0)
        checked = validate_vkn(value)
        yield EntityCandidate(
            text=value,
            type=EntityType.TAX_IDENTIFIER,
            start=page.document_offset + match.start(),
            end=page.document_offset + match.end(),
            page=page.page,
            detector="TR_VKN",
            method=DetectionMethod.DETERMINISTIC,
            validated=checked,
            verification_level=(
                VerificationLevel.VALIDATED if checked else VerificationLevel.REVIEW_RECOMMENDED
            ),
            verification_method="vkn_checksum" if checked else "structural_label",
            reason="Tax label with 10-digit identifier.",
        )
    yield from ibans


from app.detectors.turkish_advanced import detect_turkish_advanced
from app.detectors.locale_pack import register_locale_pack, run_locale_detectors


def detect_legal_structure(page: PageText) -> Iterable[EntityCandidate]:
    from app.detectors.legal.structure import detect_legal_structure as _run

    return _run(page)


# Legacy DETECTORS for backward compatibility
DETECTORS: tuple[tuple[str, Detector], ...] = (
    ("GLOBAL_STRUCTURED", detect_global),
    ("TR_DOCUMENTED", detect_tr),
    ("TR_ADVANCED_GRAMMAR", detect_turkish_advanced),
    ("TR_LEGAL_STRUCTURE", detect_legal_structure),
)


def drop_retired_detections(
    candidates: list[EntityCandidate],
) -> list[EntityCandidate]:
    return [item for item in candidates if item.type not in RETIRED_DETECTION_TYPES]


def run_detectors(
    pages: list[PageText],
    locale_ids: list[str] | None = None,
) -> tuple[list[EntityCandidate], list[str]]:
    """Run detectors with optional locale pack system.
    
    Args:
        pages: Document pages to scan
        locale_ids: Optional list of locale pack IDs (e.g., ["global", "tr"]).
                   If None, uses legacy DETECTORS list for backward compatibility.
    
    Returns:
        (candidates, detector_names)
    """
    if locale_ids is not None:
        # Ensure packs are registered before use
        _ensure_packs_registered()
        # Use new locale pack system
        return run_locale_detectors(pages, locale_ids)
    
    # Legacy path for backward compatibility
    candidates: list[EntityCandidate] = []
    for page in pages:
        for _, detector in DETECTORS:
            candidates.extend(detector(page))

    # A country-specific detector may overlap a global candidate. Prefer the
    # more specific detector, then deduplicate exact span/type matches.
    candidates.sort(key=lambda item: (item.start, item.end, item.detector.startswith("GLOBAL")))
    unique: dict[tuple[int, int, EntityType], EntityCandidate] = {}
    for candidate in candidates:
        unique.setdefault((candidate.start, candidate.end, candidate.type), candidate)

    scored = apply_scoring(pages, list(unique.values()))
    merged = merge_rule_candidates(scored)
    paired = pair_adjacent_person_name_tokens(pages, merged)
    if paired:
        merged = merge_rule_candidates(merged + paired)
    repeats = propagate_person_name_repeats(pages, merged)
    if repeats:
        merged = merge_rule_candidates(merged + repeats)
    identifiers = propagate_identifier_repeats(pages, merged)
    if identifiers:
        merged = merge_rule_candidates(merged + identifiers)
    merged = promote_counsel_titles(pages, merged)
    names = [name for name, _ in DETECTORS]
    names.append("TR_EVIDENCE_SCORING")
    if any(item.detector == "TR_NARRATIVE_PERSON" for item in merged):
        names.append("TR_NARRATIVE_PERSON")
    if any(item.detector == "TR_EVIDENCE_ADDRESS" for item in merged):
        names.append("TR_EVIDENCE_ADDRESS")
    if paired:
        names.append("TR_NAME_PAIR")
    if repeats:
        names.append(NAME_REPEAT)
    if identifiers:
        names.extend(
            detector
            for detector in (IBAN_REPEAT, PHONE_REPEAT, PORT_REPEAT)
            if any(item.detector == detector for item in identifiers)
        )
    return apply_verification(drop_retired_detections(merged)), names


# Auto-register built-in locale packs
def _register_builtin_packs():
    # Import here to avoid circular dependency
    from app.detectors.packs import ENGLISH_PACK, GLOBAL_PACK, TURKISH_PACK
    register_locale_pack(GLOBAL_PACK)
    register_locale_pack(TURKISH_PACK)
    register_locale_pack(ENGLISH_PACK)

# Defer registration to avoid circular import at module load time
# Will be called when first needed
_packs_registered = False

def _ensure_packs_registered():
    global _packs_registered
    if not _packs_registered:
        _register_builtin_packs()
        _packs_registered = True
