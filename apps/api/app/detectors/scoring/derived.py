"""Provenance for candidates that never enter full evidence scoring.

CATEGORY A — MUST BE SCORED
    Detector and composite candidates whose accept/review/ignore depends on
    evidence. Routed through ``evaluate_candidate``.

CATEGORY B — DERIVED FROM AN ALREADY SCORED SOURCE
    Safe exact-surface repeats and adjacent name pairs. Inherit decision
    metadata from the source span. This is "same normalized text again",
    not person identity or coreference.

CATEGORY C — OUTSIDE SCORING BY DESIGN
    USER_DEFINED_TERM (explicit user dictionary), QR_CODE geometry,
    TR_COURT_LETTERHEAD, and STRUCTURAL_* label-value hits. They do not
    invent an evidence score.
"""

from __future__ import annotations

from app.domain.models import EntityCandidate

from app.detectors.scoring.models import EvidenceSource

DERIVED_EVIDENCE_CODE = "derived_from_exact_surface_match"
SCORING_PROVENANCE_INHERITED = "inherited"
SCORING_PROVENANCE_OUTSIDE = "outside_scoring"


def inherit_scoring_provenance(
    derived: EntityCandidate, source: EntityCandidate
) -> EntityCandidate:
    """Copy decision metadata from an accepted/review source onto a derived span."""
    source_attrs = source.attributes or {}
    decision = str(source_attrs.get("scoring_decision") or "")
    if decision not in {"ACCEPT", "REVIEW"}:
        decision = "REVIEW" if source.needs_review else "ACCEPT"
    attributes = dict(derived.attributes or {})
    attributes["scoring_decision"] = decision
    attributes["scoring_provenance"] = SCORING_PROVENANCE_INHERITED
    attributes["source_candidate_id"] = source.id
    attributes["evidence_score"] = source_attrs.get("evidence_score", 0)
    attributes["hard_validation"] = source_attrs.get("hard_validation", "NOT_APPLICABLE")
    attributes["evidence"] = [
        {
            "code": DERIVED_EVIDENCE_CODE,
            "weight": 0,
            "source": EvidenceSource.DERIVED,
        }
    ]
    attributes["negative_evidence"] = []
    attributes["identity_resolved"] = False
    return derived.model_copy(
        update={
            "attributes": attributes,
            "needs_review": decision == "REVIEW" or source.needs_review,
        }
    )


def mark_outside_scoring(entity: EntityCandidate) -> EntityCandidate:
    """Document that this span is intentionally not evidence-scored."""
    attributes = dict(entity.attributes or {})
    if attributes.get("scoring_provenance"):
        return entity
    attributes["scoring_provenance"] = SCORING_PROVENANCE_OUTSIDE
    return entity.model_copy(update={"attributes": attributes})
