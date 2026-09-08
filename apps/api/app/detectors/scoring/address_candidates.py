"""Composite address candidates from clustered structural signals."""

from __future__ import annotations

import re
from typing import Any

from app.detectors.gazetteers import TURKISH_CITIES, TURKISH_DISTRICTS
from app.detectors.legal.common import make_candidate
from app.detectors.legal.names import clip_trailing_uets_span
from app.detectors.textutil import fold_tr
from app.domain.models import EntityCandidate, EntityType

from app.detectors.scoring.context import DocumentIndex
from app.detectors.scoring.evaluate import attach_score, evaluate_candidate
from app.detectors.scoring.exclusions import is_court_phrase, is_institution_phrase
from app.detectors.scoring.models import ScoringDecision
from app.detectors.scoring.policy import EVIDENCE_ADDRESS_DETECTOR

_MARKER = re.compile(
    r"(?i)(?<![\w.])(?:"
    r"mahallesi|mah\.?|caddesi|cad\.?|soka[gğ]ı|sokagi|sok\.?|"
    r"bulvar[ıi]|bulvari|bul\.?|apartman[ıi]|apt\.?|sitesi|"
    r"no:?|daire:?|kat:?"
    r")(?=\s|[.,;:]|$)"
)
_LABEL = re.compile(r"(?i)\b(?:adres(?:inde)?|ikamet)\b")
_PLACE = re.compile(
    r"\b("
    + "|".join(re.escape(name) for name in sorted(TURKISH_CITIES | TURKISH_DISTRICTS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)


def generate_composite_addresses(
    pages: list[Any],
    existing: list[EntityCandidate],
    index: DocumentIndex,
) -> list[EntityCandidate]:
    """Emit an address only when several structural signals sit together.

    A lone 'Atatürk Mahallesi' is not a complete address.
    """
    found: list[EntityCandidate] = []
    for page in pages:
        text = page.text
        markers = list(_MARKER.finditer(text))
        if not markers:
            continue
        clusters: list[list[re.Match[str]]] = [[markers[0]]]
        for match in markers[1:]:
            if match.start() - clusters[-1][-1].end() <= 80:
                clusters[-1].append(match)
            else:
                clusters.append([match])
        for cluster in clusters:
            start = max(0, cluster[0].start() - 40)
            end = min(len(text), cluster[-1].end() + 40)
            prefix = text[start : cluster[0].start()]
            lead = re.search(
                r"((?:\d{1,3}\.\s*)?[A-ZÇĞİÖŞÜÂÎÛ][A-Za-zÇĞİÖŞÜçğıöşüâîû0-9]+"
                r"(?:\s+[A-ZÇĞİÖŞÜÂÎÛ][A-Za-zÇĞİÖŞÜçğıöşüâîû0-9]+){0,2})\s*$",
                prefix,
            )
            if lead:
                start = start + lead.start(1)
            place = _PLACE.search(text[cluster[-1].end() : end])
            if place:
                end = cluster[-1].end() + place.end()
            else:
                end = cluster[-1].end()
            uets_cut = re.search(r"(?i)\bUETS\b", text[start:end])
            if uets_cut:
                end = start + uets_cut.start()
            abs_start = page.document_offset + start
            abs_end = page.document_offset + end
            if index.overlaps_any(abs_start, abs_end, index.address_spans):
                continue
            if index.overlaps_any(abs_start, abs_end, index.org_spans):
                continue
            span = text[start:end].strip(" ,;.")
            clipped = clip_trailing_uets_span(span)
            if clipped is None:
                continue
            span = span[clipped[0] : clipped[1]].strip(" ,;.")
            if len(span) < 12:
                continue
            if is_court_phrase(span) or is_institution_phrase(span):
                continue
            kinds = {item.group(0).lower()[:3] for item in cluster}
            has_place = bool(_PLACE.search(span))
            has_label = bool(_LABEL.search(text[max(0, start - 24) : start]))
            if len(kinds) < 2 and not (has_place and has_label):
                continue
            if fold_tr(span) in {fold_tr(name) for name in TURKISH_CITIES | TURKISH_DISTRICTS}:
                continue
            candidate = make_candidate(
                page,
                text=span,
                local_start=start,
                local_end=start + len(span),
                entity_type=EntityType.ADDRESS,
                detector=EVIDENCE_ADDRESS_DETECTOR,
                reason="Composite address evidence cluster.",
                validated=False,
                attributes={"source": "address_scoring", "markers": sorted(kinds)},
            )
            scored = evaluate_candidate(candidate, index)
            if scored.decision == ScoringDecision.IGNORE:
                continue
            found.append(attach_score(scored.entity, scored))
            index.address_spans.append((abs_start, abs_end))
    return found
