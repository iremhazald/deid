"""An email followed by sentence punctuation is still detected."""

from app.detectors.registry import PageText, detect_global
from app.domain.models import EntityType

ADDRESS = "patient@example.com"


def _emails(text: str) -> list[tuple[str, int, int]]:
    page = PageText(page=0, text=text, document_offset=0)
    return [
        (item.text, item.start, item.end)
        for item in detect_global(page)
        if item.type == EntityType.EMAIL
    ]


def test_sentence_punctuation_stays_outside_the_address() -> None:
    for punctuation in (".", ",", ";", ":", ")", "]", '"', "'", "\u201d", "\u2019"):
        text = f"Write to {ADDRESS}{punctuation} Thanks"
        found = _emails(text)
        assert found == [(ADDRESS, text.index(ADDRESS), text.index(ADDRESS) + len(ADDRESS))]


def test_address_at_the_end_of_the_text() -> None:
    text = f"Contact {ADDRESS}"
    assert _emails(text) == [(ADDRESS, text.index(ADDRESS), len(text))]


def test_address_followed_by_a_full_stop_and_a_line_break() -> None:
    text = f"E-posta {ADDRESS}.\nSonraki satir."
    start = text.index(ADDRESS)
    assert _emails(text) == [(ADDRESS, start, start + len(ADDRESS))]
    assert text[start + len(ADDRESS) : start + len(ADDRESS) + 2] == ".\n"


def test_a_longer_domain_stays_one_address() -> None:
    longer = "patient@example.co.uk"
    text = f"Write to {longer} today"
    start = text.index(longer)
    assert _emails(text) == [(longer, start, start + len(longer))]


def test_address_characters_after_the_match_are_rejected() -> None:
    assert _emails("patient@example.com-extra") == []
    assert _emails("patient@example.com+tag") == []
    assert _emails("patient@example.com2") == []
    assert _emails("patient@example.com.2extra") == []
    full = "patient@example.com.department"
    assert _emails(full) == [(full, 0, len(full))]
