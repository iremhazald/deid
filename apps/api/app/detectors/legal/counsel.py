"""Counsel / lawyer block parser."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate, relation
from app.detectors.legal.names import clipped_name_span, first_person_span
from app.detectors.legal.roles import counsel_label_pattern, resolve_counsel
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_OPEN = counsel_label_pattern()
_TITLE = re.compile(r"^\s*(?:Av\.?|Avukat)\s+", re.IGNORECASE)
_REG = re.compile(r"\b(\d{5,6})\b")
_MAX_VALUE = 240


def parse_counsel(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    for opener in _OPEN.finditer(page.text):
        role = resolve_counsel(opener.group(1))
        value_start = opener.end()
        line_end = page.text.find("\n", value_start)
        if line_end < 0:
            line_end = len(page.text)
        value_end = min(line_end, value_start + _MAX_VALUE)
        value = page.text[value_start:value_end]
        rest = _TITLE.sub("", value, count=1)
        shift = len(value) - len(rest)
        name_match = first_person_span(rest)
        if name_match is None:
            continue
        clipped = clipped_name_span(name_match.group(1), value_start + shift + name_match.start(1))
        if clipped is None:
            continue
        name, abs_start, abs_end = clipped
        linked: list[EntityCandidate] = []
        links = [relation("LAWYER_FOR", label=role)]

        after = rest[name_match.end(1) :]
        after_start = value_start + shift + name_match.end(1)
        address_part = after.lstrip(" ,;")
        address_shift = len(after) - len(address_part)
        if len(address_part) >= 8 and re.search(
            r"\b(?:Mah\.?|Mahallesi|Cad\.?|Cd\.?|Caddesi|Sk\.?|Sok\.?|No:?)\b",
            address_part,
            re.IGNORECASE,
        ):
            cut = re.split(r"\s{2,}|\t", address_part, maxsplit=1)[0].strip(" .;")
            if len(cut) >= 8:
                addr_start = after_start + address_shift
                address = make_candidate(
                    page,
                    text=cut,
                    local_start=addr_start,
                    local_end=addr_start + len(cut),
                    entity_type=EntityType.ADDRESS,
                    detector="TR_COUNSEL_BLOCK",
                    reason="Address in a counsel block.",
                    attributes={"source": "counsel_block"},
                )
                links.append(relation("HAS_ADDRESS", target=address))
                linked.append(address)

        for match in _REG.finditer(value):
            # Registry only if it sits after the name, not a street number.
            if match.start() < shift + name_match.start(1):
                continue
            ctx = value[max(0, match.start() - 8) : match.start()].lower()
            if re.search(r"\bno:?\s*$", ctx):
                continue
            ident = make_candidate(
                page,
                text=match.group(1),
                local_start=value_start + match.start(1),
                local_end=value_start + match.end(1),
                entity_type=EntityType.PROFESSIONAL_ID,
                detector="TR_COUNSEL_BLOCK",
                role=role,
                reason="Professional id in a counsel block.",
                attributes={"kind": "REGISTRY_NUMBER", "source": "counsel_block"},
            )
            links.append(relation("HAS_PROFESSIONAL_ID", target=ident))
            linked.append(ident)
            break

        found.append(
            make_candidate(
                page,
                text=name,
                local_start=abs_start,
                local_end=abs_end,
                entity_type=EntityType.LAWYER_NAME,
                detector="TR_COUNSEL_BLOCK",
                role=role,
                reason="Counsel / vekil block.",
                attributes={"legal_role": opener.group(1), "source": "counsel_block"},
                relations=links,
            )
        )
        found.extend(linked)
    return found
