"""Explicit candidate resolution. Highest score does not automatically win."""

from __future__ import annotations

import re

from app.detectors.legal.merge import detector_rank
from app.domain.models import EntityType

from app.detectors.scoring.models import HardValidation, ScoredCandidate, ScoringDecision

_PERSON = {
    EntityType.PERSON_NAME,
    EntityType.FIRST_NAME,
    EntityType.LAST_NAME,
    EntityType.ALIAS,
    EntityType.JUDGE_NAME,
    EntityType.LAWYER_NAME,
    EntityType.CLAIMANT_NAME,
    EntityType.DEFENDANT_NAME,
    EntityType.WITNESS_NAME,
    EntityType.EXPERT_NAME,
}

_ORG = {EntityType.ORGANISATION, EntityType.COMPANY_NAME, EntityType.COURT_NAME}
_LEGAL_REF = {
    EntityType.CASE_NUMBER,
    EntityType.FILE_NUMBER,
    EntityType.DECISION_NUMBER,
}
_DOCKET_LINE = re.compile(r"(?i)\b(?:esas|karar|dosya|soruşturma|sorusturma)\s*(?:no)?\b")
_NUMERIC_LOSER = {
    EntityType.PHONE_NUMBER,
    EntityType.CREDIT_CARD,
    EntityType.POSTAL_CODE,
    EntityType.PORT_NUMBER,
    EntityType.OTHER_IDENTIFIER,
}


def _overlaps(left: ScoredCandidate, right: ScoredCandidate) -> bool:
    return left.page == right.page and left.start < right.end and right.start < left.end


def _contains(outer: ScoredCandidate, inner: ScoredCandidate) -> bool:
    return (
        outer.page == inner.page
        and inner.start >= outer.start
        and inner.end <= outer.end
    )


def _specificity(item: ScoredCandidate) -> int:
    return item.end - item.start


def resolve_scored(candidates: list[ScoredCandidate]) -> list[ScoredCandidate]:
    """Drop hard-invalid / ignore, then apply parent and type-conflict rules."""
    working = [item for item in candidates if item.decision != ScoringDecision.IGNORE]
    kept: list[ScoredCandidate] = []
    for item in sorted(
        working,
        key=lambda candidate: (
            candidate.hard_validation != HardValidation.INVALID,
            detector_rank(candidate.detector),
            _specificity(candidate),
            candidate.evidence_score,
        ),
        reverse=True,
    ):
        drop = False
        reason = None
        for other in kept:
            if not _overlaps(item, other):
                continue
            if (
                item.detector.startswith("GLOBAL_")
                and other.detector.startswith("STRUCTURAL")
                and item.type == other.type
            ):
                kept = [kept_item for kept_item in kept if kept_item.entity.id != other.entity.id]
                continue
            if other.type == EntityType.UYAP_ACCESS and item.type in {
                EntityType.URL,
                EntityType.SYSTEM_URL,
            }:
                drop = True
                reason = "uyap_parent_precedes_url"
                break
            if other.type == EntityType.IBAN and item.type in _NUMERIC_LOSER | {
                EntityType.NATIONAL_ID,
            }:
                if _contains(other, item):
                    drop = True
                    reason = "inside_iban"
                    break
            if other.type == EntityType.NATIONAL_ID and item.type in _NUMERIC_LOSER:
                if _contains(other, item):
                    drop = True
                    reason = "inside_tckn"
                    break
            if other.type in _ORG and item.type in _PERSON:
                drop = True
                reason = "institution_suppresses_person"
                break
            if other.type in _PERSON and item.type == EntityType.LOCATION:
                drop = True
                reason = "identity_not_location"
                break
            if other.type == EntityType.COURT_NAME and item.type in _LEGAL_REF:
                if _DOCKET_LINE.search(other.entity.text) and other.entity.attributes.get("mask_scope") != "header_line":
                    continue
                if _contains(other, item) and other.entity.attributes.get("mask_scope") == "header_line":
                    drop = True
                    reason = "court_header_parent"
                    break
            if other.type in _ORG and item.type == EntityType.ADDRESS:
                overlap = min(other.end, item.end) - max(other.start, item.start)
                if overlap >= 0.7 * _specificity(item):
                    drop = True
                    reason = "institution_not_address"
                    break
            if other.type == EntityType.ADDRESS and item.type == EntityType.VEHICLE_PLATE:
                if _contains(other, item):
                    drop = True
                    reason = "plate_inside_address"
                    break
            if other.type == EntityType.ADDRESS and item.type == EntityType.POSTAL_CODE:
                item.parent_candidate_id = other.entity.id
                continue
            if other.type == EntityType.IP_ADDRESS and item.type in {
                EntityType.PHONE_NUMBER,
                EntityType.POSTAL_CODE,
                EntityType.FILE_NUMBER,
                EntityType.PORT_NUMBER,
            }:
                if _overlaps(other, item):
                    drop = True
                    reason = "ip_port_not_other_numeric"
                    break
            if (
                other.hard_validation == HardValidation.VALID
                and item.hard_validation != HardValidation.VALID
                and other.type in {EntityType.NATIONAL_ID, EntityType.IBAN, EntityType.CREDIT_CARD}
                and item.type in _NUMERIC_LOSER | {EntityType.NATIONAL_ID, EntityType.CREDIT_CARD}
            ):
                drop = True
                reason = "hard_validator_specificity"
                break
        if drop:
            item.decision = ScoringDecision.IGNORE
            item.conflict_reason = reason
            continue
        if item.type == EntityType.COURT_NAME and _DOCKET_LINE.search(item.entity.text):
            if not re.search(r"(?i)(?:mahkeme|dairesi|yargıtay|danıştay|hakimli)", item.entity.text):
                item.decision = ScoringDecision.IGNORE
                item.conflict_reason = "docket_label_not_court"
                continue
        if item.type in _ORG:
            survivors: list[ScoredCandidate] = []
            for other in kept:
                if other.type in _PERSON and _overlaps(item, other):
                    other.decision = ScoringDecision.IGNORE
                    other.conflict_reason = "institution_suppresses_person"
                    continue
                if other.type == EntityType.ADDRESS and _overlaps(item, other):
                    overlap = min(other.end, item.end) - max(other.start, item.start)
                    if overlap >= 0.7 * _specificity(other):
                        other.decision = ScoringDecision.IGNORE
                        other.conflict_reason = "institution_not_address"
                        continue
                survivors.append(other)
            kept = survivors
        if item.type in _PERSON:
            survivors = []
            for other in kept:
                if other.type == EntityType.LOCATION and _overlaps(item, other):
                    other.decision = ScoringDecision.IGNORE
                    other.conflict_reason = "identity_not_location"
                    continue
                survivors.append(other)
            kept = survivors
        kept.append(item)
    return kept
