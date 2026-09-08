"""Re-identification risk assessment based on quasi-identifiers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.models import EntityCandidate, EntityType, TransformationStrategy


# Quasi-identifier categories that can combine for re-identification
QUASI_IDENTIFIERS = {
    EntityType.DATE,  # Date of birth
    EntityType.POSTAL_CODE,
    EntityType.ADDRESS,
    EntityType.LOCATION,
    EntityType.COURT_NAME,  # Can reveal location
    EntityType.VEHICLE_PLATE,  # Province code
    EntityType.ORGANISATION,  # Employer/affiliation
    EntityType.SALARY_INFORMATION,
}

# High-uniqueness identifiers (even one remaining is high risk)
DIRECT_IDENTIFIERS = {
    EntityType.NATIONAL_ID,
    EntityType.PASSPORT_NUMBER,
    EntityType.IBAN,
    EntityType.CREDIT_CARD,
    EntityType.BANK_ACCOUNT,
    EntityType.EMAIL,
    EntityType.PHONE_NUMBER,
    EntityType.IP_ADDRESS,
    EntityType.URL,
    EntityType.UYAP_ACCESS,
    EntityType.TAX_IDENTIFIER,
    EntityType.EMPLOYEE_ID,
    EntityType.CUSTOMER_ID,
}


@dataclass
class ReidentificationRisk:
    """Assessment of re-identification risk in a document."""
    
    risk_level: Literal["low", "medium", "high", "critical"]
    score: float  # 0.0 (safe) to 1.0 (critical risk)
    
    remaining_direct_identifiers: int
    remaining_quasi_identifiers: int
    
    direct_identifier_types: list[str]
    quasi_identifier_types: list[str]
    
    warnings: list[str]
    recommendations: list[str]


def assess_reidentification_risk(
    entities: list[EntityCandidate],
    decisions: dict[str, tuple[str, TransformationStrategy]],  # entity_id → (action, strategy)
) -> ReidentificationRisk:
    """Assess re-identification risk based on what remains after transformation.
    
    Args:
        entities: All detected entities
        decisions: User decisions mapping entity_id → (action, strategy)
    
    Returns:
        ReidentificationRisk assessment
    """
    # Entities that will remain visible (KEEP or inadequate transformation)
    remaining_direct = []
    remaining_quasi = []
    
    for entity in entities:
        decision = decisions.get(entity.id, ("KEEP", TransformationStrategy.KEEP))
        action, strategy = decision
        
        # Check if entity will remain identifiable
        if action == "KEEP" or strategy == TransformationStrategy.KEEP:
            if entity.type in DIRECT_IDENTIFIERS:
                remaining_direct.append(entity)
            elif entity.type in QUASI_IDENTIFIERS:
                remaining_quasi.append(entity)
        elif strategy == TransformationStrategy.PARTIAL_MASK:
            # Partial masking/generalization still leaves quasi-identifiers
            if entity.type in QUASI_IDENTIFIERS:
                remaining_quasi.append(entity)
    
    direct_count = len(remaining_direct)
    quasi_count = len(remaining_quasi)
    
    # Extract unique types
    direct_types = sorted(set(e.type.value for e in remaining_direct))
    quasi_types = sorted(set(e.type.value for e in remaining_quasi))
    
    # Risk scoring
    warnings = []
    recommendations = []
    
    # Direct identifiers are critical
    if direct_count > 0:
        risk_level = "critical"
        score = 1.0
        warnings.append(
            f"{direct_count} direct identifier(s) remain: {', '.join(direct_types[:3])}"
        )
        recommendations.append(
            "Remove or fully redact all direct identifiers (NATIONAL_ID, EMAIL, PHONE, IBAN, etc.)"
        )
    
    # Quasi-identifier combination risk (k-anonymity inspired)
    elif quasi_count >= 3:
        # 3+ quasi-identifiers → high risk of unique combination
        risk_level = "high"
        score = 0.75
        warnings.append(
            f"{quasi_count} quasi-identifiers remain. Combinations may uniquely identify individuals."
        )
        recommendations.append(
            f"Consider removing or generalizing: {', '.join(quasi_types[:5])}"
        )
    
    elif quasi_count == 2:
        risk_level = "medium"
        score = 0.5
        warnings.append(
            f"2 quasi-identifiers remain: {', '.join(quasi_types)}"
        )
        recommendations.append(
            "Two quasi-identifiers may narrow down identity in small populations."
        )
    
    elif quasi_count == 1:
        risk_level = "low"
        score = 0.25
        warnings.append(
            f"1 quasi-identifier remains: {quasi_types[0]}"
        )
        recommendations.append(
            "Single quasi-identifier has low re-identification risk alone."
        )
    
    else:
        risk_level = "low"
        score = 0.0
        recommendations.append(
            "No identifiable quasi-identifiers detected in final document."
        )
    
    return ReidentificationRisk(
        risk_level=risk_level,
        score=score,
        remaining_direct_identifiers=direct_count,
        remaining_quasi_identifiers=quasi_count,
        direct_identifier_types=direct_types,
        quasi_identifier_types=quasi_types,
        warnings=warnings,
        recommendations=recommendations,
    )
