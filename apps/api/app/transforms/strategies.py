from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.detectors.gazetteers import TURKISH_CITIES, TURKISH_DISTRICTS
from app.domain.models import EntityCandidate, EntityType, TransformationStrategy
from app.transforms.catalog import (
    normalize_role_key,
    placeholder_prefix,
    role_label,
)
from app.transforms.resolution import split_name_suffix
from app.transforms.tag_registry import DocumentTagRegistry
from app.transforms.tag_taxonomy import normalize_tag_locale, spec_for
from app.transforms.turkish_morphology import (
    attach_turkish_suffix,
    extract_trailing_apostrophe_suffix,
    suffix_classification_token,
)


@dataclass
class TransformOp:
    entity_id: str | None
    category: str | None
    strategy: TransformationStrategy
    start: int
    end: int
    replacement: str
    original: str
    resolved_entity_id: str | None = None
    role: str | None = None
    ai_assisted: bool = False
    export_path: str = "text_rebuild"
    source: str = "default"
    parameters: dict[str, Any] | None = None
    user_decision: str | None = None
    mapping_coarse: bool = False
    placeholder_key: str | None = None


def redact_value(original: str) -> str:
    return "█" * max(1, len(original))


def placeholder_value(
    entity: EntityCandidate,
    counters: dict[str, int],
    locale: str,
    *,
    numbered: bool = True,
    trailing_suffix: str = "",
    original_surface: str = "",
    registry: DocumentTagRegistry | None = None,
) -> str:
    """Type-preserving token, with optional Turkish case ending.

    Person tags follow the document registry when one is supplied:

        Mehmet Yılmaz (CLAIMANT_NAME)  →  [DAVACI_1]
        Mehmet Yılmaz'ın               →  [DAVACI_1]'ın

    Without a registry, the token uses this span's detector type only.
    Partial names never inherit a full-name tag.
    """
    if registry is not None:
        token = registry.token_for(entity, prefer_stamped=False)
    else:
        spec = spec_for(entity.type)
        prefix = (
            spec.labels_tr
            if normalize_tag_locale(locale) == "tr"
            else spec.labels_en
        )
        if numbered and spec.numbered:
            key = entity.resolved_entity_id or entity.id
            if key not in counters:
                counters[key] = len(counters) + 1
            token = f"[{prefix}_{counters[key]}]"
        else:
            token = f"[{prefix}]"
    suffix = trailing_suffix.strip()
    if not suffix:
        _base, attached = split_name_suffix(entity.text, extended=True)
        suffix = attached.lstrip("'’′")
    if not suffix:
        return token
    probe = original_surface or entity.text
    return attach_turkish_suffix(
        token,
        suffix,
        apostrophe=True,
        original_token=suffix_classification_token(probe, suffix),
    )


def initials_value(original: str, trailing_suffix: str = "") -> str:
    base, attached = split_name_suffix(original, extended=True)
    if attached and not trailing_suffix:
        trailing_suffix = attached.lstrip("'’")
        original = base
    elif attached:
        original = base
    parts = [part for part in re.split(r"\s+", original.strip()) if part]
    if not parts:
        return "█"
    initials = ".".join(part[0].upper() for part in parts if part) + "."
    if not trailing_suffix:
        return initials
    return f"{initials}'{trailing_suffix.lstrip("'’")}"


COURT_ORDINAL_TAG = "X"
_DATE_DIGIT_GROUP = re.compile(r"\d+")
_DATE_YEAR4 = re.compile(r"(?:19|20)\d{2}")


def partial_mask_date_of_birth(text: str) -> str:
    """Keep the year; mask day/month digits. Separators stay as written.

    ``26/03/2009`` → ``**/**/2009``
    ``26.03.2009`` → ``**.**.2009``
    ``12 March 1985`` → ``** March 1985``
    ``2009-03-26`` → ``2009-**-**``
    """
    matches = list(_DATE_DIGIT_GROUP.finditer(text))
    if not matches:
        return redact_value(text)

    year_match = next(
        (item for item in reversed(matches) if _DATE_YEAR4.fullmatch(item.group())),
        None,
    )
    if year_match is None:
        year_match = next(
            (item for item in reversed(matches) if len(item.group()) == 4),
            None,
        )
    if year_match is None and len(matches) == 3 and len(matches[-1].group()) == 2:
        year_match = matches[-1]
    if year_match is None:
        return redact_value(text)

    year_span = year_match.span()
    parts: list[str] = []
    cursor = 0
    for match in matches:
        parts.append(text[cursor : match.start()])
        if match.span() == year_span:
            parts.append(match.group())
        else:
            parts.append("*" * len(match.group()))
        cursor = match.end()
    parts.append(text[cursor:])
    return "".join(parts)


