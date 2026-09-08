"""English structural LABEL:VALUE / stacked party / caption / matter headings."""

from __future__ import annotations

import re

from app.detectors.en.common import (
    EN_FULL_NAME,
    fold_en,
    is_company_surface,
    looks_like_person_name,
    make_candidate,
    seed,
    strip_en_possessive,
    titled_name_has_initials,
)
from app.detectors.en.vocab import PARTY_ROLES, PERSON_TITLES
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_PARTY = sorted((item[0] for item in PARTY_ROLES), key=len, reverse=True)
_PARTY_BODY = "|".join(re.escape(item) for item in _PARTY)
_STACKED = re.compile(
    rf"(?m)^(?P<label>(?i:{_PARTY_BODY}))\s*$[\r\n]+\s*(?P<value>{EN_FULL_NAME}|[A-Z][A-Za-z0-9'’&. \-]{{2,80}})$"
)
_DASHED = re.compile(
    rf"(?<![A-Za-z])(?P<label>(?i:{_PARTY_BODY}))\s+[-–]\s+(?P<value>{EN_FULL_NAME}|[A-Z][A-Za-z0-9'’&. \-]{{2,80}})"
)
_BETWEEN = re.compile(
    r"(?is)(?P<head>\bBETWEEN\s*:?\s*)(?P<body>.{10,800}?)(?:\n\s*\n|\Z)"
)
_ROLE_LINE = re.compile(
    rf"(?m)^(?P<name>{EN_FULL_NAME}|[A-Z][A-Za-z0-9'’&. \-]{{2,80}})\s*$[\r\n]+\s*"
    rf"(?P<role>(?i:{_PARTY_BODY}))\s*$"
)
# Title-case tokens only. The old [A-Za-z …]{2,60} class swallowed lowercase prose
# after a short case name ("Astley we have to identify…").
_VS_TOKEN = r"(?:[A-Z][A-Za-z0-9'’&.-]+|Ltd\.?|LLC|LLP|PLC)"
_VS_GLUE = r"(?:[Dd]e|[Vv]an|[Vv]on|[Dd]a|[Dd]i|and|&)"
_VS_PARTY = rf"{_VS_TOKEN}(?:[ \t]+(?:{_VS_GLUE}[ \t]+)?{_VS_TOKEN}){{0,6}}"
_VERSUS = re.compile(
    rf"(?<![A-Za-z])(?P<left>{_VS_PARTY})\s+"
    rf"(?P<vs>(?i:v\.?|vs\.?))\s+"
    rf"(?P<right>{_VS_PARTY})(?![A-Za-z])"
)
_LEGAL_CTX = re.compile(
    r"(?i)\b(?:between|claimant|defendant|plaintiff|applicant|respondent|"
    r"in the matter of|in the\s+\w+\s+court|before the)\b"
)
_MATTER = re.compile(r"(?i)\bin\s+the\s+matter\s+of\b")
# "In X v Y" / "Applying X v Y" introduce a cited case, not the live caption.
_CITATION_OPENER = re.compile(
    r"(?i)^(?:(?:the\s+)?"
    r"(?:house\s+of\s+lords|court\s+of\s+appeal|european\s+court|"
    r"employment\s+appeal\s+tribunal|judgment)\s+)?"
    r"(?:in|applying|following|see|per|cf|citing)\s+"
)
_REPORT_OR_YEAR = re.compile(
    r"(?i)(?:\[\s*[12]\d{3}\s*\]|\b(?:UKEAT|UKSC|EWCA|EWHC|ICR|IRLR|WLR)\b)"
)
# Whole-token org heads. Not a name blacklist: "Trust" as a surname still needs
# a title/initials path elsewhere.
_ORG_HEADS = frozenset(
    {
        "authority",
        "council",
        "association",
        "department",
        "agency",
        "commission",
        "university",
        "board",
        "company",
    }
)


def _has_org_head(value: str) -> bool:
    tokens = [fold_en(token.rstrip(".,;:")) for token in value.split() if token]
    return any(token in _ORG_HEADS for token in tokens)


