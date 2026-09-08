"""Convert NER predictions into DeID candidates. No masking here."""

from __future__ import annotations

import re

from app.detectors.legal.names import (
    clip_trailing_uets_span,
    is_isolated_letter_person_surface,
    is_isolated_uppercase_fragment,
    is_procedural_notice_surface,
    is_uets_label_surface,
    strip_possessive,
)
from app.detectors.registry import PageText
from app.domain.models import DetectionMethod, EntityCandidate, EntityType
from app.ner.labels import mapped_entity_type, normalize_ner_label
from app.ner.models import NERPrediction

DETECTOR_TR = "LOCAL_NER_TR"
DETECTOR_EN = "LOCAL_NER_EN"

_PERSON_TYPES = {
    EntityType.PERSON_NAME,
    EntityType.FIRST_NAME,
    EntityType.LAST_NAME,
    EntityType.ALIAS,
    EntityType.JUDGE_NAME,
    EntityType.LAWYER_NAME,
    EntityType.CLAIMANT_NAME,
    EntityType.DEFENDANT_NAME,
    EntityType.WITNESS_NAME,
    EntityType.EXPERT_NAME,
}
_SOFT_SURFACE_TYPES = _PERSON_TYPES | {
    EntityType.LOCATION,
    EntityType.BIRTH_PLACE,
    EntityType.ORGANISATION,
    EntityType.COMPANY_NAME,
}

_EN_POSSESSIVE = re.compile(r"^(.+?)['’]s$", re.IGNORECASE)
_TRAILING_PUNCT = re.compile(r"[\s,;:]+$")
_LEADING_PUNCT = re.compile(r"^[\s,;:]+")


def detector_for(language: str) -> str:
    return DETECTOR_TR if language == "tr" else DETECTOR_EN


def _trim_surface(source: str, start: int, end: int, language: str) -> tuple[int, int, str] | None:
    if start < 0 or end > len(source) or end <= start:
        return None
    surface = source[start:end]
    lead = _LEADING_PUNCT.match(surface)
    if lead:
        start += lead.end()
        surface = source[start:end]
    trail = _TRAILING_PUNCT.search(surface)
    if trail:
        end -= len(trail.group(0))
        surface = source[start:end]
    if not surface:
        return None
    if language == "tr":
        stripped = strip_possessive(surface)
        if stripped and surface.startswith(stripped) and stripped != surface:
            end = start + len(stripped)
            surface = source[start:end]
    else:
        possessive = _EN_POSSESSIVE.match(surface)
        if possessive:
            end = start + len(possessive.group(1))
            surface = source[start:end]
    if not surface.strip() or source[start:end] != surface:
        return None
    return start, end, surface


def ner_prediction_to_candidate(
    prediction: NERPrediction,
    page: PageText,
    *,
    document_language: str,
) -> EntityCandidate | None:
    """Build one evidence candidate. Offset mismatch → drop (never redact)."""
    entity_type = mapped_entity_type(prediction.label)
    if entity_type is None:
        return None
    local_start = prediction.start
    local_end = prediction.end
    page_text = page.text
    if local_start < 0 or local_end > len(page_text) or local_end <= local_start:
        return None
    if page_text[local_start:local_end] != prediction.text:
        # Allow only whitespace-equivalent reported surfaces.
        if "".join(page_text[local_start:local_end].split()) != "".join(prediction.text.split()):
            return None
    trimmed = _trim_surface(page_text, local_start, local_end, document_language)
    if trimmed is None:
        return None
    local_start, local_end, surface = trimmed
    if not surface or page_text[local_start:local_end] != surface:
        return None
    if is_procedural_notice_surface(surface) or is_uets_label_surface(surface):
        return None
    clipped = clip_trailing_uets_span(surface)
    if clipped is None:
        return None
    clip_start, clip_end = clipped
    if (clip_start, clip_end) != (0, len(surface)):
        local_start += clip_start
        local_end = local_start + (clip_end - clip_start)
        surface = page_text[local_start:local_end]
        if not surface or is_uets_label_surface(surface):
            return None
    if entity_type in _SOFT_SURFACE_TYPES:
        if is_isolated_letter_person_surface(surface):
            return None
        if document_language == "tr" and is_isolated_uppercase_fragment(surface):
            return None
    abs_start = page.document_offset + local_start
    abs_end = page.document_offset + local_end
    score = prediction.score
    if score is not None:
        score = max(0.0, min(1.0, float(score)))
    return EntityCandidate(
        text=surface,
        type=entity_type,
        start=abs_start,
        end=abs_end,
        page=page.page,
        detector=detector_for(document_language),
        method=DetectionMethod.DETERMINISTIC,
        validated=False,
        confidence=None,
        reason="Local contextual candidate; routed through evidence scoring.",
        attributes={
            "source": "local_ner",
            "ner_label": normalize_ner_label(prediction.label),
            "ner_raw_label": prediction.label,
            "ner_model_score": score,
            "ner_language": prediction.language,
            "ner_provider": prediction.provider,
            "ner_model_id": prediction.model_id,
            "identity_resolved": False,
        },
    )
