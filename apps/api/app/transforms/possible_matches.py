"""Human-confirmed PERSON possible-match suggestions. Not identity resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha1

from app.detectors.scoring.english_page import is_ordinary_english_page_noun
from app.detectors.textutil import fold_tr_identity
from app.domain.models import (
    EntityCandidate,
    EntityType,
    PossibleMatch,
    PossibleMatchMember,
    ResolutionState,
)
from app.transforms.resolution import split_name_suffix
from app.transforms.tag_taxonomy import PERSON_MATCH_TYPES

_HONORIFIC_TOKENS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "miss",
        "mx",
        "dr",
        "prof",
        "professor",
        "sir",
        "dame",
        "av",
        "avukat",
        "bay",
        "bayan",
        "sn",
        "sayin",
        "sayın",
        "hakim",
        "hâkim",
        "yargic",
        "yargıç",
    }
)
_ROLE_PREFIX_TOKENS = frozenset(
    {
        "davaci",
        "davacı",
        "davacilar",
        "davacılar",
        "davali",
        "davalı",
        "davalilar",
        "davalılar",
        "sanik",
        "sanık",
        "saniklar",
        "sanıklar",
    }
)
_TITLE_TOKENS = _HONORIFIC_TOKENS | _ROLE_PREFIX_TOKENS
_TOKEN = re.compile(
    r"[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+(?:['’`´ʼ′][A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+)?"
)
_COMPANY_TAIL = re.compile(
    r"(?i)\b(?:ltd|limited|llc|llp|inc|incorporated|corp|corporation|plc)\.?\s*$"
)
_COMPANY_TYPES = {EntityType.COMPANY_NAME, EntityType.ORGANISATION}
_TRAILING_PUNCT = ".,;:!?)]}\"'"


def _bare_token(token: str) -> str:
    compact = token.strip().strip(_TRAILING_PUNCT)
    base, suffix = split_name_suffix(compact)
    return (base if suffix else compact).strip(_TRAILING_PUNCT)


def _fold(token: str) -> str:
    return fold_tr_identity(_bare_token(token)).rstrip(".")


def _name_tokens(text: str) -> list[str]:
    surface = " ".join(text.split()).strip(_TRAILING_PUNCT)
    base, suffix = split_name_suffix(surface)
    source = base if suffix else surface
    return [_fold(token) for token in _TOKEN.findall(source) if _fold(token)]


def person_name_parts(text: str) -> tuple[list[str], str | None]:
    """Return (given-name tokens, surname) after stripping courtesy titles."""
    tokens = [token for token in _name_tokens(text) if token not in _TITLE_TOKENS]
    if not tokens:
        return [], None
    if len(tokens) == 1:
        return [], tokens[0]
    return tokens[:-1], tokens[-1]


def _display_text(members: list[EntityCandidate]) -> str:
    first = min(members, key=lambda item: (item.page, item.start, item.id))
    return " ".join(first.text.split())


def _canonical_id(entity: EntityCandidate) -> str:
    return entity.resolved_entity_id or entity.id


def _pair_key(left: str, right: str) -> list[str]:
    return sorted((left, right))


def _rejected(state: ResolutionState | None) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    if state is None:
        return found
    for pair in state.rejected_pairs:
        if len(pair) != 2:
            continue
        ordered = tuple(_pair_key(pair[0], pair[1]))
        found.add(ordered)  # type: ignore[arg-type]
    return found


def _lexical_person_span(entity: EntityCandidate, text: str) -> bool:
    left = text[max(0, entity.start - 48) : entity.start]
    right = text[entity.end : min(len(text), entity.end + 24)]
    return is_ordinary_english_page_noun(left, entity.text, right)


@dataclass(frozen=True)
class _NameProfile:
    canonical: str
    members: tuple[EntityCandidate, ...]
    given: tuple[str, ...]
    surname: str
    types: frozenset[EntityType]

    @property
    def is_partial(self) -> bool:
        return not self.given

    @property
    def first_name_only(self) -> bool:
        return bool(self.types) and self.types <= {EntityType.FIRST_NAME}

    @property
    def last_name_only(self) -> bool:
        return bool(self.types) and self.types <= {EntityType.LAST_NAME}


def _tokens_contain(longer: tuple[str, ...], shorter: tuple[str, ...]) -> bool:
    if len(shorter) < 2 or len(longer) <= len(shorter):
        return False
    width = len(shorter)
    return any(longer[index : index + width] == shorter for index in range(len(longer) - width + 1))


def _pair_kind(left: _NameProfile, right: _NameProfile) -> str | None:
    """Conservative partial-reference match. Never a trusted identity merge."""
    if left.given and right.given:
        if left.surname == right.surname and left.given == right.given:
            return "full"
        left_core = left.given + (left.surname,)
        right_core = right.given + (right.surname,)
        if _tokens_contain(left_core, right_core) or _tokens_contain(right_core, left_core):
            return "full"
        return None
    if left.surname == right.surname:
        if left.first_name_only or right.first_name_only:
            return None
        if bool(left.given) != bool(right.given):
            return "surname"
        return None
    if (
        left.is_partial
        and not left.last_name_only
        and right.given
        and left.surname in right.given
    ):
        return "given"
    if (
        right.is_partial
        and not right.last_name_only
        and left.given
        and right.surname in left.given
    ):
        return "given"
    return None


def _member(profile: _NameProfile) -> PossibleMatchMember:
    members = list(profile.members)
    return PossibleMatchMember(
        canonical_id=profile.canonical,
        entity_ids=[item.id for item in members],
        text=_display_text(members),
        pages=sorted({item.page for item in members}),
        placeholder_token=members[0].placeholder_token,
    )


def generate_possible_matches(
    entities: list[EntityCandidate],
    text: str,
    state: ResolutionState | None = None,
) -> list[PossibleMatch]:
    """Suggest PERSON partial-reference pairs. Never mutates identity."""
    groups: dict[str, list[EntityCandidate]] = {}
    for entity in entities:
        if entity.type not in PERSON_MATCH_TYPES:
            continue
        if entity.type in _COMPANY_TYPES or _COMPANY_TAIL.search(entity.text):
            continue
        if _lexical_person_span(entity, text):
            continue
        groups.setdefault(_canonical_id(entity), []).append(entity)

    profiles: list[_NameProfile] = []
    for canonical, members in groups.items():
        given, surname = person_name_parts(_display_text(members))
        if not surname or len(surname) < 2:
            continue
        profiles.append(
            _NameProfile(
                canonical=canonical,
                members=tuple(members),
                given=tuple(given),
                surname=surname,
                types=frozenset(item.type for item in members),
            )
        )

    rejected = _rejected(state)
    suggestions: list[PossibleMatch] = []
    seen: set[tuple[str, str]] = set()

    def add_pair(left: _NameProfile, right: _NameProfile) -> None:
        keys = _pair_key(left.canonical, right.canonical)
        pair: tuple[str, str] = (keys[0], keys[1])
        if pair in seen or pair in rejected:
            return
        seen.add(pair)
        match_id = sha1("|".join(pair).encode("utf-8")).hexdigest()[:12]
        suggestions.append(
            PossibleMatch(
                id=f"pm_{match_id}",
                members=[_member(left), _member(right)],
            )
        )

    fulls = [item for item in profiles if not item.is_partial]
    partials = [item for item in profiles if item.is_partial]
    for index, left in enumerate(fulls):
        for right in fulls[index + 1 :]:
            if _pair_kind(left, right) == "full":
                add_pair(left, right)
    for partial in partials:
        partners = [item for item in fulls if _pair_kind(partial, item)]
        if len(partners) != 1:
            continue
        add_pair(partial, partners[0])

    suggestions.sort(key=lambda item: (item.members[0].pages[:1], item.members[0].text))
    suggestions.extend(_address_possible_matches(entities, state, seen))
    return suggestions


_ADDRESS_STREET = re.compile(
    r"\b(caddesi|cadde|cad|sokagi|sokağı|sokak|sok|bulvarı|bulvari|blv|mahallesi|mah)\b"
)
_ADDRESS_NO = re.compile(r"\b(numara|no)\b")


def _address_merge_key(text: str) -> str:
    folded = fold_tr_identity(text)
    folded = _ADDRESS_STREET.sub(" ", folded)
    folded = _ADDRESS_NO.sub(" ", folded)
    return re.sub(r"[^a-z0-9]+", "", folded)


def _address_possible_matches(
    entities: list[EntityCandidate],
    state: ResolutionState | None,
    seen: set[tuple[str, str]],
) -> list[PossibleMatch]:
    rejected = _rejected(state)
    groups: dict[str, list[EntityCandidate]] = {}
    for entity in entities:
        if entity.type != EntityType.ADDRESS:
            continue
        groups.setdefault(_canonical_id(entity), []).append(entity)
    keyed: dict[str, list[str]] = {}
    for canonical, members in groups.items():
        key = _address_merge_key(_display_text(members))
        if len(key) < 10:
            continue
        keyed.setdefault(key, []).append(canonical)
    suggestions: list[PossibleMatch] = []
    for canonicals in keyed.values():
        unique = list(dict.fromkeys(canonicals))
        if len(unique) < 2:
            continue
        left_id, right_id = unique[0], unique[1]
        keys = _pair_key(left_id, right_id)
        pair: tuple[str, str] = (keys[0], keys[1])
        if pair in seen or pair in rejected:
            continue
        seen.add(pair)
        match_id = sha1(f"addr|{pair[0]}|{pair[1]}".encode("utf-8")).hexdigest()[:12]
        suggestions.append(
            PossibleMatch(
                id=f"pm_{match_id}",
                kind="address",
                members=[
                    PossibleMatchMember(
                        canonical_id=left_id,
                        entity_ids=[item.id for item in groups[left_id]],
                        text=_display_text(groups[left_id]),
                        pages=sorted({item.page for item in groups[left_id]}),
                        placeholder_token=groups[left_id][0].placeholder_token,
                    ),
                    PossibleMatchMember(
                        canonical_id=right_id,
                        entity_ids=[item.id for item in groups[right_id]],
                        text=_display_text(groups[right_id]),
                        pages=sorted({item.page for item in groups[right_id]}),
                        placeholder_token=groups[right_id][0].placeholder_token,
                    ),
                ],
            )
        )
    return suggestions
