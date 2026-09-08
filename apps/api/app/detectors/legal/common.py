"""Shared emit helpers for deterministic legal-document parsers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.detectors.textutil import fold_tr
from app.domain.models import (
    DetectionMethod,
    EntityCandidate,
    EntityRelation,
    EntityType,
)

if TYPE_CHECKING:
    from app.detectors.registry import PageText

__all__ = ["fold_tr", "collapse_ws", "make_candidate", "relation"]


def collapse_ws(value: str) -> str:
    return " ".join(value.split())


def make_candidate(
    page: PageText,
    *,
    text: str,
    local_start: int,
    local_end: int,
    entity_type: EntityType,
    detector: str,
    role: str | None = None,
    reason: str | None = None,
    validated: bool = True,
    attributes: dict[str, Any] | None = None,
    relations: list[EntityRelation] | None = None,
) -> EntityCandidate:
    value = text.strip()
    lead = len(text) - len(text.lstrip())
    trail = len(text) - len(text.rstrip())
    start = local_start + lead
    end = local_end - trail
    return EntityCandidate(
        text=value,
        type=entity_type,
        start=page.document_offset + start,
        end=page.document_offset + end,
        page=page.page,
        detector=detector,
        method=DetectionMethod.DETERMINISTIC,
        validated=validated,
        role=role,
        reason=reason,
        attributes=attributes or {},
        relations=relations or [],
    )


def relation(
    kind: str,
    *,
    target: EntityCandidate | None = None,
    target_start: int | None = None,
    target_end: int | None = None,
    target_type: str | None = None,
    target_text: str | None = None,
    label: str | None = None,
) -> EntityRelation:
    if target is not None:
        return EntityRelation(
            kind=kind,
            target_start=target.start,
            target_end=target.end,
            target_type=target.type.value,
            target_text=target.text,
            label=label,
        )
    return EntityRelation(
        kind=kind,
        target_start=target_start,
        target_end=target_end,
        target_type=target_type,
        target_text=target_text,
        label=label,
    )
