"""Legal role labels strengthen PERSON candidates. They do not create identity tokens."""

from __future__ import annotations

import re

from app.detectors.en.common import (
    EN_COMPACT_INITIALS_TOKEN,
    EN_FULL_NAME,
    EN_INITIALS_GROUP,
    EN_INITIAL_TOKEN,
    EN_SURNAME_PHRASE,
    EN_TITLED_NAME_BODY,
    alt_pattern,
    fold_en,
    in_trading_as_context,
    is_company_surface,
    is_determiner_plus_court_head,
    is_generic_court_term,
    is_known_en_first_name,
    is_representation_status,
    is_standalone_legal_role,
    looks_like_legal_heading,
    looks_like_person_name,
    looks_like_titled_name_body,
    make_candidate,
    seed,
    strip_en_possessive,
    titled_name_has_initials,
)
from app.detectors.en.vocab import (
    COUNSEL_ROLES,
    DECISION_ROLES,
    EXPERT_ROLES,
    PARTY_ROLES,
    PERSON_TITLES,
    ordinal_party_role_labels,
)
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_ROLE_MAP: tuple[tuple[str, str, EntityType], ...] = tuple(
    [(label, role, EntityType.PERSON_NAME) for label, role in PARTY_ROLES]
    + [(label, role, EntityType.PERSON_NAME) for label, role in ordinal_party_role_labels()]
    + [(label, role, EntityType.LAWYER_NAME) for label, role in COUNSEL_ROLES]
    + [
        (
            label,
            role,
            EntityType.JUDGE_NAME if role == "JUDGE" else EntityType.PERSON_NAME,
        )
        for label, role in DECISION_ROLES
    ]
    + [
        (
            label,
            role,
            EntityType.EXPERT_NAME if role == "EXPERT" else EntityType.PERSON_NAME,
        )
        for label, role in EXPERT_ROLES
    ]
)
_ROLE_LABELS = sorted((item[0] for item in _ROLE_MAP), key=len, reverse=True)
_ROLE_BODY = "|".join(re.escape(item) for item in _ROLE_LABELS)
_ROLE_THEN_NAME = re.compile(
    rf"(?<![A-Za-z])(?P<role>(?i:{_ROLE_BODY}))(?![A-Za-z])"
    rf"(?:[ \t]*[-–:][ \t\r\n]*|[ \t]+|[ \t]*\n[ \t]*)"
    rf"(?P<name>{EN_TITLED_NAME_BODY})(?![A-Za-z])"
)
_NAME_THEN_ROLE = re.compile(
    rf"(?<![A-Za-z])(?P<name>{EN_FULL_NAME})\s*,?\s+"
    rf"(?P<role>(?i:{_ROLE_BODY}))(?![A-Za-z])"
)
_NAME_COMMA_COUNSEL = re.compile(
    rf"(?<![A-Za-z])(?P<name>{EN_INITIALS_GROUP}[ \t]+{EN_SURNAME_PHRASE}|{EN_FULL_NAME})"
    rf"\s*,\s*(?P<role>(?i:counsel|solicitor|barrister|attorney|lawyer))(?![A-Za-z])"
)
_JUSTICE_OF = re.compile(r"(?i)\b(?:ministry|department|administration)\s+of\s+justice\b")
_DECISION_ROLE_KEYS = frozenset(label for label, _role in DECISION_ROLES)
_ROLE_OR_TITLE_HEADS = frozenset(
    {fold_en(title) for title in PERSON_TITLES}
    | {fold_en(label.split()[0]) for label, _role in DECISION_ROLES}
    | {fold_en(label.split()[0]) for label, _role in PARTY_ROLES}
    | {fold_en(label.split()[0]) for label, _role in COUNSEL_ROLES}
)
_LEFT_TITLE_OR_INITIAL = re.compile(
    rf"(?:(?i:{alt_pattern(PERSON_TITLES)})\.?|{EN_COMPACT_INITIALS_TOKEN}|{EN_INITIAL_TOKEN})\s+$"
)


def _resolve(label: str) -> tuple[str, EntityType]:
    key = fold_en(label)
    for name, role, entity_type in _ROLE_MAP:
        if name == key:
            return role, entity_type
    return "", EntityType.PERSON_NAME


