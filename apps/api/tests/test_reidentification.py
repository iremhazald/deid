"""Risk score treats a visible date of birth as a quasi-identifier."""

from app.domain.models import (
    DetectionMethod,
    EntityCandidate,
    EntityType,
    TransformationStrategy,
)
from app.privacy.reidentification import assess_reidentification_risk


def _candidate(entity_type: EntityType) -> EntityCandidate:
    return EntityCandidate(
        text="01.01.1990",
        type=entity_type,
        start=0,
        end=10,
        page=0,
        detector="test",
        method=DetectionMethod.DETERMINISTIC,
    )


def test_kept_date_of_birth_raises_risk_above_a_masked_one() -> None:
    entity = _candidate(EntityType.DATE_OF_BIRTH)
    kept = assess_reidentification_risk(
        [entity],
        {entity.id: ("KEEP", TransformationStrategy.KEEP)},
    )
    masked = assess_reidentification_risk(
        [entity],
        {entity.id: ("REDACT", TransformationStrategy.REDACT)},
    )

    assert kept.score > masked.score
    assert kept.quasi_identifier_types == ["DATE_OF_BIRTH"]
    assert masked.remaining_quasi_identifiers == 0
    assert masked.score == 0.0


def test_a_kept_calendar_date_still_counts_as_a_quasi_identifier() -> None:
    entity = _candidate(EntityType.DATE)
    kept = assess_reidentification_risk(
        [entity],
        {entity.id: ("KEEP", TransformationStrategy.KEEP)},
    )

    assert kept.quasi_identifier_types == ["DATE"]
    assert kept.score > 0.0
