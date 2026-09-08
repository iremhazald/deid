"""Replicate already-detected person names to later mentions and spelling variants.

This is not coreference and does not invent new people. A 2–4 token name that a
rule (or later local NER) already found is searched again across the document so the
same surface form is covered when it is written in a different case, wrapped, or
glued together.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.detectors.legal.merge import detector_rank
from app.detectors.legal.names import collapse_name, strip_possessive
from app.detectors.textutil import fold_tr_identity
from app.domain.models import DetectionMethod, EntityCandidate, EntityType, VerificationLevel

_PERSON = {
    EntityType.PERSON_NAME,
    EntityType.FIRST_NAME,
    EntityType.LAST_NAME,
    EntityType.ALIAS,
    EntityType.JUDGE_NAME,
    EntityType.LAWYER_NAME,
    EntityType.CLAIMANT_NAME,
    EntityType.DEFENDANT_NAME,
    EntityType.WITNESS_NAME,
    EntityType.EXPERT_NAME,
}


def _inherit_scoring_provenance(candidate: EntityCandidate, source: EntityCandidate) -> EntityCandidate:
    from app.detectors.scoring.derived import inherit_scoring_provenance

    return inherit_scoring_provenance(candidate, source)

if TYPE_CHECKING:
    from app.detectors.registry import PageText

DETECTOR_NAME = "TR_NAME_REPEAT"
PAIR_DETECTOR_NAME = "TR_NAME_PAIR"

_WORD = r"A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû"
# PDF layers often insert 10–30 spaces between given name and surname, or wrap
# with a newline. Only whitespace is allowed so a following sentence is not
# swallowed. Optional apostrophe suffix: Emine'ye / ELİTAŞ'ın.
_GAP = r"[\s\u00a0\u00ad\u2000-\u200d\u202f\-\u2010-\u2015\u2212]{0,80}"
_POSSESSIVE = r"(?:['’`´ʼ′][A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]{1,12})?"
_PAIR_GAP = re.compile(r"[\s\u00a0\u00ad\u2000-\u200d\u202f]{1,40}")
_NAME_WORD = re.compile(
    r"[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+(?:['’`´ʼ′][A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+)?"
)
_HONORIFIC_PREFIX = re.compile(
    r"^(?:av\.?|avukat|sn\.?|say[ıi]n|dr\.?|prof(?:essor)?\.?)\s+",
    re.IGNORECASE,
)
_TOKEN_SEP = re.compile(r"^[\s\u00a0\u00ad\u2000-\u200d\u202f\-\u2010-\u2015\u2212,/]*$")
_FOLD_GROUPS = (
    "iİıI",
    "çÇcC",
    "ğĞgG",
    "öÖoO",
    "şŞsS",
    "üÜuU",
    "âÂaA",
    "îÎiIıİ",
    "ûÛuU",
)


def _char_class(char: str) -> str:
    for group in _FOLD_GROUPS:
        if char in group:
            return f"[{group}]"
    if char.isalpha():
        lower, upper = char.lower(), char.upper()
        if lower != upper:
            return f"[{re.escape(lower)}{re.escape(upper)}]"
    return re.escape(char)


def _token_regex(token: str) -> str:
    return "".join(_char_class(char) for char in token)


def _without_honorific(value: str) -> str:
    compact = collapse_name(strip_possessive(value))
    stripped = _HONORIFIC_PREFIX.sub("", compact).strip()
    return stripped or compact


def variant_pattern(name: str) -> re.Pattern[str] | None:
    tokens = _without_honorific(name).split()
    if not 2 <= len(tokens) <= 4:
        return None
    if any(len(re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]", "", token)) < 2 for token in tokens):
        return None
    body = _GAP.join(_token_regex(token) + _POSSESSIVE for token in tokens)
    return re.compile(rf"(?<![{_WORD}]){body}(?![{_WORD}])")


def is_repeatable_person_name(value: str) -> bool:
    """True for 2–4 alphabetic tokens, regardless of original casing."""
    tokens = _without_honorific(value).split()
    if not 2 <= len(tokens) <= 4:
        return False
    if not all(len(re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]", "", token)) >= 2 for token in tokens):
        return False
    try:
        from app.detectors.en.common import (
            is_determiner_plus_court_head,
            is_representation_status,
            is_standalone_legal_role,
        )
    except ImportError:
        return True
    if is_standalone_legal_role(value) or is_representation_status(value):
        return False
    return not is_determiner_plus_court_head(value)


def _name_key(value: str) -> str:
    return fold_tr_identity("".join(_without_honorific(value).split()))


def _overlaps(start: int, end: int, other: EntityCandidate) -> bool:
    return start < other.end and other.start < end


def _tight_person_cover(start: int, end: int, other: EntityCandidate) -> bool:
    """True only when a real name span already covers this mention.

    Clause-sized PERSON hits are ignored: merge drops them later, and treating
    them as coverage is why later ``Uğur AKBAY`` lines disappeared.
    """
    if other.type not in _PERSON or not _overlaps(start, end, other):
        return False
    if not is_repeatable_person_name(other.text):
        return False
    return len(other.text.split()) <= 5


def iter_compact_name_spans(text: str, name_key: str) -> list[tuple[int, int, str]]:
    """Find mentions by folded letters so spacing, hyphens, and glue still hit."""
    if len(name_key) < 5:
        return []
    tokens = list(_NAME_WORD.finditer(text))
    found: list[tuple[int, int, str]] = []
    index = 0
    while index < len(tokens):
        acc = ""
        start = tokens[index].start()
        last_end = tokens[index].start()
        hit_at: int | None = None
        for cursor in range(index, len(tokens)):
            token = tokens[cursor]
            if cursor > index:
                gap = text[last_end : token.start()]
                if not _TOKEN_SEP.fullmatch(gap):
                    break
            acc += _name_key(token.group(0))
            last_end = token.end()
            if acc == name_key:
                found.append((start, token.end(), text[start : token.end()]))
                hit_at = cursor
                break
            if not name_key.startswith(acc):
                break
        index = hit_at + 1 if hit_at is not None else index + 1
    return found


def pair_adjacent_person_name_tokens(
    pages: list["PageText"],
    candidates: list[EntityCandidate],
) -> list[EntityCandidate]:
    """Join neighbouring 1-token person hits (Emine + ELİTAŞ) into a full-name seed.

    Overlay often boxes given name and surname separately. A 1-token span is not
    a repeat seed, so later ``Emine ELİTAŞ`` mentions are missed unless we
    recombine them here.
    """
    by_page: dict[int, "PageText"] = {page.page: page for page in pages}
    grouped: dict[int, list[EntityCandidate]] = {}
    for item in candidates:
        if item.type not in _PERSON:
            continue
        grouped.setdefault(item.page, []).append(item)

    found: list[EntityCandidate] = []
    seen: set[tuple[int, int, int]] = set()
    for page_num, items in grouped.items():
        page = by_page.get(page_num)
        if page is None:
            continue
        ordered = sorted(items, key=lambda item: (item.start, -item.end))
        singles = [
            item
            for item in ordered
            if len(collapse_name(strip_possessive(item.text)).split()) == 1
        ]
        for left, right in zip(singles, singles[1:]):
            if left.end > right.start:
                continue
            local_start = left.start - page.document_offset
            local_end = right.end - page.document_offset
            if local_start < 0 or local_end > len(page.text):
                continue
            gap = page.text[left.end - page.document_offset : right.start - page.document_offset]
            if not _PAIR_GAP.fullmatch(gap):
                continue
            surface = page.text[local_start:local_end]
            if not is_repeatable_person_name(surface):
                continue
            covered = any(
                other.start <= left.start
                and other.end >= right.end
                and is_repeatable_person_name(other.text)
                for other in ordered
            )
            if covered:
                continue
            key = (page_num, left.start, right.end)
            if key in seen:
                continue
            seen.add(key)
            source = left if (left.attributes or {}).get("scoring_decision") else right
            found.append(
                _inherit_scoring_provenance(
                    EntityCandidate(
                        text=surface,
                        type=left.type,
                        start=left.start,
                        end=right.end,
                        page=page_num,
                        detector=PAIR_DETECTOR_NAME,
                        method=DetectionMethod.DETERMINISTIC,
                        validated=True,
                        role=left.role or right.role,
                        reason="Adjacent given name and surname joined into a full person name.",
                        verification_level=VerificationLevel.REVIEW_RECOMMENDED,
                        verification_method="name_pair",
                        attributes={
                            "source": "name_pair",
                            "left_text": left.text,
                            "right_text": right.text,
                        },
                    ),
                    source,
                )
            )
    return found


def _seed_entities(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    seeds: list[EntityCandidate] = []
    seen: set[str] = set()
    ordered = sorted(candidates, key=lambda item: detector_rank(item.detector), reverse=True)
    for item in ordered:
        if item.type not in _PERSON:
            continue
        if not is_repeatable_person_name(item.text):
            continue
        attrs = item.attributes or {}
        # STRUCTURAL PERSON is outside scoring. Do not let form-layout guesses
        # become document-wide repeat seeds.
        if item.detector.startswith("STRUCTURAL_") or attrs.get("scoring_provenance") == "outside_scoring":
            continue
        # Local NER may emit job titles and claim phrases. Repeat only when a
        # deterministic rule already agreed on the same surface.
        if item.detector == "LOCAL_NER_EN" and not attrs.get("ner_overlap_existing_rule"):
            continue
        key = _name_key(item.text)
        if len(key) < 5 or key in seen:
            continue
        seen.add(key)
        seeds.append(item)
    seeds.sort(key=lambda item: len(collapse_name(item.text).split()), reverse=True)
    return seeds


def propagate_person_name_repeats(
    pages: list["PageText"],
    seeds: list[EntityCandidate],
) -> list[EntityCandidate]:
    """Emit extra candidates for later / variant mentions of known full names."""
    prototypes = _seed_entities(seeds)
    if not prototypes:
        return []

    found: list[EntityCandidate] = []
    for page in pages:
        for prototype in prototypes:
            key = _name_key(prototype.text)
            spans: list[tuple[int, int, str]] = []
            pattern = variant_pattern(prototype.text)
            if pattern is not None:
                spans.extend(
                    (match.start(), match.end(), match.group(0))
                    for match in pattern.finditer(page.text)
                )
            spans.extend(iter_compact_name_spans(page.text, key))
            spans.sort(key=lambda item: (-(item[1] - item[0]), item[0]))
            seen_here: set[tuple[int, int]] = set()
            for local_start, local_end, surface in spans:
                stripped = strip_possessive(surface)
                if surface.startswith(stripped) and stripped != surface:
                    surface = stripped
                    local_end = local_start + len(stripped)
                if (local_start, local_end) in seen_here:
                    continue
                seen_here.add((local_start, local_end))
                start = page.document_offset + local_start
                end = page.document_offset + local_end
                if any(_tight_person_cover(start, end, item) for item in seeds):
                    continue
                if any(_tight_person_cover(start, end, item) for item in found):
                    continue
                found.append(
                    _inherit_scoring_provenance(
                        EntityCandidate(
                            text=surface,
                            type=prototype.type,
                            start=start,
                            end=end,
                            page=page.page,
                            detector=DETECTOR_NAME,
                            method=DetectionMethod.DETERMINISTIC,
                            validated=True,
                            role=prototype.role,
                            reason="Later mention of a person name already found in this document.",
                            verification_level=VerificationLevel.REVIEW_RECOMMENDED,
                            verification_method="name_repeat",
                            attributes={
                                "source": "name_repeat",
                                "seed_text": prototype.text,
                                "seed_detector": prototype.detector,
                            },
                        ),
                        prototype,
                    )
                )
    return found