def _name_starts_with_role_or_title(name: str) -> bool:
    tokens = name.split()
    return bool(tokens) and fold_en(tokens[0].rstrip(".")) in _ROLE_OR_TITLE_HEADS


def _preceded_by_title_or_initial(page: PageText, start: int) -> bool:
    left = page.text[max(0, start - 24) : start]
    return bool(_LEFT_TITLE_OR_INITIAL.search(left))


def _name_plus_role_is_longer_role(name: str, role_raw: str) -> bool:
    """'The Employment' + 'Judge' is the role Employment Judge, not a person."""
    tokens = [fold_en(token) for token in name.split() if token]
    role = fold_en(role_raw)
    if not tokens or not role:
        return False
    known = {fold_en(label) for label in _ROLE_LABELS}
    for take in (1, 2):
        if len(tokens) >= take and " ".join(tokens[-take:] + [role]) in known:
            return True
    return False


def _acceptable_role_name(name: str, role_raw: str) -> bool:
    if _name_starts_with_role_or_title(name):
        return False
    if is_determiner_plus_court_head(name):
        return False
    if is_standalone_legal_role(name) or is_representation_status(name):
        return False
    if is_generic_court_term(name) or looks_like_legal_heading(name):
        return False
    if looks_like_person_name(name):
        return True
    if not looks_like_titled_name_body(name):
        role_key = fold_en(role_raw)
        return role_key == "justice" and bool(re.fullmatch(r"[A-Z][a-z]+|[A-Z]{2,}", name))
    role_key = fold_en(role_raw)
    if titled_name_has_initials(name):
        return True
    if role_key in _DECISION_ROLE_KEYS:
        return True
    return False


def _emit(
    page: PageText, name_raw: str, start: int, role_raw: str
) -> EntityCandidate | None:
    name = strip_en_possessive(name_raw)
    if is_company_surface(name) or in_trading_as_context(page.text, start):
        return None
    if not _acceptable_role_name(name, role_raw):
        return None
    if fold_en(role_raw) == "justice":
        left = page.text[max(0, start - 40) : start]
        if _JUSTICE_OF.search(left) or "of " in fold_en(left[-8:]):
            return None
    role, entity_type = _resolve(role_raw)
    extra = seed(("en_legal_role_label", 4), ("en_party_label", 3))
    if role == "COUNSEL":
        extra = seed(("en_legal_role_label", 4), ("en_counsel_context", 4))
    tokens = name.split()
    if tokens and is_known_en_first_name(tokens[0]):
        extra = extra + seed(("en_first_name_lexicon", 2), source="lexicon")
    return make_candidate(
        page,
        text=name,
        local_start=start,
        local_end=start + len(name),
        entity_type=entity_type,
        detector="EN_ROLE_PERSON",
        role=role or None,
        reason="English legal role adjacent to a person name.",
        attributes={
            "legal_role": role_raw,
            "source": "en_role_trigger",
            "identity_resolved": False,
            "evidence": extra,
        },
    )


def parse_legal_roles(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()

    def take(item: EntityCandidate | None) -> None:
        if item is None:
            return
        key = (item.start, item.end)
        if key in seen:
            return
        seen.add(key)
        found.append(item)

    for match in _ROLE_THEN_NAME.finditer(page.text):
        if fold_en(match.group("role")) in {"justice", "employment judge", "judge"}:
            prefix = page.text[max(0, match.start() - 28) : match.start()]
            if re.search(r"(?i)\b(?:ministry|department|administration)\s+of\s+$", prefix):
                continue
        take(_emit(page, match.group("name"), match.start("name"), match.group("role")))
    for match in _NAME_THEN_ROLE.finditer(page.text):
        if _preceded_by_title_or_initial(page, match.start("name")):
            continue
        if _name_plus_role_is_longer_role(match.group("name"), match.group("role")):
            continue
        take(_emit(page, match.group("name"), match.start("name"), match.group("role")))
    for match in _NAME_COMMA_COUNSEL.finditer(page.text):
        if _preceded_by_title_or_initial(page, match.start("name")):
            continue
        take(_emit(page, match.group("name"), match.start("name"), match.group("role")))
    return found
