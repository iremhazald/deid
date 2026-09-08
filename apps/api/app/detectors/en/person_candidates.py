"""High-confidence English legal-context person surfaces. Not a capitalization sweep."""

from __future__ import annotations

import re

from app.detectors.en.common import (
    EN_FULL_NAME,
    EN_NAME_TOKEN,
    EN_TITLED_NAME_BODY,
    alt_pattern,
    in_trading_as_context,
    is_company_surface,
    is_court_surface,
    is_institution_surface,
    is_known_en_first_name,
    looks_like_legal_heading,
    looks_like_person_name,
    looks_like_titled_name_body,
    make_candidate,
    seed,
    strip_en_possessive,
)
from app.detectors.en.vocab import (
    EN_DISCOURSE_OPENERS,
    LEGAL_NARRATIVE_CUES,
    NARRATIVE_PRE_NAME_CUES,
    PERSON_TITLES,
    SIGNATURE_LABELS,
    THE_ROLE_CUES,
)
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_TITLE_BODY = alt_pattern(PERSON_TITLES)
_TITLED = re.compile(
    rf"(?<![A-Za-z])(?P<title>(?i:{_TITLE_BODY}))\.?\s+"
    rf"(?P<name>{EN_TITLED_NAME_BODY})(?![A-Za-z])"
)
_SIG_BODY = alt_pattern(SIGNATURE_LABELS)
_SIGNED = re.compile(
    rf"(?<![A-Za-z])(?P<label>(?i:{_SIG_BODY}))\s*[:\-–]?\s*(?P<name>{EN_FULL_NAME})"
)
_THE_ROLE = alt_pattern(THE_ROLE_CUES)
_CUE_BODY = alt_pattern(LEGAL_NARRATIVE_CUES)
_PRE_NAME_CUE = alt_pattern(NARRATIVE_PRE_NAME_CUES)
_NARRATIVE = re.compile(
    rf"(?<![A-Za-z])(?i:{_THE_ROLE})\s+(?P<name>{EN_FULL_NAME})"
    rf"(?:\s+(?i:{_CUE_BODY}))?"
)
_CUE_THEN_NAME = re.compile(
    rf"(?i:{_PRE_NAME_CUE})\s+(?P<name>{EN_FULL_NAME})"
)
_NAME_THEN_CUE = re.compile(
    rf"(?<![A-Za-z])(?P<name>{EN_FULL_NAME})\s+(?i:{_CUE_BODY})"
)
# "named individuals, namely A and B" — not bare "namely", which introduces
# products, definitions, and legal issues in the same judgments.
_NAMED_PERSON_LIST_INTRO = re.compile(
    r"(?i)\bnamed\s+"
    r"(?:individuals?|persons?|comparators?|employees?|witnesses?|colleagues?|people)"
    r"\s*,?\s*namely\s+"
)
_LIST_NAME = re.compile(rf"(?P<name>{EN_FULL_NAME})(?![A-Za-z])")
_LIST_SEPARATOR = re.compile(r"\s*,\s*|\s+(?:and|or)\s+")
_APPEARED_NON_PERSON = re.compile(r"(?i)^\s+appeared\s+(?:to|that)\b")
_DETERMINER_BEFORE_LABEL = re.compile(r"(?i)\b(?:the|a|an|that|this)\s+$")
_NAME_FIELD_PUNCT = re.compile(r"^\s*[:\-–]\s*$")
_DECISION_TITLE = re.compile(
    rf"(?<![A-Za-z])(?P<role>(?i:employment\s+judge|judge|justice|magistrate|arbitrator))"
    rf"\.?\s+(?P<name>{EN_TITLED_NAME_BODY})(?![A-Za-z])"
)
_MINISTRY_JUSTICE = re.compile(r"(?i)\b(?:ministry|department|administration)\s+of\s+$")
_POSTFIX_COUNSEL = re.compile(
    r"^\s*,\s*(?i:counsel|solicitor|barrister|attorney|lawyer)\b"
)


def _person(
    page: PageText,
    name_raw: str,
    start: int,
    detector: str,
    reason: str,
    extra: list[dict],
    role: str | None = None,
    *,
    titled: bool = False,
) -> EntityCandidate | None:
    name = strip_en_possessive(name_raw)
    if titled:
        if not looks_like_titled_name_body(name):
            return None
    elif not looks_like_person_name(name):
        return None
    if is_court_surface(name) or is_institution_surface(name) or is_company_surface(name):
        return None
    if looks_like_legal_heading(name) or in_trading_as_context(page.text, start):
        return None
    tokens = name.split()
    if tokens and is_known_en_first_name(tokens[0]):
        extra = list(extra) + seed(("en_first_name_lexicon", 2), source="lexicon")
    return make_candidate(
        page,
        text=name,
        local_start=start,
        local_end=start + len(name),
        entity_type=EntityType.PERSON_NAME,
        detector=detector,
        role=role,
        reason=reason,
        attributes={
            "source": "en_person",
            "identity_resolved": False,
            "evidence": extra,
        },
    )


def _postfix_evidence(page: PageText, name_end: int, extra: list[dict]) -> list[dict]:
    after = page.text[name_end : name_end + 36]
    if _POSTFIX_COUNSEL.match(after):
        return list(extra) + seed(("en_counsel_context", 4))
    return extra


