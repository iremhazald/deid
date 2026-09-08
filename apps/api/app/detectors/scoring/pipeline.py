"""Deterministic evidence scoring entry point. No AI, embeddings, or network."""

from __future__ import annotations

import logging
from typing import Any

from app.domain.models import EntityCandidate

from app.detectors.scoring.address_candidates import generate_composite_addresses
from app.detectors.scoring.context import DocumentIndex
from app.detectors.scoring.debug import format_scored, scoring_debug_enabled
from app.detectors.scoring.evaluate import attach_score, evaluate_candidate
from app.detectors.scoring.legal_ref_candidates import generate_labeled_legal_refs
from app.detectors.scoring.models import ScoringDecision
from app.detectors.scoring.person_candidates import generate_narrative_persons
from app.detectors.scoring.resolve import resolve_scored

logger = logging.getLogger(__name__)


def apply_scoring(pages: list[Any], candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    """Evaluate detector outputs, add composite candidates, then resolve conflicts.

    The second evaluate_candidate pass is the single authoritative evidence set.
    Seeded generator evidence is merged by code and not double-counted.
    """
    if not candidates and not pages:
        return []
    index = DocumentIndex.build(pages, candidates)
    scored = [evaluate_candidate(item, index) for item in candidates]
    kept = [item for item in scored if item.decision != ScoringDecision.IGNORE]
    attached = [attach_score(item.entity, item) for item in kept]
    extra_people = generate_narrative_persons(pages, attached, index)
    extra_addresses = generate_composite_addresses(pages, attached, index)
    extra_refs = generate_labeled_legal_refs(pages, attached, index)
    combined = attached + extra_people + extra_addresses + extra_refs
    rescored = [evaluate_candidate(item, index) for item in combined]
    resolved = resolve_scored(rescored)
    if scoring_debug_enabled():
        for item in resolved:
            logger.debug("scoring\n%s", format_scored(item, redact=True))
    return [attach_score(item.entity, item) for item in resolved if item.decision != ScoringDecision.IGNORE]