def mask_court_ordinals(text: str) -> str:
    """Hide only the chamber number; keep city and court type readable."""
    return re.sub(r"\b(\d{1,3})\s*(\.)", lambda match: ("█" * len(match.group(1))) + match.group(2), text)


def label_court_ordinals(text: str, tag: str = COURT_ORDINAL_TAG) -> str:
    """Replace chamber numbers with a tag; keep city and court type readable."""
    return re.sub(r"\b\d{1,3}\s*\.", tag, text)


def partial_mask_value(entity: EntityCandidate) -> str:
    text = entity.text
    category = entity.type
    if category == EntityType.COURT_NAME:
        return mask_court_ordinals(text)
    if category == EntityType.DATE_OF_BIRTH:
        return partial_mask_date_of_birth(text)
    if category == EntityType.PHONE_NUMBER:
        digits = re.sub(r"\D", "", text)
        if len(digits) < 7:
            return redact_value(text)
        # Keep leading trunk and last 2 digits in a spaced Turkish mobile style.
        keep_head = digits[:4]
        keep_tail = digits[-2:]
        return f"{keep_head} *** ** {keep_tail}"
    if category == EntityType.EMAIL:
        if "@" not in text:
            return redact_value(text)
        local, domain = text.split("@", 1)
        if not local:
            return f"*@{domain}"
        return f"{local[0]}{'*' * max(1, len(local) - 1)}@{domain}"
    if category == EntityType.IBAN:
        compact = re.sub(r"\s+", "", text.upper())
        if len(compact) < 10:
            return redact_value(text)
        head = compact[:4]
        tail = compact[-2:]
        middle = "*" * max(4, len(compact) - 6)
        masked = head + middle + tail
        return " ".join(masked[i : i + 4] for i in range(0, len(masked), 4))
    if category == EntityType.NATIONAL_ID:
        compact = re.sub(r"\s+", "", text)
        if len(compact) == 11:
            return f"{compact[:3]}{'•' * 6}{compact[-2:]}"
        if len(compact) <= 3:
            return redact_value(text)
        return ("*" * (len(compact) - 3)) + compact[-3:]
    if category in {
        EntityType.PASSPORT_NUMBER,
        EntityType.TAX_IDENTIFIER,
        EntityType.CREDIT_CARD,
        EntityType.BANK_ACCOUNT,
        EntityType.EMPLOYEE_ID,
        EntityType.CUSTOMER_ID,
        EntityType.OTHER_IDENTIFIER,
        EntityType.VEHICLE_PLATE,
    }:
        compact = re.sub(r"\s+", "", text)
        if len(compact) <= 3:
            return redact_value(text)
        return ("*" * (len(compact) - 3)) + compact[-3:]
    return redact_value(text)


def _word_bounded_hits(text: str, names: frozenset[str]) -> list[tuple[int, int, str]]:
    folded = text.casefold()
    hits: list[tuple[int, int, str]] = []
    for name in names:
        needle = name.casefold()
        start = 0
        while True:
            idx = folded.find(needle, start)
            if idx < 0:
                break
            before = folded[idx - 1] if idx > 0 else " "
            after_idx = idx + len(needle)
            after = folded[after_idx] if after_idx < len(folded) else " "
            if not before.isalnum() and not after.isalnum():
                hits.append((idx, len(needle), name))
            start = idx + 1
    return hits


def _rightmost_hit(hits: list[tuple[int, int, str]]) -> tuple[str, int] | None:
    if not hits:
        return None
    last_start = max(item[0] for item in hits)
    at_last = [item for item in hits if item[0] == last_start]
    best = max(at_last, key=lambda item: item[1])
    return best[2], best[0]