def _versus_is_citation(page_text: str, match: re.Match[str]) -> bool:
    """True when X v Y is a cited authority, not a live caption pairing."""
    if _CITATION_OPENER.match(match.group("left")):
        return True
    before = page_text[max(0, match.start() - 32) : match.start()]
    if _CITATION_OPENER.search(before + match.group("left")[:16]):
        return True
    if re.search(r"(?i)\b(?:in|applying|following|see|per|citing)\s+$", before):
        return True
    window = f"{match.group(0)} {page_text[match.end() : match.end() + 36]}"
    return bool(_REPORT_OR_YEAR.search(window))


def _party_item(
    page: PageText,
    value: str,
    start: int,
    role_raw: str,
    *,
    from_versus: bool = False,
) -> EntityCandidate | None:
    text = strip_en_possessive(value.strip())
    if is_company_surface(text) or _has_org_head(text):
        return make_candidate(
            page,
            text=text,
            local_start=start,
            local_end=start + len(text),
            entity_type=EntityType.COMPANY_NAME if is_company_surface(text) else EntityType.ORGANISATION,
            detector="EN_LEGAL_PARTY",
            role=role_raw.upper(),
            reason="Organisation heading an English party block.",
            attributes={
                "legal_role": role_raw,
                "source": "en_party_block",
                "identity_resolved": False,
                "evidence": seed(("en_party_label", 5), ("en_company_suffix", 4)),
            },
        )
    tokens = text.split()
    titled = bool(tokens) and fold_en(tokens[0].rstrip(".")) in PERSON_TITLES
    # Untitled 3+ token versus sides are case names / trading styles, not a person.
    if (
        from_versus
        and looks_like_person_name(text)
        and len(tokens) >= 3
        and not titled
        and not titled_name_has_initials(text)
    ):
        return make_candidate(
            page,
            text=text,
            local_start=start,
            local_end=start + len(text),
            entity_type=EntityType.ORGANISATION,
            detector="EN_LEGAL_PARTY",
            role=role_raw.upper(),
            reason="Organisation heading an English party block.",
            attributes={
                "legal_role": role_raw,
                "source": "en_party_block",
                "identity_resolved": False,
                "evidence": seed(("en_party_label", 5), ("en_company_suffix", 4)),
            },
        )
    individual = titled or titled_name_has_initials(text) or looks_like_person_name(text)
    if individual and not _CITATION_OPENER.match(text):
        return make_candidate(
            page,
            text=text,
            local_start=start,
            local_end=start + len(text),
            entity_type=EntityType.PERSON_NAME,
            detector="EN_LEGAL_PARTY",
            role=role_raw.upper(),
            reason="Person heading an English party block.",
            attributes={
                "legal_role": role_raw,
                "source": "en_party_block",
                "identity_resolved": False,
                "evidence": seed(("en_party_label", 5), ("en_legal_role_label", 3)),
            },
        )
    return None


def parse_structural(page: PageText) -> list[EntityCandidate]:
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

    for match in _DASHED.finditer(page.text):
        take(_party_item(page, match.group("value"), match.start("value"), match.group("label")))
    for match in _STACKED.finditer(page.text):
        take(_party_item(page, match.group("value"), match.start("value"), match.group("label")))
    for match in _ROLE_LINE.finditer(page.text):
        take(_party_item(page, match.group("name"), match.start("name"), match.group("role")))
    if _LEGAL_CTX.search(page.text):
        for match in _VERSUS.finditer(page.text):
            if _versus_is_citation(page.text, match):
                continue
            take(
                _party_item(
                    page, match.group("left"), match.start("left"), "claimant", from_versus=True
                )
            )
            right = match.group("right").strip()
            if is_company_surface(right) or _has_org_head(right) or looks_like_person_name(right):
                take(
                    _party_item(
                        page, right, match.start("right"), "defendant", from_versus=True
                    )
                )
    return found


def has_matter_heading(text: str) -> bool:
    return bool(_MATTER.search(text))
