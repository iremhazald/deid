"""Role-triggered person detection in running text."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate
from app.detectors.legal.names import (
    BARE_NAME_TOKEN,
    clipped_name_span,
    is_legal_role_label,
    is_non_person_surface,
    is_workplace_or_job_title,
    strip_possessive,
)
from app.detectors.legal.roles import PERSON_TRIGGERS, resolve_trigger
from app.detectors.registry import PageText
from app.detectors.textutil import fold_tr_identity
from app.domain.models import EntityCandidate, EntityType

_ASCII_TR = str.maketrans(
    {"ğ": "g", "ü": "u", "ş": "s", "ı": "i", "ö": "o", "ç": "c", "â": "a"}
)

_TRIGGERS = sorted((item[0] for item in PERSON_TRIGGERS), key=len, reverse=True)
_TRIGGER_BODY = "|".join(re.escape(item) for item in _TRIGGERS)
_NAME_PIECE = rf"{BARE_NAME_TOKEN}(?:['’`´ʼ′][A-Za-zÇĞİÖŞÜçğıöşü]{{1,8}})?"
_NAME_GAP = r"[\s\u00a0\u00ad\u2000-\u200d\u202f]{0,40}"
_NAME_CHUNK = rf"{_NAME_PIECE}(?:{_NAME_GAP}{_NAME_PIECE}){{1,3}}"
_TITLED_NAME = rf"{_NAME_PIECE}(?:{_NAME_GAP}{_NAME_PIECE}){{0,3}}"
_SHORT_TITLED_NAME = rf"{_NAME_PIECE}(?:{_NAME_GAP}{_NAME_PIECE}){{0,1}}"
_ROLE_THEN_NAME = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<role>{_TRIGGER_BODY}))(?![\wÇĞİÖŞÜçğıöşü])"
    rf"(?:\s*-\s*\(\s*\d+\s*\)\s*-)?"
    rf"\s*:?\s+(?P<name>{_NAME_CHUNK})"
)
# OCR often glues the period to the given name: "Av.İrem Hazal Deveci".
_AV_THEN_NAME = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<role>av))\.?\s*(?P<name>{_NAME_CHUNK})"
)
_NAME_THEN_ROLE = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?P<name>{_NAME_CHUNK})\s+"
    rf"(?i:(?P<role>{_TRIGGER_BODY}))(?![\wÇĞİÖŞÜçğıöşü])"
)
_AND_NAME = re.compile(rf"(?i:\s+ve\s+)(?P<name>{_NAME_CHUNK})")
# Courtesy / professional titles. Title stays outside the person span, matching
# English EN_TITLED_PERSON so "Bay Yılmaz" can seed a possible-match candidate.
_COURTESY_TITLE = r"bayan|bay|say[ıi]n|sn"
_PROFESSIONAL_TITLE = r"professor|prof|avukat|av|h[âa]k[iı]m|yarg[ıi][çc]|dr"
_COURTESY_THEN_NAME = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<title>{_COURTESY_TITLE}))"
    rf"(?:\.|(?![A-Za-zÇĞİÖŞÜçğıöşü]))\s*"
    rf"(?P<name>{_SHORT_TITLED_NAME})"
)
_PROFESSIONAL_THEN_NAME = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<title>{_PROFESSIONAL_TITLE}))"
    rf"(?:\.|(?![A-Za-zÇĞİÖŞÜçğıöşü]))\s*"
    rf"(?P<name>{_TITLED_NAME})"
)
_BLOCKED_TITLED_STEMS = (
    "mahkeme",
    "hakimlig",
    "nobetci",
    "savcilik",
    "mudurluk",
    "baskanlik",
    "heyet",
    "kurul",
)


def _title_type(title: str) -> tuple[EntityType, str | None]:
    folded = fold_tr_identity(title).replace(".", "")
    if folded.startswith("av"):
        return EntityType.LAWYER_NAME, "COUNSEL"
    if folded.startswith("hakim") or folded.startswith("yargic"):
        return EntityType.JUDGE_NAME, "JUDGE"
    return EntityType.PERSON_NAME, None


def _titled_body_ok(name: str) -> bool:
    if not name or len(name) < 2:
        return False
    if is_non_person_surface(name) or is_workplace_or_job_title(name):
        return False
    if is_legal_role_label(name):
        return False
    folded = fold_tr_identity(name).translate(_ASCII_TR)
    for mark in "'’′`´ʼ":
        folded = folded.replace(mark, "")
    return not any(stem in folded for stem in _BLOCKED_TITLED_STEMS)


def _emit(page: PageText, name_raw: str, name_start: int, role_raw: str) -> EntityCandidate | None:
    clipped = clipped_name_span(name_raw, name_start)
    if clipped is None:
        return None
    name, start, end = clipped
    role, entity_type = resolve_trigger(role_raw)
    return make_candidate(
        page,
        text=name,
        local_start=start,
        local_end=end,
        entity_type=entity_type,
        detector="TR_ROLE_PERSON",
        role=role or None,
        reason="Legal role trigger adjacent to a person name.",
        attributes={"legal_role": role_raw, "source": "role_trigger"},
    )


def _emit_titled(
    page: PageText, name_raw: str, name_start: int, title: str
) -> EntityCandidate | None:
    """Honorific / short professional title. Allows a single surname body."""
    clipped = clipped_name_span(name_raw, name_start)
    if clipped is not None:
        name, start, end = clipped
        if not _titled_body_ok(name):
            return None
    else:
        name = strip_possessive(name_raw.strip())
        if not _titled_body_ok(name):
            return None
        letters = [char for char in name if char.isalpha()]
        if len(letters) < 2:
            return None
        local = name_raw.find(name) if name in name_raw else 0
        start = name_start + max(local, 0)
        end = start + len(name)
    entity_type, role = _title_type(title)
    return make_candidate(
        page,
        text=name,
        local_start=start,
        local_end=end,
        entity_type=entity_type,
        detector="TR_ROLE_PERSON",
        role=role,
        reason="Turkish courtesy or professional title before a name.",
        attributes={"legal_role": title, "source": "honorific_title"},
    )


def parse_role_persons(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()

    def take(candidate: EntityCandidate | None) -> None:
        if candidate is None:
            return
        key = (candidate.start, candidate.end)
        if key in seen:
            return
        seen.add(key)
        found.append(candidate)

    for pattern in (_COURTESY_THEN_NAME, _PROFESSIONAL_THEN_NAME):
        for match in pattern.finditer(page.text):
            take(
                _emit_titled(
                    page,
                    match.group("name"),
                    match.start("name"),
                    match.group("title"),
                )
            )
    for pattern in (_AV_THEN_NAME, _ROLE_THEN_NAME, _NAME_THEN_ROLE):
        for match in pattern.finditer(page.text):
            take(_emit(page, match.group("name"), match.start("name"), match.group("role")))
            cursor = match.end("name")
            for extra in _AND_NAME.finditer(page.text[cursor : cursor + 80]):
                take(
                    _emit(
                        page,
                        extra.group("name"),
                        cursor + extra.start("name"),
                        match.group("role"),
                    )
                )
    return found
