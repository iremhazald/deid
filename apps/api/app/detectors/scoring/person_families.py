"""English PERSON evidence-family normalization.

NER and deterministic rules stay independent sources. This layer only
stops English codes that share one parser/detector decision from being
counted as separate observations.

Turkish PERSON scoring is not rewritten here. Shared PERSON high-confidence
floor semantics live in ``evaluate`` so identifiers stay additive.
"""

from __future__ import annotations

from app.domain.models import EntityType

from app.detectors.scoring.models import Evidence, EvidenceSource, ScoredCandidate

# One EN role/title/party parse currently seeds several of these.
EN_ROLE_STRUCTURE_FAMILY = frozenset(
    {
        "en_legal_role_label",
        "en_counsel_context",
        "en_party_label",
        "en_title_context",
        "lawyer_title_or_role",
        "roster_or_judge_role",
        "title_or_party_or_roster",
    }
)

EN_PERSON_DETECTORS = frozenset(
    {
        "EN_LEGAL_PARTY",
        "EN_ROLE_PERSON",
        "EN_TITLED_PERSON",
        "EN_SIGNATURE_PERSON",
        "EN_NARRATIVE_PERSON",
    }
)

_PERSON_TYPES = {
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


def is_en_person_candidate(scored: ScoredCandidate) -> bool:
    return scored.entity.type in _PERSON_TYPES and scored.detector in EN_PERSON_DETECTORS


def cap_en_role_structure_family(evidence: list[Evidence]) -> list[Evidence]:
    """Keep the strongest EN role-structure code; zero the rest of the family.

    Codes remain on the candidate so provenance is visible. Weight 0 means the
    signal was seen but does not add another independent observation.
    """
    members = [item for item in evidence if item.code in EN_ROLE_STRUCTURE_FAMILY]
    if len(members) <= 1:
        return evidence
    keeper = max(members, key=lambda item: (item.weight, item.code))
    normalized: list[Evidence] = []
    for item in evidence:
        if item.code in EN_ROLE_STRUCTURE_FAMILY and item.code != keeper.code:
            if item.weight == 0:
                normalized.append(item)
                continue
            normalized.append(
                Evidence(
                    code=item.code,
                    weight=0,
                    source=item.source or EvidenceSource.DETECTOR,
                    hard_reject=item.hard_reject,
                )
            )
            continue
        normalized.append(item)
    return normalized
