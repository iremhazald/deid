"""Statement / testimony person grammar."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate
from app.detectors.legal.names import BARE_NAME_TOKEN, clipped_name_span
from app.detectors.legal.roles import PERSON_TRIGGERS, resolve_trigger
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_NAME_CHUNK = rf"{BARE_NAME_TOKEN}(?:[\s\u00a0\u00ad\u2000-\u200d\u202f]{{0,40}}{BARE_NAME_TOKEN}){{1,3}}"
_ROLE_BODY = "|".join(re.escape(item[0]) for item in sorted(PERSON_TRIGGERS, key=lambda item: len(item[0]), reverse=True))
_VERB = r"(?P<verb>beyanında|beyaninda|ifadesinde|savunmasında|anlatımında|anlatiminda)"

_ROLE_NAME_VERB = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<role>{_ROLE_BODY}))\s+(?P<name>{_NAME_CHUNK})\s+(?i:{_VERB})"
)
_NAME_POSS_VERB = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?P<name>{_NAME_CHUNK})['’`´ʼ′](?P<suf>in|ın|un|ün|nin|nın)\s+(?i:{_VERB})"
)
_ROLE_NAME_POSS_VERB = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<role>{_ROLE_BODY}))\s+(?P<name>{_NAME_CHUNK})['’`´ʼ′]"
    rf"(?P<suf>in|ın|un|ün|nin|nın)\s+(?i:{_VERB})"
)


def parse_statements(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()
    for pattern in (_ROLE_NAME_POSS_VERB, _ROLE_NAME_VERB, _NAME_POSS_VERB):
        for match in pattern.finditer(page.text):
            clipped = clipped_name_span(match.group("name"), match.start("name"))
            if clipped is None:
                continue
            name, start, end = clipped
            role_raw = match.groupdict().get("role") or ""
            role, entity_type = (
                resolve_trigger(role_raw) if role_raw else ("", EntityType.PERSON_NAME)
            )
            candidate = make_candidate(
                page,
                text=name,
                local_start=start,
                local_end=end,
                entity_type=entity_type,
                detector="TR_STATEMENT",
                role=role or None,
                reason="Statement / testimony grammar.",
                attributes={"trigger": match.group("verb"), "source": "statement"},
            )
            key = (candidate.start, candidate.end)
            if key in seen:
                continue
            seen.add(key)
            found.append(candidate)
    return found
