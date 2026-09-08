"""Legal party block parser for SANIK / DAVACI / DAVALI style openings."""

from __future__ import annotations

import re

from app.detectors.checksum import validate_tckn
from app.detectors.legal.birth import parse_birth
from app.detectors.legal.common import make_candidate, relation
from app.detectors.legal.names import (
    clipped_name_span,
    is_non_person_surface,
    is_workplace_or_job_title,
    iter_person_spans,
)
from app.detectors.legal.organisation import parse_companies
from app.detectors.legal.parentage import parse_parentage
from app.detectors.legal.roles import party_label_pattern, resolve_party
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_OPEN = party_label_pattern()
_NEXT_SECTION = re.compile(
    r"(?m)^\s*(?:"
    r"GEREKÇE|GEREKCE|HÜKÜM|HUKUM|KARAR|TARAFLAR|"
    r"BAŞKAN|BASKAN|ÜYE|UYE|KATİP|KATIP|"
    r"MÜDAFİ|MUDAFI|VEKİL|VEKIL"
    r")\b"
)
_TCKN = re.compile(r"(?<!\d)([1-9]\d{10})(?!\d)")
_MAX_BLOCK = 900
_PARTY_TYPES = {EntityType.CLAIMANT_NAME, EntityType.DEFENDANT_NAME}


def _block_end(text: str, value_start: int) -> int:
    limit = min(len(text), value_start + _MAX_BLOCK)
    window = text[value_start:limit]
    next_party = _OPEN.search(window, 1) if window.startswith("\n") else _OPEN.search(window)
    # Search remaining text for another party opener or a section header.
    rest = text[value_start:limit]
    candidates = []
    for match in _OPEN.finditer(text):
        if match.start() > value_start:
            candidates.append(match.start())
            break
    header = _NEXT_SECTION.search(text, value_start + 1, limit)
    if header:
        candidates.append(header.start())
    blank = re.search(r"\n\s*\n", rest)
    if blank:
        candidates.append(value_start + blank.start())
    return min(candidates) if candidates else limit


def parse_party_blocks(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    for opener in _OPEN.finditer(page.text):
        role, entity_type = resolve_party(opener.group(1))
        value_start = opener.end()
        value_end = _block_end(page.text, value_start)
        block = page.text[value_start:value_end]
        if len(block.strip()) < 3:
            continue

        inner = PageText(page=page.page, text=block, document_offset=page.document_offset + value_start)
        name_matches = iter_person_spans(block)
        person = None
        person_links = []
        extras: list[EntityCandidate] = []
        people: list[EntityCandidate] = []
        for name_match in name_matches:
            clipped = clipped_name_span(name_match.group(1), value_start + name_match.start(1))
            if not clipped:
                continue
            name, local_start, local_end = clipped
            if is_non_person_surface(name) or is_workplace_or_job_title(name):
                continue
            if re.search(r"(?i)(?:a\.?\s*ş\.?|\bltd\.?|limited\s+şirket)", name):
                continue
            item = make_candidate(
                page,
                text=name,
                local_start=local_start,
                local_end=local_end,
                entity_type=entity_type,
                detector="TR_LEGAL_PARTY",
                role=role or None,
                reason="Person heading a legal party block.",
                attributes={"legal_role": opener.group(1), "source": "party_block"},
            )
            people.append(item)
        person = people[0] if people else None

        for relative in parse_parentage(inner):
            dumped = relative.model_dump()
            rels = list(dumped.get("relations") or [])
            attrs = {**(dumped.get("attributes") or {}), "source": "party_block"}
            if person:
                rels.append(relation("PARENT_OF", target=person))
                person_links.append(relation("CHILD_OF", target=relative))
            extras.append(
                relative.model_copy(
                    update={"detector": "TR_LEGAL_PARTY", "attributes": attrs, "relations": rels}
                )
            )

        for birth in parse_birth(inner):
            dumped = birth.model_dump()
            attrs = {**(dumped.get("attributes") or {}), "source": "party_block"}
            if person:
                person_links.append(relation("HAS_BIRTH_INFO", target=birth))
            extras.append(
                birth.model_copy(update={"detector": "TR_LEGAL_PARTY", "attributes": attrs})
            )

        for match in _TCKN.finditer(block):
            if not validate_tckn(match.group(1)):
                continue
            ident_links = []
            if person:
                ident_links.append(relation("IDENTIFIES", target=person))
            ident = make_candidate(
                page,
                text=match.group(1),
                local_start=value_start + match.start(1),
                local_end=value_start + match.end(1),
                entity_type=EntityType.NATIONAL_ID,
                detector="TR_LEGAL_PARTY",
                reason="TCKN inside a legal party block.",
                attributes={"source": "party_block"},
                relations=ident_links,
            )
            if person:
                person_links.append(relation("HAS_NATIONAL_ID", target=ident))
            extras.append(ident)

        company_found = False
        for company in parse_companies(inner):
            company_found = True
            extras.append(
                company.model_copy(
                    update={
                        "type": entity_type if entity_type in _PARTY_TYPES else company.type,
                        "detector": "TR_LEGAL_PARTY",
                        "role": role or None,
                        "reason": "Company heading a legal party block.",
                        "attributes": {
                            **company.attributes,
                            "legal_role": opener.group(1),
                            "source": "party_block",
                        },
                    }
                )
            )

        heading = _party_heading_value(block)
        if heading and not people and not company_found:
            name, local_start, local_end = heading
            people.append(
                make_candidate(
                    page,
                    text=name,
                    local_start=value_start + local_start,
                    local_end=value_start + local_end,
                    entity_type=entity_type or EntityType.PERSON_NAME,
                    detector="TR_LEGAL_PARTY",
                    role=role or None,
                    reason="Name heading a legal party block.",
                    attributes={"legal_role": opener.group(1), "source": "party_block"},
                )
            )

        if people:
            person_links.append(relation("PARTY_ROLE", label=role or opener.group(1)))
            found.append(people[0].model_copy(update={"relations": person_links}))
            found.extend(people[1:])
        found.extend(extras)
    return found


def _party_heading_value(block: str) -> tuple[str, int, int] | None:
    """First-line value after a party opener, stripping a trailing dash."""
    first = block.split("\n", 1)[0]
    text = first.strip().rstrip(" \t-–")
    if len(text) < 3:
        return None
    local = first.find(text)
    if local < 0:
        return None
    return text, local, local + len(text)