def generalize_address(text: str, locale: str, mode: str | None = None) -> str:
    """Keep only gazetteer-backed city/district. Otherwise a type token.

    Do not invent a location from slash-separated street fragments.
    """
    fallback = f"[{placeholder_prefix('ADDRESS', locale)}]"
    city_hit = _rightmost_hit(_word_bounded_hits(text, TURKISH_CITIES))
    if city_hit is None:
        return fallback
    city, city_at = city_hit
    if mode == "city_only":
        return city
    district_hits = [
        item for item in _word_bounded_hits(text, TURKISH_DISTRICTS) if item[0] < city_at
    ]
    district_hit = _rightmost_hit(district_hits)
    if district_hit is not None:
        return f"{district_hit[0]} / {city}"
    return city


def generalize_value(
    entity: EntityCandidate,
    parameters: dict[str, Any] | None,
    locale: str = "tr",
) -> str:
    mode = (parameters or {}).get("mode")
    text = entity.text.strip()
    if entity.type in {EntityType.DATE, EntityType.DATE_OF_BIRTH}:
        year_match = re.search(r"(19|20)\d{2}", text)
        if not year_match:
            if entity.type == EntityType.DATE_OF_BIRTH:
                return f"[{placeholder_prefix('DATE_OF_BIRTH', locale)}]"
            return text
        year = int(year_match.group(0))
        if mode == "year_range":
            base = year - (year % 5)
            return f"{base}–{base + 5}"
        return str(year)
    if entity.type in {EntityType.ADDRESS, EntityType.LOCATION}:
        return generalize_address(text, locale, mode)
    if entity.type == EntityType.COURT_NAME:
        # Drop leading city ordinal markers: "İstanbul 1. Ağır Ceza Mahkemesi"
        cleaned = re.sub(
            r"^[\wÇĞİÖŞÜçğıöşü]+\s+\d+\.\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        return cleaned or text
    return text


def suppress_value(_entity: EntityCandidate) -> str:
    return ""


def role_replacement_plan(
    text: str,
    entity: EntityCandidate,
    locale: str,
    counters: dict[str, int] | None = None,
) -> TransformOp | None:
    role_key = normalize_role_key(entity.role, entity.type)
    if not role_key or not entity.role_confident:
        return None
    label = role_label(role_key, locale)
    start, end = entity.start, entity.end
    original = text[start:end]
    left = text[max(0, start - 40) : start]
    right = text[end : min(len(text), end + 12)]

    # Expand over a preceding role word that duplicates the replacement.
    role_pattern = re.compile(
        rf"(?i)(?<!\w){re.escape(label)}(?:'|\u2019)?(?:[^\s]*)?\s+$"
    )
    match = role_pattern.search(left)
    if match:
        start = start - (len(left) - match.start())
        original = text[start:end]

    suffix = ""
    suffix_match = re.match(r"(?:'|\u2019)([^\s.,;:!?]+)", right)
    if suffix_match:
        suffix = suffix_match.group(1)
        end = end + suffix_match.end()
        original = text[start:end]
        replacement = _attach_turkish_possessive(label, suffix)
    else:
        table = counters if counters is not None else {}
        key = f"role|{role_key}|{entity.resolved_entity_id or entity.id}"
        if key not in table:
            table[key] = 1 + sum(1 for existing in table if existing.startswith(f"role|{role_key}|"))
        letter = chr(ord("A") + min(table[key] - 1, 25))
        replacement = f"{label} {letter}"

    # Avoid "Sanık Sanık" if somehow still present.
    if replacement.lower() in original.lower() and original.strip().lower().startswith(
        label.lower()
    ):
        # already role-only span
        pass

    return TransformOp(
        entity_id=entity.id,
        category=entity.type.value,
        strategy=TransformationStrategy.PLACEHOLDER,
        start=start,
        end=end,
        replacement=replacement,
        original=original,
        resolved_entity_id=entity.resolved_entity_id,
        role=role_key,
        export_path="text_rebuild",
    )


def _span_and_suffix(text: str, entity: EntityCandidate) -> tuple[int, int, str, str]:
    """Expand the entity span over a following ``'ın`` leftover and return it.

    Detection often reports the bare name (``Mehmet Yılmaz``) while the case
    ending sits just after ``entity.end``. Including that leftover in the
    operation span keeps the suffix from becoming orphaned, and the caller
    re-harmonizes it onto the replacement.
    """
    start, end = entity.start, entity.end
    original = text[start:end] if 0 <= start < end <= len(text) else entity.text
    _base, attached = split_name_suffix(entity.text, extended=True)
    if attached:
        return start, end, original, attached.lstrip("'’′")
    right = text[end : min(len(text), end + 12)] if 0 <= end <= len(text) else ""
    suffix_match = extract_trailing_apostrophe_suffix(right)
    if suffix_match:
        end = end + suffix_match.end()
        original = text[start:end]
        return start, end, original, suffix_match.group(1)
    return start, end, original, ""


def _attach_turkish_possessive(role: str, raw_suffix: str) -> str:
    """Map name case leftovers onto a role word without an apostrophe.

    Delegates to :func:`attach_turkish_suffix`. Kept as a named helper so
    existing role-replacement call sites stay stable.
    """
    return attach_turkish_suffix(role, raw_suffix, apostrophe=False)


def transform_entity(
    text: str,
    entity: EntityCandidate,
    strategy: TransformationStrategy,
    *,
    locale: str,
    counters: dict[str, int],
    parameters: dict[str, Any] | None = None,
    rewrite_text: str | None = None,
    registry: DocumentTagRegistry | None = None,
) -> TransformOp | None:
    if strategy == TransformationStrategy.KEEP:
        return None
    if entity.type == EntityType.QR_CODE:
        original = entity.text
        replacement = redact_value(original)
        return TransformOp(
            entity_id=entity.id,
            category=entity.type.value,
            strategy=strategy,
            start=entity.start,
            end=entity.end,
            replacement=replacement,
            original=original,
            resolved_entity_id=entity.resolved_entity_id,
            export_path="secure_pdf",
            parameters=parameters or {},
        )
    start, end = entity.start, entity.end
    original = text[start:end] if 0 <= start < end <= len(text) else entity.text
    if not original.strip():
        original = entity.text
    custom = str((parameters or {}).get("replacement") or "").strip()
    if custom:
        return TransformOp(
            entity_id=entity.id,
            category=entity.type.value,
            strategy=strategy,
            start=start,
            end=end,
            replacement=custom,
            original=original,
            resolved_entity_id=entity.resolved_entity_id,
            role=normalize_role_key(entity.role, entity.type),
            export_path="text_rebuild",
            parameters=parameters or {},
        )
    # PLACEHOLDER uses the document tag registry ([DAVACI_1], [KİŞİ_2], …)
    if strategy == TransformationStrategy.REDACT:
        replacement = redact_value(original)
        export_path = "secure_pdf"
    elif strategy == TransformationStrategy.PLACEHOLDER:
        if entity.type == EntityType.COURT_NAME:
            labeled = label_court_ordinals(original)
            if labeled == original:
                return None
            replacement = labeled
            export_path = "secure_pdf"
        else:
            start, end, original, suffix = _span_and_suffix(text, entity)
            replacement = placeholder_value(
                entity,
                counters,
                locale,
                numbered=True,
                trailing_suffix=suffix,
                original_surface=original,
                registry=registry,
            )
            export_path = "secure_pdf"
    elif strategy == TransformationStrategy.INITIALS:
        right = text[end : min(len(text), end + 12)]
        suffix_match = re.match(r"(?:'|\u2019)([^\s.,;:!?]+)", right)
        if suffix_match:
            end = end + suffix_match.end()
            original = text[start:end]
            replacement = initials_value(entity.text, suffix_match.group(1))
        else:
            replacement = initials_value(entity.text)
        export_path = "secure_pdf"
    elif strategy == TransformationStrategy.PARTIAL_MASK:
        replacement = partial_mask_value(entity)
        export_path = "secure_pdf"
    else:
        replacement = redact_value(original)
        export_path = "secure_pdf"

    return TransformOp(
        entity_id=entity.id,
        category=entity.type.value,
        strategy=strategy,
        start=start,
        end=end,
        replacement=replacement,
        original=original,
        resolved_entity_id=entity.resolved_entity_id,
        role=normalize_role_key(entity.role, entity.type),
        export_path=export_path,
        parameters=parameters or {},
        placeholder_key=(
            registry.placeholder_key(entity)
            if registry is not None and strategy == TransformationStrategy.PLACEHOLDER
            else None
        ),
    )
