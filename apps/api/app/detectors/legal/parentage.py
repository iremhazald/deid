"""Parentage grammar: X ve Y oğlu / kızı."""

from __future__ import annotations

import re

from app.detectors.legal.common import fold_tr, make_candidate, relation
from app.detectors.legal.names import _TOKEN, collapse_name
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

# Father/mother sides are 1–3 name tokens; the whole phrase is the signal.
_PARENT = rf"({_TOKEN}(?:\s+{_TOKEN}){{0,2}})"
PARENTAGE_RE = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü]){_PARENT}\s+ve\s+{_PARENT}\s+"
    rf"(?P<rel>oğlu|oglu|kızı|kizi)(?![\wÇĞİÖŞÜçğıöşü])",
    re.IGNORECASE,
)

_NAME_PART_STOP = frozenset(
    {
        "ve",
        "ile",
        "olan",
        "doğumlu",
        "dogumlu",
        "tc",
        "kimlik",
        "sanık",
        "davacı",
        "davalı",
    }
)


def _parent_ok(value: str) -> bool:
    tokens = collapse_name(value).split()
    if not 1 <= len(tokens) <= 3:
        return False
    for token in tokens:
        folded = fold_tr(token.strip(".,;"))
        if folded in _NAME_PART_STOP or any(char.isdigit() for char in token):
            return False
        letters = [char for char in token if char.isalpha()]
        if len(letters) < 2 or not (letters[0].isupper() or token.isupper()):
            return False
    return True


def parse_parentage(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    for match in PARENTAGE_RE.finditer(page.text):
        father_raw, mother_raw = match.group(1), match.group(2)
        if not _parent_ok(father_raw) or not _parent_ok(mother_raw):
            continue
        rel = "SON" if fold_tr(match.group("rel")).startswith("ogl") else "DAUGHTER"
        father = make_candidate(
            page,
            text=father_raw,
            local_start=match.start(1),
            local_end=match.end(1),
            entity_type=EntityType.PERSON_NAME,
            detector="TR_PARENTAGE",
            role="PARENT",
            reason="Parentage grammar (father).",
            attributes={"relationship": "PARENTAGE", "parent_role": "FATHER", "child_gender": rel},
        )
        mother = make_candidate(
            page,
            text=mother_raw,
            local_start=match.start(2),
            local_end=match.end(2),
            entity_type=EntityType.PERSON_NAME,
            detector="TR_PARENTAGE",
            role="PARENT",
            reason="Parentage grammar (mother).",
            attributes={"relationship": "PARENTAGE", "parent_role": "MOTHER", "child_gender": rel},
            relations=[
                relation("PARENT_OF", target=father, label=rel),
                relation("PARENTAGE", label=rel),
            ],
        )
        father = make_candidate(
            page,
            text=father_raw,
            local_start=match.start(1),
            local_end=match.end(1),
            entity_type=EntityType.PERSON_NAME,
            detector="TR_PARENTAGE",
            role="PARENT",
            reason="Parentage grammar (father).",
            attributes={"relationship": "PARENTAGE", "parent_role": "FATHER", "child_gender": rel},
            relations=[
                relation("PARENT_OF", target=mother, label=rel),
                relation("PARENTAGE", label=rel),
            ],
        )
        found.extend((father, mother))
    return found
