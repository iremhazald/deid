"""Dev-only scoring inspection. Never log raw sensitive surfaces in production."""

from __future__ import annotations

import os

from app.detectors.scoring.models import ScoredCandidate

_DEBUG_ENV = "DEID_SCORING_DEBUG"


def scoring_debug_enabled() -> bool:
    return os.environ.get(_DEBUG_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def redact_surface(value: str) -> str:
    if len(value) <= 2:
        return "…"
    return f"{value[0]}…{value[-1]}({len(value)})"


def format_scored(scored: ScoredCandidate, *, redact: bool = True) -> str:
    surface = redact_surface(scored.entity.text) if redact else scored.entity.text
    lines = [
        f"{scored.entity.type.value} {surface}",
        f"detector={scored.detector}",
        f"hard_validation={scored.hard_validation.value}",
    ]
    for item in scored.evidence:
        lines.append(f"+ {item.code:<32} {item.weight}")
    for item in scored.negative_evidence:
        lines.append(f"- {item.code:<32} {item.weight}")
    lines.append(f"{'score':<34} {scored.evidence_score}")
    lines.append(f"decision={scored.decision.value}")
    if scored.conflict_reason:
        lines.append(f"conflict={scored.conflict_reason}")
    return "\n".join(lines)
