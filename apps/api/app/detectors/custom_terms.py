"""Exact / safely-normalized matching for user-defined terms.

Inflected leftovers after a *user-provided* base (``Mehmet Yılmaz'ın``) are
included in the match when they are a known Turkish proper-noun inflection.
The document is not scanned token-by-token with Zemberek; expansion only
runs after the base term already matched.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.detectors.registry import PageText
from app.detectors.scoring.derived import mark_outside_scoring
from app.domain.models import (
    DetectionMethod,
    EntityCandidate,
    EntityType,
    UserDefinedTerm,
    VerificationLevel,
)
from app.transforms.tag_taxonomy import PERSON_MATCH_TYPES
from app.transforms.turkish_morphology import (
    analyze_inflected_surface,
    is_safe_custom_term_suffix,
)

_CATEGORY_TO_TYPE: dict[str, EntityType] = {
    "PERSON_NAME": EntityType.PERSON_NAME,
    "ADDRESS": EntityType.ADDRESS,
    "COMPANY_NAME": EntityType.COMPANY_NAME,
    "OTHER_IDENTIFIER": EntityType.OTHER_IDENTIFIER,
}

_TR_I = "iİıI"
_TRAILING_INFLECTION = re.compile(r"(?:'|\u2019|\u2032)([A-Za-zçğıöşüâîûÇĞİÖŞÜ]{1,12})")
_NAME_TOKEN = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+")


def _looks_like_person_name(value: str) -> bool:
    if any(char.isdigit() for char in value):
        return False
    tokens = _NAME_TOKEN.findall(value)
    if len(tokens) < 2:
        return False
    return all(token[0].isupper() for token in tokens)


def resolve_custom_term_type(term: UserDefinedTerm) -> EntityType:
    """Prefer an explicit category; name-like “Other” terms become PERSON_NAME."""
    category = term.category if isinstance(term.category, EntityType) else None
    if category is None:
        try:
            category = EntityType(str(term.category))
        except ValueError:
            category = EntityType.OTHER_IDENTIFIER
    if category == EntityType.OTHER_IDENTIFIER and _looks_like_person_name(term.value):
        return EntityType.PERSON_NAME
    return category


def drop_hits_inside_person_spans(
    fresh: list[EntityCandidate],
    existing: list[EntityCandidate],
) -> list[EntityCandidate]:
    """Do not nest a custom span inside an existing person/role finding."""
    people = [item for item in existing if item.type in PERSON_MATCH_TYPES]
    if not people:
        return fresh
    kept: list[EntityCandidate] = []
    for item in fresh:
        overlapping = any(
            item.start < person.end and item.end > person.start for person in people
        )
        if overlapping:
            continue
        kept.append(item)
    return kept


def _term_pattern(value: str) -> re.Pattern[str] | None:
    compact = " ".join(value.split())
    if len(compact) < 2:
        return None
    parts: list[str] = []
    for char in compact:
        if char in _TR_I:
            parts.append(f"[{_TR_I}]")
        elif char.isspace():
            parts.append(r"\s+")
        elif char.isalnum() or char in "çğıöşüÇĞİÖŞÜ":
            parts.append(re.escape(char))
        else:
            parts.append(re.escape(char))
    return re.compile(
        rf"(?<![A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]){''.join(parts)}(?![A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû])",
        re.IGNORECASE,
    )


def _expand_inflected_end(page_text: str, match_end: int, term_value: str) -> int:
    """Grow a base-term hit over a following apostrophe inflection, if safe."""
    leftover = page_text[match_end:]
    suffix_match = _TRAILING_INFLECTION.match(leftover)
    if suffix_match is None:
        return match_end
    raw_suffix = suffix_match.group(1)
    if is_safe_custom_term_suffix(raw_suffix):
        return match_end + suffix_match.end()
    probe = f"{term_value.split()[-1]}'{raw_suffix}" if term_value.split() else ""
    if not probe:
        return match_end
    parsed = analyze_inflected_surface(
        probe,
        allow_extended_local=False,
        allow_zemberek=True,
    )
    if parsed.source == "zemberek" and parsed.suffix:
        return match_end + suffix_match.end()
    return match_end


def detect_user_terms(
    pages: list[PageText],
    terms: Iterable[UserDefinedTerm],
) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int, str]] = set()
    for term in terms:
        pattern = _term_pattern(term.value)
        if pattern is None:
            continue
        entity_type = resolve_custom_term_type(term)
        allowed_starts = list(dict.fromkeys(term.starts)) if term.starts else None
        if allowed_starts:
            collected = _collect_hits_for_starts(
                pages, term, pattern, entity_type, seen, allowed_starts
            )
            if not collected:
                collected = _collect_term_hits(pages, term, pattern, entity_type, seen, None)
        else:
            collected = _collect_term_hits(pages, term, pattern, entity_type, seen, None)
        found.extend(collected)
    return found


def _page_at(pages: list[PageText], start: int) -> PageText | None:
    for page in pages:
        end = page.document_offset + len(page.text)
        if page.document_offset <= start < end:
            return page
        if start == end and page is pages[-1]:
            return page
    return pages[-1] if pages else None


def _span_from_match(
    page: PageText,
    term: UserDefinedTerm,
    local_start: int,
    match_end: int,
) -> tuple[int, int]:
    local_end = _expand_inflected_end(page.text, match_end, term.value)
    return page.document_offset + local_start, page.document_offset + local_end


def _hit_near_start(
    page: PageText,
    term: UserDefinedTerm,
    pattern: re.Pattern[str],
    abs_start: int,
) -> tuple[int, int] | None:
    local = abs_start - page.document_offset
    for match in pattern.finditer(page.text):
        start, end = _span_from_match(page, term, match.start(), match.end())
        if start <= abs_start < end or abs(start - abs_start) <= 12:
            return match.start(), match.end()
    window_from = max(0, local - 12)
    window = page.text[window_from : local + max(len(term.value), 2) + 24]
    match = pattern.search(window)
    if match is not None:
        return window_from + match.start(), window_from + match.end()
    if 0 <= local < len(page.text):
        probe = " ".join(term.value.split())
        folded_page = page.text.casefold()
        folded_term = probe.casefold()
        at = folded_page.find(folded_term, max(0, local - 12))
        if at >= 0 and abs(at - local) <= 12:
            return at, at + len(page.text[at : at + len(probe)])
    return None


def _collect_hits_for_starts(
    pages: list[PageText],
    term: UserDefinedTerm,
    pattern: re.Pattern[str],
    entity_type: EntityType,
    seen: set[tuple[int, int, str]],
    starts: list[int],
) -> list[EntityCandidate]:
    collected: list[EntityCandidate] = []
    for abs_start in starts:
        page = _page_at(pages, abs_start)
        if page is None:
            continue
        hit = _hit_near_start(page, term, pattern, abs_start)
        if hit is None:
            continue
        local_start, match_end = hit
        local_end = _expand_inflected_end(page.text, match_end, term.value)
        start = page.document_offset + local_start
        end = page.document_offset + local_end
        key = (start, end, entity_type.value)
        if key in seen:
            continue
        seen.add(key)
        collected.append(
            mark_outside_scoring(
                EntityCandidate(
                    text=page.text[local_start:local_end],
                    type=entity_type,
                    start=key[0],
                    end=key[1],
                    page=page.page,
                    recommended=True,
                    detector="USER_DEFINED_TERM",
                    method=DetectionMethod.DETERMINISTIC,
                    validated=True,
                    verification_level=VerificationLevel.VALIDATED,
                    verification_method="user_defined",
                    reason="User-defined term.",
                    attributes={"source": "user_defined", "term": term.value},
                )
            )
        )
    return collected


def _collect_term_hits(
    pages: list[PageText],
    term: UserDefinedTerm,
    pattern: re.Pattern[str],
    entity_type: EntityType,
    seen: set[tuple[int, int, str]],
    allowed_starts: set[int] | None,
) -> list[EntityCandidate]:
    collected: list[EntityCandidate] = []
    for page in pages:
        for match in pattern.finditer(page.text):
            local_start = match.start()
            local_end = _expand_inflected_end(page.text, match.end(), term.value)
            start = page.document_offset + local_start
            end = page.document_offset + local_end
            if allowed_starts is not None and start not in allowed_starts:
                if not any(start <= item < end for item in allowed_starts):
                    continue
            key = (start, end, entity_type.value)
            if key in seen:
                continue
            seen.add(key)
            collected.append(
                mark_outside_scoring(
                    EntityCandidate(
                        text=page.text[local_start:local_end],
                        type=entity_type,
                        start=key[0],
                        end=key[1],
                        page=page.page,
                        recommended=True,
                        detector="USER_DEFINED_TERM",
                        method=DetectionMethod.DETERMINISTIC,
                        validated=True,
                        verification_level=VerificationLevel.VALIDATED,
                        verification_method="user_defined",
                        reason="User-defined term.",
                        attributes={"source": "user_defined", "term": term.value},
                    )
                )
            )
    return collected
