"""'ismi geçen / adlı / şahıs' person triggers."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate
from app.detectors.legal.names import BARE_NAME_TOKEN, clipped_name_span
from app.detectors.legal.roles import MENTION_TRIGGERS, resolve_trigger
from app.detectors.registry import PageText
from app.detectors.textutil import fold_tr_identity
from app.domain.models import EntityCandidate, EntityType

_TRIG = "|".join(re.escape(item) for item in sorted(MENTION_TRIGGERS, key=len, reverse=True))
_NAME_PIECE = rf"{BARE_NAME_TOKEN}(?:['’`´ʼ′][A-Za-zÇĞİÖŞÜçğıöşü]{{1,8}})?"
_NAME_CHUNK = rf"{_NAME_PIECE}(?:[\s\u00a0\u00ad\u2000-\u200d\u202f]{{0,40}}{_NAME_PIECE}){{1,3}}"
# ismi geçen sanık X  /  adlı kişi Y  /  şahıs Z
_AFTER_TRIGGER = re.compile(
    rf"(?i:(?P<trig>{_TRIG}))(?:\s+(?i:(?P<role>sanık|sanik|kişi|kisi|şahıs|sahis|davalı|davali|davacı|davaci|tanık|tanik)))?"
    rf"\s+(?P<name>{_NAME_CHUNK})"
)
# X isimli kişi / X adlı sanık
_BEFORE_TRIGGER = re.compile(
    rf"(?P<name>{_NAME_CHUNK})\s+(?i:(?P<trig>isimli|adlı))\b"
)


def _is_judicial_adli(trigger: str) -> bool:
    """``ADLİ`` (judicial) must not be treated as ``adlı`` (named)."""
    compact = re.sub(r"\s+", "", trigger)
    if fold_tr_identity(compact) != "adli":
        return False
    return compact[-1:] in "iİ"


def parse_mentioned(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()
    for match in _AFTER_TRIGGER.finditer(page.text):
        if _is_judicial_adli(match.group("trig")):
            continue
        clipped = clipped_name_span(match.group("name"), match.start("name"))
        if clipped is None:
            continue
        name, start, end = clipped
        role_raw = match.group("role") or ""
        role, entity_type = resolve_trigger(role_raw) if role_raw else ("", EntityType.PERSON_NAME)
        candidate = make_candidate(
            page,
            text=name,
            local_start=start,
            local_end=end,
            entity_type=entity_type,
            detector="TR_MENTIONED_PERSON",
            role=role or None,
            reason="Mention trigger (ismi geçen / adlı / şahıs).",
            attributes={"trigger": match.group("trig"), "source": "mentioned"},
        )
        key = (candidate.start, candidate.end)
        if key in seen:
            continue
        seen.add(key)
        found.append(candidate)
    for match in _BEFORE_TRIGGER.finditer(page.text):
        if _is_judicial_adli(match.group("trig")):
            continue
        clipped = clipped_name_span(match.group("name"), match.start("name"))
        if clipped is None:
            continue
        name, start, end = clipped
        parts = name.split()
        if len(parts) > 2:
            kept = parts[-2:]
            raw = match.group("name")
            tail = raw.rfind(kept[0])
            if tail >= 0:
                name = " ".join(kept)
                start = match.start("name") + tail
                end = match.start("name") + tail + len(raw[tail:].rstrip())
        candidate = make_candidate(
            page,
            text=name,
            local_start=start,
            local_end=end,
            entity_type=EntityType.PERSON_NAME,
            detector="TR_MENTIONED_PERSON",
            reason="Mention trigger (isimli / adlı).",
            attributes={"trigger": match.group("trig"), "source": "mentioned"},
        )
        key = (candidate.start, candidate.end)
        if key in seen:
            continue
        seen.add(key)
        found.append(candidate)
    return found
