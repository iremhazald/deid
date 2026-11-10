"""Role-triggered person detection in running text."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate
from app.detectors.legal.names import (
    BARE_NAME_TOKEN,
    clip_name_beside_role,
    clipped_name_span,
    is_legal_role_label,
    is_non_person_surface,
    is_workplace_or_job_title,
    strip_possessive,
)
from app.detectors.legal.roles import PERSON_TRIGGERS, officer_role_body, resolve_trigger
from app.detectors.registry import PageText
from app.detectors.textutil import fold_tr_identity
from app.domain.models import EntityCandidate, EntityType

_ASCII_TR = str.maketrans(
    {"ğ": "g", "ü": "u", "ş": "s", "ı": "i", "ö": "o", "ç": "c", "â": "a"}
)

_TRIGGERS = sorted((item[0] for item in PERSON_TRIGGERS), key=len, reverse=True)
_TRIGGER_BODY = "|".join(re.escape(item) for item in _TRIGGERS)
# ve / hem / ile break a name. They must not glue the title before "tanık"
# onto the role, or two people into one span.
_NAME_PIECE = (
    rf"(?!(?i:ve|hem|ile|veya)(?![\wÇĞİÖŞÜçğıöşü]))"
    rf"{BARE_NAME_TOKEN}(?:['’`´ʼ′][A-Za-zÇĞİÖŞÜçğıöşü]{{1,8}})?"
)
# A name stays on one line. The role may still sit on the previous line.
_NAME_GAP = r"[^\S\r\n\u2028\u2029]{0,40}"
_NAME_CHUNK = rf"{_NAME_PIECE}(?:{_NAME_GAP}{_NAME_PIECE}){{1,3}}"
_TITLED_NAME = rf"{_NAME_PIECE}(?:{_NAME_GAP}{_NAME_PIECE}){{0,3}}"
_SHORT_TITLED_NAME = rf"{_NAME_PIECE}(?:{_NAME_GAP}{_NAME_PIECE}){{0,1}}"
_ROLE_THEN_NAME = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<role>{_TRIGGER_BODY}))(?![\wÇĞİÖŞÜçğıöşü])"
    rf"(?:\s*-\s*\(\s*\d+\s*\)\s*-)?"
    rf"\s*:?\s+(?P<name>{_NAME_CHUNK})"
)
# Prosecutor and clerk labels need explicit İ/I folding. The shared trigger
# list still resolves the role; this pattern only finds the span.
_OFFICER_BODY = officer_role_body()
_OFFICER_THEN_NAME = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?P<role>{_OFFICER_BODY})(?![\wÇĞİÖŞÜçğıöşü])"
    rf"(?:\s*-\s*\(\s*\d+\s*\)\s*-)?"
    rf"\s*:?\s+(?P<name>{_NAME_CHUNK})",
    re.IGNORECASE,
)
_NAME_THEN_OFFICER = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?P<name>{_NAME_CHUNK})\s+"
    rf"(?P<role>{_OFFICER_BODY})(?![\wÇĞİÖŞÜçğıöşü])",
    re.IGNORECASE,
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
# Courtesy titles stay outside the span ("Bay Yılmaz"). Professional titles
# (Prof., Dr., Av.) are part of the labeled span, including when the period
# is glued to the next title or the given name: "Prof.Dr.", "Dr.Mehmet".
_COURTESY_TITLE = r"bayan|bay|say[ıi]n|sn"
_PROFESSIONAL_TITLE = r"professor|prof|avukat|av|h[âa]k[iı]m|yarg[ıi][çc]|dr"
_PROFESSIONAL_CHAIN = rf"(?:(?:{_PROFESSIONAL_TITLE})\.?\s*){{1,3}}"
_COURTESY_THEN_NAME = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<title>{_COURTESY_TITLE}))"
    rf"(?:\.|(?![A-Za-zÇĞİÖŞÜçğıöşü]))\s*"
    rf"(?P<name>{_SHORT_TITLED_NAME})"
)
_PROFESSIONAL_THEN_NAME = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])(?i:(?P<titles>{_PROFESSIONAL_CHAIN}))"
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


_ATTENDANCE = re.compile(r"(?i)toplant[ıi](?:ya|da|nda)|seminer(?:e|de|ine)")
_SPORTS = re.compile(r"(?i)futbol|basketbol|voleybol|stadyum|d[üu]d[üu]k|\bmac[ıi]?\b|maç")


def _emit(
    page: PageText,
    name_raw: str,
    name_start: int,
    role_raw: str,
    *,
    before_role: bool,
) -> EntityCandidate | None:
    folded_role = fold_tr_identity(role_raw)
    left = page.text[max(0, name_start - 64) : name_start]
    # "toplantıya katılan" is attendance, not the intervening-party role.
    if folded_role in {"katilan", "katilanlar"} and _ATTENDANCE.search(left):
        return None
    # A sports referee is not an arbitrator. Colon labels use the party parser.
    if (folded_role == "hakem" or folded_role.startswith("hakem ")) and _SPORTS.search(
        page.text[max(0, name_start - 80) : name_start + 48]
    ):
        return None
    clipped = clip_name_beside_role(name_raw, name_start, before_role=before_role)
    if clipped is None:
        return None
    name, start, end = clipped
    if is_non_person_surface(name) or is_legal_role_label(name):
        return None
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
    page: PageText,
    name_raw: str,
    name_start: int,
    title: str,
    *,
    include_title: bool = False,
    span_start: int | None = None,
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
    if include_title and span_start is not None and span_start <= start:
        start = span_start
        name = page.text[start:end]
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

    for match in _COURTESY_THEN_NAME.finditer(page.text):
        take(
            _emit_titled(
                page,
                match.group("name"),
                match.start("name"),
                match.group("title"),
            )
        )
    for match in _PROFESSIONAL_THEN_NAME.finditer(page.text):
        before = fold_tr_identity(page.text[max(0, match.start() - 16) : match.start()])
        if "arabulucu" in before:
            continue
        take(
            _emit_titled(
                page,
                match.group("name"),
                match.start("name"),
                match.group("titles"),
                include_title=True,
                span_start=match.start(),
            )
        )
    for pattern, before_role in (
        (_AV_THEN_NAME, False),
        (_OFFICER_THEN_NAME, False),
        (_NAME_THEN_OFFICER, True),
        (_ROLE_THEN_NAME, False),
        (_NAME_THEN_ROLE, True),
    ):
        for match in pattern.finditer(page.text):
            take(
                _emit(
                    page,
                    match.group("name"),
                    match.start("name"),
                    match.group("role"),
                    before_role=before_role,
                )
            )
            cursor = match.end("name")
            for extra in _AND_NAME.finditer(page.text[cursor : cursor + 80]):
                take(
                    _emit(
                        page,
                        extra.group("name"),
                        cursor + extra.start("name"),
                        match.group("role"),
                        before_role=False,
                    )
                )
    return found
