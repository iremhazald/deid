"""English PERSON precision guards.

This is not a surname blacklist. ``Page`` after Miss/Ms/Mrs/Mr remains a
valid person surface. Ordinary noun uses of page/pages must not inherit
that identity.

Lives under scoring so evaluate.py does not import ``app.detectors.en``,
which would cycle through registry → scoring.
"""

from __future__ import annotations

import re

from app.detectors.scoring.context import DocumentIndex

_PAGE_SURFACES = frozenset({"page", "pages"})

_TITLE_LEFT = re.compile(
    r"(?i)(?:^|[^A-Za-z])(?:miss|mrs|ms|mr|mx|dr|prof(?:essor)?|sir|dame)\.?\s+$"
)
_ROLE_LEFT = re.compile(
    r"(?i)(?:^|[^A-Za-z])(?:claimant|defendant|plaintiff|applicant|respondent|"
    r"appellant|witness|counsel|judge|justice|solicitor|barrister|attorney|"
    r"lawyer|advocate)\s+$"
)
_DETERMINER_LEFT = re.compile(r"(?i)(?:^|[^A-Za-z])(?:the|this|that|a|an)\s+$")
_NUMBER_LEFT = re.compile(r"\d[\s\u00a0]*$")
_NUMBER_RIGHT = re.compile(r"^[\s\u00a0]*\d")
_PAGE_NOUN_RIGHT = re.compile(
    r"(?i)^[\s\u00a0]+(?:number|no\.?|of|in|from|to)\b"
)


def is_supported_person_page_left(left: str) -> bool:
    """True when a courtesy title or legal role independently supports Page."""
    return bool(_TITLE_LEFT.search(left) or _ROLE_LEFT.search(left))


def is_ordinary_english_page_noun(left: str, surface: str, right: str) -> bool:
    """True for lexical page/pages uses that must not become a person repeat.

    ``Miss Page`` / ``Ms Page`` / role-adjacent ``Page`` stay eligible.
    Untitled ``pages`` is always an ordinary plural noun.
    """
    folded = surface.strip().strip(".,;:").casefold()
    if folded not in _PAGE_SURFACES:
        return False
    if is_supported_person_page_left(left):
        return False
    if folded == "pages":
        return True
    if _NUMBER_LEFT.search(left) or _NUMBER_RIGHT.match(right):
        return True
    if _DETERMINER_LEFT.search(left):
        return True
    if _PAGE_NOUN_RIGHT.match(right):
        return True
    return False


def ordinary_english_page_noun_at(index: DocumentIndex, start: int, end: int) -> bool:
    surface = index.full_text[start:end]
    left = index.left_window(start, 48)
    right = index.right_window(end, 24)
    return is_ordinary_english_page_noun(left, surface, right)
