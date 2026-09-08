"""Assign deterministic verification metadata without inventing scores."""

from __future__ import annotations

from app.domain.models import EntityCandidate, VerificationLevel

# Detector → method used when the finding already passed a structural check.
_VALIDATED_METHODS: dict[str, str] = {
    "TR_TCKN": "tckn_checksum",
    "TR_IBAN": "iban_mod97",
    "GLOBAL_IBAN": "iban_mod97",
    "GLOBAL_LUHN_CARD": "luhn",
    "GLOBAL_EMAIL": "regex_format",
    "GLOBAL_IPV4": "regex_format",
    "TR_MOBILE_PHONE": "phone_area_code",
    "TR_LANDLINE_PHONE": "phone_area_code",
    "TR_VKN": "vkn_checksum",
    "USER_DEFINED_TERM": "user_defined",
    "TR_NARRATIVE_PERSON": "evidence_weight",
    "TR_EVIDENCE_ADDRESS": "evidence_weight",
}

_METHOD_BY_DETECTOR_PREFIX: tuple[tuple[str, str], ...] = (
    ("TR_ADDRESS", "address_grammar"),
    ("TR_LEGAL_ROLE", "legal_role_grammar"),
    ("TR_ROLE", "legal_role_grammar"),
    ("TR_COURT", "gazetteer"),
    ("TR_ORG", "gazetteer"),
    ("TR_COMPANY", "gazetteer"),
    ("TR_CASE", "structural_label"),
    ("TR_DECISION", "structural_label"),
    ("TR_FILE", "structural_label"),
    ("TR_UYAP", "structural_label"),
    ("STRUCTURAL", "structural_label"),
)


def _method_for(candidate: EntityCandidate) -> str:
    if candidate.verification_method:
        return candidate.verification_method
    if candidate.validated and candidate.detector in _VALIDATED_METHODS:
        return _VALIDATED_METHODS[candidate.detector]
    for prefix, method in _METHOD_BY_DETECTOR_PREFIX:
        if candidate.detector.startswith(prefix):
            return method
    if candidate.method.value == "STRUCTURAL":
        return "structural_label"
    return "regex_format"


def apply_verification(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    updated: list[EntityCandidate] = []
    for candidate in candidates:
        if candidate.verification_level is not None:
            updated.append(candidate)
            continue
        method = _method_for(candidate)
        strong = candidate.validated and candidate.detector in _VALIDATED_METHODS
        level = (
            VerificationLevel.VALIDATED
            if strong
            else VerificationLevel.REVIEW_RECOMMENDED
        )
        attributes = dict(candidate.attributes)
        attributes.setdefault("verification_level", level.value)
        attributes.setdefault("verification_method", method)
        updated.append(
            candidate.model_copy(
                update={
                    "verification_level": level,
                    "verification_method": method,
                    "attributes": attributes,
                }
            )
        )
    return updated