def parse_titled_persons(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    for match in _TITLED.finditer(page.text):
        title = match.group("title")
        extra = _postfix_evidence(
            page, match.end("name"), seed(("en_title_context", 5))
        )
        item = _person(
            page,
            match.group("name"),
            match.start("name"),
            "EN_TITLED_PERSON",
            "English courtesy or professional title before a name.",
            extra,
            titled=True,
        )
        if item:
            found.append(item)
        if title.lower() == "dr":
            # Title stays outside the person span.
            pass
    for match in _DECISION_TITLE.finditer(page.text):
        if _MINISTRY_JUSTICE.search(page.text[max(0, match.start() - 32) : match.start()]):
            continue
        name = strip_en_possessive(match.group("name"))
        if looks_like_legal_heading(name) or in_trading_as_context(page.text, match.start("name")):
            continue
        if not looks_like_titled_name_body(name) and not (
            looks_like_person_name(name) or re.fullmatch(EN_NAME_TOKEN, name)
        ):
            continue
        extra = seed(("en_title_context", 5), ("en_legal_role_label", 3))
        extra = _postfix_evidence(page, match.end("name"), extra)
        role_key = re.sub(r"\s+", " ", match.group("role").strip().lower())
        role = "ARBITRATOR" if role_key == "arbitrator" else "JUDGE"
        entity_type = (
            EntityType.PERSON_NAME if role == "ARBITRATOR" else EntityType.JUDGE_NAME
        )
        item = make_candidate(
            page,
            text=name,
            local_start=match.start("name"),
            local_end=match.start("name") + len(name),
            entity_type=entity_type,
            detector="EN_TITLED_PERSON",
            role=role,
            reason="Legal decision-maker title before a name.",
            attributes={
                "source": "en_person",
                "identity_resolved": False,
                "evidence": extra,
            },
        )
        found.append(item)
    return found


def _generic_name_is_signature_field(page: PageText, match: re.Match[str]) -> bool:
    """Bare 'name' is a form field only with punctuation and no determiner."""
    left = page.text[max(0, match.start("label") - 12) : match.start("label")]
    if _DETERMINER_BEFORE_LABEL.search(left):
        return False
    between = page.text[match.end("label") : match.start("name")]
    return _NAME_FIELD_PUNCT.fullmatch(between) is not None


def parse_signature_persons(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    for match in _SIGNED.finditer(page.text):
        if fold_label_is_generic_name(match.group("label")):
            if not _generic_name_is_signature_field(page, match):
                continue
            if not looks_like_person_name(match.group("name")):
                continue
        extra = seed(("en_signature_context", 5))
        item = _person(
            page,
            match.group("name"),
            match.start("name"),
            "EN_SIGNATURE_PERSON",
            "Name in an English signature block.",
            extra,
        )
        if item:
            found.append(item)
    return found


def fold_label_is_generic_name(label: str) -> bool:
    return label.strip().casefold() == "name"


def _starts_with_discourse_opener(name: str) -> bool:
    token = name.split()[0].casefold() if name.split() else ""
    return token in EN_DISCOURSE_OPENERS


def _narrative_span_blocked(page: PageText, match: re.Match[str]) -> bool:
    name = match.group("name")
    if _starts_with_discourse_opener(name):
        return True
    after = page.text[match.end("name") : match.end("name") + 24]
    return _APPEARED_NON_PERSON.match(after) is not None


def _parse_named_person_lists(page: PageText) -> list[EntityCandidate]:
    """Coordinated names after a named-person introducer. One cue, each conjunct."""
    found: list[EntityCandidate] = []
    extra = seed(("en_legal_narrative_context", 3))
    for intro in _NAMED_PERSON_LIST_INTRO.finditer(page.text):
        pos = intro.end()
        while True:
            match = _LIST_NAME.match(page.text, pos)
            if match is None:
                break
            if not _starts_with_discourse_opener(match.group("name")):
                item = _person(
                    page,
                    match.group("name"),
                    match.start("name"),
                    "EN_NARRATIVE_PERSON",
                    "Name in a named-individual list after namely.",
                    extra,
                )
                if item is not None:
                    found.append(item)
            pos = match.end()
            sep = _LIST_SEPARATOR.match(page.text, pos)
            if sep is None:
                break
            pos = sep.end()
    return found


def parse_narrative_persons(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()
    for item in _parse_named_person_lists(page):
        key = (item.start, item.end)
        if key in seen:
            continue
        seen.add(key)
        found.append(item)
    for pattern in (_NARRATIVE, _CUE_THEN_NAME, _NAME_THEN_CUE):
        for match in pattern.finditer(page.text):
            if _narrative_span_blocked(page, match):
                continue
            extra = seed(("en_legal_narrative_context", 3))
            item = _person(
                page,
                match.group("name"),
                match.start("name"),
                "EN_NARRATIVE_PERSON",
                "Bounded English legal-narrative person cue.",
                extra,
            )
            if item is None or (item.start, item.end) in seen:
                continue
            seen.add((item.start, item.end))
            found.append(item)
    return found
