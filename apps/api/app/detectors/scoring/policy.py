"""Category-specific evidence weights and decision thresholds.

Thresholds are evidence weights, not probabilities. They are calibrated so
existing high-confidence detector emissions stay ACCEPT unless hard-invalid.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import EntityType

from app.detectors.scoring.models import CandidateClass


@dataclass(frozen=True)
class CategoryPolicy:
    candidate_class: CandidateClass
    accept_threshold: int
    review_threshold: int
    # Same-line first, then this many characters around the span.
    context_chars: int
    adjacent_line: bool = True


# Structured-source floor for PERSON (minimum score, not an extra +10).
# Non-PERSON high-confidence detectors still record this as additive evidence.
# Soft/composite families do not get this.
EXISTING_HIGH_CONFIDENCE_WEIGHT = 10
EXISTING_DETECTOR_WEIGHT = 6

# Titled / checksum / labeled structured sources. Safe to keep ACCEPT-dominant.
HIGH_CONFIDENCE_STRUCTURED_SOURCE = frozenset(
    {
        "TR_TCKN",
        "TR_IBAN",
        "GLOBAL_IBAN",
        "GLOBAL_LUHN_CARD",
        "GLOBAL_EMAIL",
        "GLOBAL_IPV4",
        "GLOBAL_URL",
        "TR_MOBILE_PHONE",
        "TR_UYAP_FOOTER",
        "TR_LEGAL_PARTY",
        "TR_COUNSEL_BLOCK",
        "TR_JUDICIAL_ROSTER",
        "TR_ROLE_PERSON",
        "TR_LEGAL_ROLE_NAME",
        "TR_PARENTAGE",
        "TR_BIRTH_INFO",
        "USER_DEFINED_TERM",
        "TR_COURT_LETTERHEAD",
        "TR_COURT_GRAMMAR",
        "TR_ORG_AUTHORITY",
        "TR_COMPANY_SUFFIX",
        "TR_CASE_NUMBER",
        "TR_DECISION_NUMBER",
        "TR_FILE_NUMBER",
        "TR_ARBITRATION_NUMBER",
        "TR_VKN",
        "TR_ADDRESS_TOKENS",
        "TR_ADDRESS_GRAMMAR",
        "EN_LEGAL_PARTY",
        "EN_ROLE_PERSON",
        "EN_TITLED_PERSON",
        "EN_SIGNATURE_PERSON",
        "EN_CASE_NUMBER",
        "EN_FILE_NUMBER",
        "EN_COURT",
        "EN_COMPANY_SUFFIX",
        "EN_ORGANISATION",
        "EN_ADDRESS",
        "EN_BIRTH",
        "EN_PASSPORT",
        "EN_NATIONAL_ID",
        "EN_POSTAL_CODE",
        "EN_PHONE_CONTEXT",
    }
)

# Soft heuristics: keep as known surfaces for local grouping, but do not grant +10.
SOFT_HEURISTIC_SOURCE = frozenset(
    {
        "TR_STATEMENT",
        "TR_MENTIONED_PERSON",
        "TR_OWNERSHIP",
        "EN_NARRATIVE_PERSON",
        "EN_ACCOUNT",
    }
)

# Backward-compatible alias used by DocumentIndex local-person grouping.
HIGH_CONFIDENCE_DETECTORS = HIGH_CONFIDENCE_STRUCTURED_SOURCE | SOFT_HEURISTIC_SOURCE

NARRATIVE_PERSON_DETECTOR = "TR_NARRATIVE_PERSON"
EVIDENCE_ADDRESS_DETECTOR = "TR_EVIDENCE_ADDRESS"
LOCAL_NER_TR = "LOCAL_NER_TR"
LOCAL_NER_EN = "LOCAL_NER_EN"
LOCAL_NER_SOURCES = frozenset({LOCAL_NER_TR, LOCAL_NER_EN})
_LOCATION_NER = CategoryPolicy(CandidateClass.COMPOSITE, accept_threshold=8, review_threshold=5, context_chars=40)

_STRICT = CategoryPolicy(CandidateClass.STRICT, accept_threshold=8, review_threshold=8, context_chars=40)
_EMAIL = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=6, review_threshold=6, context_chars=24, adjacent_line=False)
_PHONE_MOBILE = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=5, review_threshold=5, context_chars=40)
_PHONE_FIXED = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=8, review_threshold=6, context_chars=40)
_PLATE = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=7, review_threshold=5, context_chars=40)
_LEGAL_REF = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=8, review_threshold=6, context_chars=32)
_BIRTH = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=8, review_threshold=8, context_chars=36, adjacent_line=False)
_POSTAL = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=8, review_threshold=8, context_chars=24)
_VKN = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=8, review_threshold=8, context_chars=40)
_COURT = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=8, review_threshold=6, context_chars=40)
_UYAP = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=8, review_threshold=8, context_chars=80)
_PERSON = CategoryPolicy(CandidateClass.COMPOSITE, accept_threshold=9, review_threshold=7, context_chars=60)
_ADDRESS = CategoryPolicy(CandidateClass.COMPOSITE, accept_threshold=10, review_threshold=7, context_chars=80)
_ORG = CategoryPolicy(CandidateClass.COMPOSITE, accept_threshold=8, review_threshold=6, context_chars=40)
_DEFAULT = CategoryPolicy(CandidateClass.STRUCTURED, accept_threshold=6, review_threshold=4, context_chars=40)

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

_ORG_TYPES = {
    EntityType.ORGANISATION,
    EntityType.COMPANY_NAME,
    EntityType.COURT_NAME,
}


def policy_for(entity_type: EntityType, detector: str = "") -> CategoryPolicy:
    if detector in LOCAL_NER_SOURCES and entity_type == EntityType.LOCATION:
        return _LOCATION_NER
    if entity_type in {EntityType.NATIONAL_ID, EntityType.IBAN, EntityType.CREDIT_CARD}:
        return _STRICT
    if entity_type == EntityType.EMAIL:
        return _EMAIL
    if entity_type == EntityType.PHONE_NUMBER:
        if "LANDLINE" in detector or "FIXED" in detector:
            return _PHONE_FIXED
        if "CONTEXT" in detector:
            return _PHONE_FIXED
        return _PHONE_MOBILE
    if entity_type == EntityType.VEHICLE_PLATE:
        return _PLATE
    if entity_type in {EntityType.CASE_NUMBER, EntityType.FILE_NUMBER, EntityType.DECISION_NUMBER}:
        return _LEGAL_REF
    if entity_type in {EntityType.DATE_OF_BIRTH, EntityType.BIRTH_PLACE}:
        return _BIRTH
    if entity_type == EntityType.POSTAL_CODE:
        return _POSTAL
    if entity_type == EntityType.TAX_IDENTIFIER:
        return _VKN
    if entity_type == EntityType.COURT_NAME:
        return _COURT
    if entity_type in {EntityType.UYAP_ACCESS, EntityType.SYSTEM_URL}:
        return _UYAP
    if entity_type in {EntityType.ADDRESS, EntityType.LOCATION}:
        return _ADDRESS
    if entity_type in _PERSON_TYPES:
        return _PERSON
    if entity_type in _ORG_TYPES:
        return _ORG
    if entity_type in {EntityType.URL, EntityType.IP_ADDRESS}:
        return _EMAIL
    return _DEFAULT


def candidate_class_for(entity_type: EntityType, detector: str = "") -> CandidateClass:
    return policy_for(entity_type, detector).candidate_class
