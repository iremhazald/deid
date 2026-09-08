"""Product scan-mode contract.

EVERY normal user-facing scan is LOCAL_CONTEXT: deterministic rules + local NER.
RULES_ONLY is only for an explicit test / debug / internal request.
"""

from __future__ import annotations

from app.domain.models import DetectionMode

PRODUCT_DETECTION_MODE = DetectionMode.LOCAL_CONTEXT


def resolve_product_analyze_mode(requested: DetectionMode | None) -> DetectionMode:
    """Resolve POST /api/documents/analyze.

    An omitted mode is LOCAL_CONTEXT. RULES_ONLY is never inferred.
    """
    if requested is None:
        return PRODUCT_DETECTION_MODE
    return requested


def local_ner_requested_for(mode: DetectionMode) -> bool:
    return mode == DetectionMode.LOCAL_CONTEXT
