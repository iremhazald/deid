"""Placeholder identity is exact surface match, not coreference.

A repeated full name shares one placeholder. A different person gets another.
A surname alone, such as Kaya after Mehmet Kaya, stays a different tag. That
is the current limitation of the registry, not a coreference failure.
"""

from app.domain.models import DetectionMethod, EntityCandidate, EntityType
from app.transforms.tag_registry import stamp_placeholder_tokens


def _person(text: str, start: int) -> EntityCandidate:
    return EntityCandidate(
        text=text,
        type=EntityType.PERSON_NAME,
        start=start,
        end=start + len(text),
        page=0,
        detector="test",
        method=DetectionMethod.DETERMINISTIC,
    )


def test_the_same_name_shares_a_placeholder_and_a_surname_does_not() -> None:
    stamped = stamp_placeholder_tokens(
        [
            _person("Mehmet Kaya", 0),
            _person("Mehmet Kaya", 20),
            _person("Ayşe Demir", 40),
            _person("Kaya", 60),
        ],
        "tr",
    )
    full_a, full_b, other, surname = stamped

    assert full_a.placeholder_token == full_b.placeholder_token
    assert full_a.placeholder_token != other.placeholder_token
    assert surname.placeholder_token != full_a.placeholder_token
    assert surname.placeholder_token is not None
