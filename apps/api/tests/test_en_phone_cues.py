"""English phone cues, step one: a function word, telephoned, and call me on."""

from app.detectors.en.identifiers import parse_identifiers
from app.detectors.registry import PageText
from app.domain.models import EntityType


def _phones(text: str) -> list[str]:
    page = PageText(page=0, text=text, document_offset=0)
    return [
        item.text
        for item in parse_identifiers(page)
        if item.type == EntityType.PHONE_NUMBER
    ]


def test_function_word_between_label_and_number() -> None:
    assert _phones("Notices by telephone at 202-555-0172.") == ["202-555-0172"]
    assert _phones("The duty line is phone on 07700 900172.") == ["07700 900172"]
    assert _phones("Tel to 202-555-0173 during office hours.") == ["202-555-0173"]


def test_telephoned_with_optional_to() -> None:
    assert _phones("I then telephoned 202-555-0171 and waited.") == ["202-555-0171"]
    assert _phones("The buyer telephoned to 07700 900173 before completion.") == ["07700 900173"]


def test_call_me_on() -> None:
    assert _phones("Please call me on 07700 900171 if the diary changes.") == ["07700 900171"]


def test_direct_label_still_matches_and_short_numbers_do_not() -> None:
    assert _phones("Phone: 202-555-0142. Tel: 07700 900142.") == [
        "202-555-0142",
        "07700 900142",
    ]
    assert _phones("Phone: 1234567.") == []
    assert _phones("The office extension 214 is the switchboard only.") == []


def test_held_back_cues_do_not_match() -> None:
    assert _phones("Notices go to ada@example.com or 202-555-0174.") == []
    assert _phones("You may call 07700 900174 after the hearing.") == []
    assert _phones("Please call 202-555-0175 if the line is busy.") == []
    assert _phones("Willa reached me at 202-555-0175 from the lobby.") == []
    assert _phones("She would ring 07700 900175 once the train arrived.") == []
