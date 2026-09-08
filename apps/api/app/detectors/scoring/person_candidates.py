"""Untitled narrative person candidates. Lexicon is evidence, not a detector."""

from __future__ import annotations

import re
from typing import Any

from app.detectors.legal.common import make_candidate
from app.detectors.legal.names import (
    PERSON_NAME_RE,
    collapse_name,
    is_non_person_surface,
    strip_possessive,
    take_person_name,
)
from app.domain.models import EntityCandidate, EntityType

from app.detectors.scoring.context import DocumentIndex, person_surface_key
from app.detectors.scoring.evaluate import attach_score, evaluate_candidate
from app.detectors.scoring.exclusions import (
    is_company_phrase,
    is_court_phrase,
    is_institution_phrase,
    is_legal_field_phrase,
    is_legal_role_word,
    is_month_name,
)
from app.detectors.scoring.first_names import is_ambiguous_first_name
from app.detectors.scoring.models import ScoringDecision
from app.detectors.scoring.policy import NARRATIVE_PERSON_DETECTOR

_TITLE_LEFT = re.compile(
    r"(?i)(?:av\.?|avukat|hâkim|hakim|savcı|savci|başkan|baskan|"
    r"kâtip|katip|bilirkişi|bilirkisi)\s*$"
)


def _looks_like_initials(value: str) -> bool:
    tokens = collapse_name(value).split()
    if any(re.fullmatch(r"[A-ZÇĞİÖŞÜ]\.?", token) for token in tokens):
        return True
    return False


def generate_narrative_persons(
    pages: list[Any],
    existing: list[EntityCandidate],
    index: DocumentIndex,
) -> list[EntityCandidate]:
    """Propose 2–4 token proper-name spans that existing detectors missed.

    Single lexicon tokens (Deniz) are never emitted. Initials and partial
    surfaces (M. Yılmaz, Mehmet) are not merged into a known full name.
    """
    found: list[EntityCandidate] = []
    for page in pages:
        for match in PERSON_NAME_RE.finditer(page.text):
            taken = take_person_name(match.group(1))
            if taken is None:
                continue
            name, lead, trail = taken
            local_start = match.start(1) + lead
            local_end = match.end(1) - trail
            abs_start = page.document_offset + local_start
            abs_end = page.document_offset + local_end
            if index.overlaps_any(abs_start, abs_end, index.person_spans):
                continue
            if index.overlaps_any(abs_start, abs_end, index.org_spans):
                continue
            if index.overlaps_any(abs_start, abs_end, index.address_spans):
                continue
            if is_non_person_surface(name) or is_court_phrase(name) or is_institution_phrase(name):
                continue
            if is_legal_role_word(name):
                continue
            if is_company_phrase(name) or is_month_name(name) or is_legal_field_phrase(name):
                continue
            tokens = collapse_name(strip_possessive(name)).split()
            if not 2 <= len(tokens) <= 4:
                continue
            if match.group(1).count(" ") >= 6:
                continue
            if person_surface_key(name) in index.local_person_keys:
                continue
            if _looks_like_initials(name):
                continue
            if all(is_ambiguous_first_name(token) for token in tokens):
                continue
            left = page.text[max(0, local_start - 24) : local_start]
            if _TITLE_LEFT.search(left):
                continue
            candidate = make_candidate(
                page,
                text=name,
                local_start=local_start,
                local_end=local_end,
                entity_type=EntityType.PERSON_NAME,
                detector=NARRATIVE_PERSON_DETECTOR,
                reason="Untitled narrative proper-name candidate (evidence scored).",
                validated=False,
                attributes={
                    "source": "narrative_scoring",
                    "normalized_text_group": person_surface_key(name),
                    "identity_resolved": False,
                },
            )
            scored = evaluate_candidate(candidate, index)
            if scored.decision == ScoringDecision.IGNORE:
                continue
            found.append(attach_score(scored.entity, scored))
            index.person_spans.append((abs_start, abs_end))
    return found
