"""Company / entity suffix evidence for English-General documents."""

from __future__ import annotations

import re

from app.detectors.en.common import alt_pattern, fold_en, make_candidate, seed
from app.detectors.en.vocab import COMPANY_SUFFIXES, INSTITUTION_PHRASES, TRADING_AS_MARKERS
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_SUFFIX = alt_pattern(COMPANY_SUFFIXES)
# Proper-name / ALLCAPS tokens only. Do not IGNORECASE the left-hand name:
# that is what turned "proceedings is limited" into a company.
_ORG_TOKEN = r"(?:[A-Z]{2,}[A-Z0-9.'’-]*|[A-Z][a-z0-9'’.-]+)"
_ORG_LINK = r"(?:&|[Aa]nd|[Oo]f)"
_COMPANY = re.compile(
    rf"(?<![A-Za-z0-9])(?P<span>(?P<name>{_ORG_TOKEN}"
    rf"(?:[ \t]+(?:{_ORG_LINK}[ \t]+)?{_ORG_TOKEN}){{0,5}})"
    rf"[ \t]+(?P<suffix>(?i:{_SUFFIX})))\.?(?![A-Za-z])"
)
_INSTITUTION = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<span>{alt_pattern(INSTITUTION_PHRASES)})(?![A-Za-z])"
)
_TRADE = re.compile(
    rf"(?i)(?<![A-Za-z])(?:{alt_pattern(TRADING_AS_MARKERS)})[ \t]+"
    rf"(?P<span>(?:the[ \t]+)?{_ORG_TOKEN}"
    rf"(?:[ \t]+(?:{_ORG_LINK}[ \t]+)?{_ORG_TOKEN}){{0,5}})"
    rf"(?![A-Za-z])"
)
_PLACE_ONLY = frozenset({"london", "new york", "united kingdom", "united states"})
_COMPANY_STOP = frozenset({"the", "a", "an", "and", "of", "this", "that"})
# Immediate left-of-suffix copula / auxiliary = ordinary prose, not an org name.
_PRE_SUFFIX_PROSE = frozenset(
    {
        "is",
        "was",
        "were",
        "are",
        "be",
        "been",
        "being",
        "has",
        "had",
        "have",
        "remain",
        "remains",
        "remained",
        "seems",
        "seemed",
        "appears",
        "appeared",
        "becomes",
        "became",
        "only",
        "very",
        "so",
        "too",
        "not",
    }
)


def _plausible_company_name(name: str) -> bool:
    tokens = [token for token in re.split(r"[\s]+", name.strip()) if token and token != "&"]
    if not tokens:
        return False
    content = [token for token in tokens if fold_en(token) not in _COMPANY_STOP]
    if not content:
        return False
    if fold_en(tokens[-1]) in _PRE_SUFFIX_PROSE:
        return False
    return True


def parse_organisations(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()

    def take(item: EntityCandidate) -> None:
        key = (item.start, item.end)
        if key in seen:
            return
        seen.add(key)
        found.append(item)

    for match in _COMPANY.finditer(page.text):
        name = match.group("name")
        if not _plausible_company_name(name):
            continue
        span = match.group("span")
        take(
            make_candidate(
                page,
                text=span,
                local_start=match.start("span"),
                local_end=match.end("span"),
                entity_type=EntityType.COMPANY_NAME,
                detector="EN_COMPANY_SUFFIX",
                reason="English company / partnership suffix.",
                validated=False,
                attributes={
                    "org_kind": "COMPANY",
                    "source": "en_company",
                    "evidence": seed(("en_company_suffix", 6)),
                },
            )
        )
    for match in _TRADE.finditer(page.text):
        span = match.group("span").strip().rstrip(".,;:")
        if not _plausible_company_name(re.sub(r"(?i)^the\s+", "", span)):
            continue
        take(
            make_candidate(
                page,
                text=span,
                local_start=match.start("span"),
                local_end=match.start("span") + len(span),
                entity_type=EntityType.COMPANY_NAME,
                detector="EN_COMPANY_SUFFIX",
                reason="English trading-as / DBA business name.",
                validated=False,
                attributes={
                    "org_kind": "TRADING_NAME",
                    "source": "en_trading_as",
                    "evidence": seed(("en_trading_as", 6)),
                },
            )
        )
    for match in _INSTITUTION.finditer(page.text):
        span = match.group("span")
        if span.casefold() in _PLACE_ONLY:
            continue
        take(
            make_candidate(
                page,
                text=span,
                local_start=match.start("span"),
                local_end=match.end("span"),
                entity_type=EntityType.ORGANISATION,
                detector="EN_ORGANISATION",
                reason="English public or legal institution phrase.",
                attributes={
                    "org_kind": "INSTITUTION",
                    "source": "en_organisation",
                    "evidence": seed(("en_court_structure", 3)),
                },
            )
        )
    return found
