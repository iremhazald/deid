"""Labeled year/number legal references missed by prefix-only patterns."""

from __future__ import annotations

import re
from typing import Any

from app.detectors.legal.common import make_candidate
from app.domain.models import EntityCandidate, EntityType

from app.detectors.scoring.context import DocumentIndex
from app.detectors.scoring.evaluate import attach_score, evaluate_candidate
from app.detectors.scoring.exclusions import is_list_marker
from app.detectors.scoring.models import ScoringDecision

_LABELED = re.compile(
    r"(?i)\b(?P<label>esas|karar|dosya|soruşturma|sorusturma|talimat|iddianame|"
    r"arabuluculuk)"
    r"(?:\s+(?:no|numara(?:s[ıi])?))?\s*[:.]?\s*"
    r"(?P<num>\d{4}\s*/\s*\d+)\b"
)

_KIND = {
    "esas": (EntityType.CASE_NUMBER, "TR_CASE_NUMBER", "CASE"),
    "karar": (EntityType.DECISION_NUMBER, "TR_DECISION_NUMBER", "DECISION"),
    "dosya": (EntityType.FILE_NUMBER, "TR_FILE_NUMBER", "FILE"),
    "sorusturma": (EntityType.FILE_NUMBER, "TR_FILE_NUMBER", "INVESTIGATION"),
    "talimat": (EntityType.FILE_NUMBER, "TR_FILE_NUMBER", "INSTRUCTION"),
    "iddianame": (EntityType.FILE_NUMBER, "TR_FILE_NUMBER", "INDICTMENT"),
    "arabuluculuk": (EntityType.FILE_NUMBER, "TR_ARBITRATION_NUMBER", "MEDIATION"),
}


def generate_labeled_legal_refs(
    pages: list[Any],
    existing: list[EntityCandidate],
    index: DocumentIndex,
) -> list[EntityCandidate]:
    covered = [(item.start, item.end) for item in existing if item.type in {
        EntityType.CASE_NUMBER, EntityType.FILE_NUMBER, EntityType.DECISION_NUMBER
    }]
    found: list[EntityCandidate] = []
    for page in pages:
        for match in _LABELED.finditer(page.text):
            if is_list_marker(match.group("num")):
                continue
            start = page.document_offset + match.start("num")
            end = page.document_offset + match.end("num")
            if index.overlaps_any(start, end, covered):
                continue
            from app.detectors.textutil import fold_tr_identity

            label = fold_tr_identity(match.group("label"))
            entity_type, detector, kind = _KIND.get(label, (EntityType.FILE_NUMBER, "TR_FILE_NUMBER", "FILE"))
            candidate = make_candidate(
                page,
                text=match.group("num"),
                local_start=match.start("num"),
                local_end=match.end("num"),
                entity_type=entity_type,
                detector=detector,
                reason="Labeled year/number legal reference.",
                attributes={"legal_ref_kind": kind, "source": "legal_ref_scoring"},
            )
            scored = evaluate_candidate(candidate, index)
            if scored.decision == ScoringDecision.IGNORE:
                continue
            found.append(attach_score(scored.entity, scored))
            covered.append((start, end))
    return found
