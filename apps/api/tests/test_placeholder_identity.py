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


def _anchored(text: str, start: int, page: int, y: float, x: float) -> EntityCandidate:
    person = _person(text, start)
    return person.model_copy(
        update={
            "page": page,
            "attributes": {"reading_page": page, "reading_y": y, "reading_x": x},
        }
    )


def test_numbers_follow_the_page_then_top_to_bottom_then_left_to_right() -> None:
    lower_on_first_page = _anchored("Ali Demir", 80, 0, 420, 70)
    upper_on_first_page = _anchored("Veli Koç", 400, 0, 90, 280)
    left_of_same_line = _anchored("Ayşe Yılmaz", 900, 0, 90, 60)
    second_page = _anchored("Eda Kurt", 20, 1, 40, 60)
    stamped = {
        item.text: item.placeholder_token
        for item in stamp_placeholder_tokens(
            [second_page, lower_on_first_page, upper_on_first_page, left_of_same_line],
            "tr",
        )
    }
    assert stamped["Ayşe Yılmaz"] == "[KİŞİ_1]"
    assert stamped["Veli Koç"] == "[KİŞİ_2]"
    assert stamped["Ali Demir"] == "[KİŞİ_3]"
    assert stamped["Eda Kurt"] == "[KİŞİ_4]"


def test_a_name_buried_in_a_longer_span_does_not_take_the_first_number() -> None:
    cover = EntityCandidate(
        text="Kuzey Mahallesi 10 Sokak",
        type=EntityType.ADDRESS,
        start=0,
        end=24,
        page=0,
        detector="test",
        method=DetectionMethod.DETERMINISTIC,
    )
    hidden = _person("Eda Kurt", 2)
    visible = _person("Lale Demir", 40)
    stamped = {
        item.text: item.placeholder_token
        for item in stamp_placeholder_tokens([cover, hidden, visible], "tr")
    }
    assert stamped["Lale Demir"] == "[KİŞİ_1]"
    assert stamped["Eda Kurt"] == "[KİŞİ_2]"


def test_a_person_left_out_of_the_labels_does_not_keep_kisi_1() -> None:
    first = _person("Eda Kurt", 0)
    second = _person("Lale Demir", 20)
    stamped = {
        item.text: item.placeholder_token
        for item in stamp_placeholder_tokens(
            [first, second],
            "tr",
            placeholder_entities=[second],
        )
    }
    assert stamped["Lale Demir"] == "[KİŞİ_1]"
    assert stamped["Eda Kurt"] == "[KİŞİ_2]"


def test_a_later_page_does_not_take_the_first_number() -> None:
    first_page = _person("Ali Demir", 500)
    second_page = _person("Eda Kurt", 10).model_copy(update={"page": 1})
    stamped = stamp_placeholder_tokens([second_page, first_page], "tr")
    by_text = {item.text: item.placeholder_token for item in stamped}
    assert by_text["Ali Demir"] == "[KİŞİ_1]"
    assert by_text["Eda Kurt"] == "[KİŞİ_2]"
