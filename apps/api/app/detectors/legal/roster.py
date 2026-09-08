"""Judicial roster parser: ROLE : PERSON_NAME [REGISTRY] and footer ROLE NUMBER."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate, relation
from app.detectors.legal.names import clipped_name_span, strip_possessive
from app.detectors.legal.roles import resolve_roster, roster_label_pattern
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_LABEL = roster_label_pattern()
_LINE_FULL = re.compile(
    r"(?P<label>[^\n:]{2,40})\s*:\s*"
    r"(?P<name>[A-ZÇĞİÖŞÜÂÎÛa-zçğıöşüâîû'’.\s]{3,80}?)"
    r"(?P<reg>\d{5,6})\b"
)
_LINE_NAME = re.compile(
    r"(?P<label>[^\n:]{2,40})\s*:\s*"
    r"(?P<name>[A-ZÇĞİÖŞÜÂÎÛa-zçğıöşüâîû'’.\s]{3,80}?)"
    r"(?=\s*(?:\n|$))"
)
_FOOTER_ID = re.compile(
    r"(?i)(?<!\w)(?P<label>başkan|baskan|üye|uye|hâkim|hakim|yargıç|yargic|"
    r"kâtip|katip|c\s*\.?\s*savc[iıIİ]s[iıIİ]|"
    r"cumhur[iıIİ]yet\s+savc[iıIİ]s[iıIİ]|savc[iıIİ])"
    r"\s+(?P<reg>\d{5,6})\b"
)


def parse_roster(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen_people: set[tuple[int, int]] = set()
    seen_regs: set[tuple[int, int]] = set()

    for match in _LINE_FULL.finditer(page.text):
        emitted = _emit_named_line(page, match, with_registry=True)
        if not emitted:
            continue
        person, registry = emitted
        seen_people.add((person.start, person.end))
        seen_regs.add((registry.start, registry.end))
        found.extend((person, registry))

    for match in _LINE_NAME.finditer(page.text):
        if _LABEL.search(f"{match.group('label').strip()}:") is None:
            continue
        person = _emit_person(page, match)
        if person is None:
            continue
        key = (person.start, person.end)
        if key in seen_people:
            continue
        seen_people.add(key)
        found.append(person)

    for match in _FOOTER_ID.finditer(page.text):
        local_start, local_end = match.start("reg"), match.end("reg")
        abs_start = page.document_offset + local_start
        abs_end = page.document_offset + local_end
        if (abs_start, abs_end) in seen_regs:
            continue
        role, _entity_type = resolve_roster(match.group("label"))
        registry = make_candidate(
            page,
            text=match.group("reg"),
            local_start=local_start,
            local_end=local_end,
            entity_type=EntityType.PROFESSIONAL_ID,
            detector="TR_JUDICIAL_ROSTER",
            role=role or "JUDGE",
            reason="Registry number attached to a judicial roster role.",
            attributes={"kind": "REGISTRY_NUMBER", "legal_role": match.group("label")},
        )
        seen_regs.add((registry.start, registry.end))
        found.append(registry)

    return found


def _emit_named_line(
    page: PageText,
    match: re.Match[str],
    *,
    with_registry: bool,
) -> tuple[EntityCandidate, EntityCandidate] | None:
    label = match.group("label").strip()
    if _LABEL.search(f"{label}:") is None:
        return None
    person = _emit_person(page, match)
    if person is None or not with_registry:
        return None
    role, _entity_type = resolve_roster(label)
    registry = make_candidate(
        page,
        text=match.group("reg"),
        local_start=match.start("reg"),
        local_end=match.end("reg"),
        entity_type=EntityType.PROFESSIONAL_ID,
        detector="TR_JUDICIAL_ROSTER",
        role=role or None,
        reason="Registry number attached to a judicial roster role.",
        attributes={"kind": "REGISTRY_NUMBER", "legal_role": label},
        relations=[relation("IDENTIFIES", target=person, label=role or None)],
    )
    person = person.model_copy(
        update={"relations": [relation("HAS_PROFESSIONAL_ID", target=registry)]}
    )
    return person, registry


def _emit_person(page: PageText, match: re.Match[str]) -> EntityCandidate | None:
    label = match.group("label").strip()
    if _LABEL.search(f"{label}:") is None:
        return None
    name_raw = strip_possessive(match.group("name"))
    clipped = clipped_name_span(name_raw, match.start("name"))
    if clipped is None:
        return None
    name, name_start, name_end = clipped
    role, entity_type = resolve_roster(label)
    return make_candidate(
        page,
        text=name,
        local_start=name_start,
        local_end=name_end,
        entity_type=entity_type,
        detector="TR_JUDICIAL_ROSTER",
        role=role or None,
        reason="Judicial roster line.",
        attributes={"legal_role": label, "source": "roster"},
    )
