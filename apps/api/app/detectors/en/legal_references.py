"""English-General legal reference numbers: label + plausible value only."""

from __future__ import annotations

import re

from app.detectors.en.common import alt_pattern, make_candidate, plausible_ref_value, seed
from app.detectors.en.vocab import CASE_REF_LABELS
from app.detectors.registry import PageText
from app.detectors.scoring.exclusions import is_paragraph_number_marker
from app.domain.models import EntityCandidate, EntityType

_KIND_TYPE = {
    "CASE": (EntityType.CASE_NUMBER, "EN_CASE_NUMBER"),
    "FILE": (EntityType.FILE_NUMBER, "EN_FILE_NUMBER"),
}
_LABELS = sorted((item[0] for item in CASE_REF_LABELS), key=len, reverse=True)
_LABEL_BODY = alt_pattern(_LABELS)
# Explicit identifier syntax: Label: value (value may wrap after a colon)
# or same-line glue (Case No1400945.2017). Do not let a sentence-final
# "reference" / "ref" consume the next paragraph marker across a newline.
_LABELED = re.compile(
    rf"(?i)(?<![A-Za-z])(?P<label>{_LABEL_BODY})(?![A-Za-z])"
    rf"\.?"
    rf"(?:"
    rf"\s*[:\-–]\s*"
    rf"|"
    rf"[ \t]*"
    rf")"
    rf"(?P<value>[A-Za-z0-9][A-Za-z0-9./\-]{{2,40}})"
)
_KIND = {label: kind for label, kind in CASE_REF_LABELS}


def parse_legal_references(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()
    for match in _LABELED.finditer(page.text):
        value = match.group("value").strip().rstrip(".,;:")
        if not plausible_ref_value(value):
            continue
        start = match.start("value")
        if is_paragraph_number_marker(value, page.text, start):
            continue
        end = start + len(value)
        if (start, end) in seen:
            continue
        seen.add((start, end))
        kind = _KIND.get(match.group("label").casefold().rstrip("."), "FILE")
        entity_type, detector = _KIND_TYPE[kind]
        found.append(
            make_candidate(
                page,
                text=value,
                local_start=start,
                local_end=end,
                entity_type=entity_type,
                detector=detector,
                reason="English legal-reference label with a plausible value.",
                attributes={
                    "legal_ref_kind": kind,
                    "source": "en_legal_ref",
                    "evidence": seed(("en_case_reference_label", 6)),
                },
            )
        )
    return found
