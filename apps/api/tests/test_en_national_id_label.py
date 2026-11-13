"""The English national-id label must not match inside a longer word."""

from app.detectors.en.identifiers import parse_identifiers
from app.detectors.registry import PageText
from app.domain.models import EntityType


def _national_ids(text: str) -> list[str]:
    page = PageText(page=0, text=text, document_offset=0)
    return [
        item.text
        for item in parse_identifiers(page)
        if item.type == EntityType.NATIONAL_ID
    ]


def test_national_id_does_not_match_inside_identifier() -> None:
    assert _national_ids("National identifier 666-11-1001") == []


def test_national_id_label_still_takes_the_number() -> None:
    assert _national_ids("National ID: 666-11-1001") == ["666-11-1001"]
    assert _national_ids("National ID no 666-11-1001") == ["666-11-1001"]
    assert _national_ids("National identification number 666-11-1001") == ["666-11-1001"]
