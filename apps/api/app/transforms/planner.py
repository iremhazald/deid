from __future__ import annotations

from typing import Any

from app.domain.models import (
    CategoryTransformDefault,
    DecisionSource,
    EntityCandidate,
    EntityType,
    ManualRedaction,
    RedactionDecision,
    ResolutionState,
    TransformationStrategy,
)
from app.transforms.catalog import (
    allowed_strategies,
    recommended_strategy,
)
from app.transforms.strategies import TransformOp, redact_value, transform_entity
from app.transforms.tag_registry import build_document_tag_registry


def resolve_strategy_for_entity(
    entity: EntityCandidate,
    decisions: list[RedactionDecision],
    category_defaults: list[CategoryTransformDefault],
    legacy_method: str | None,
) -> tuple[TransformationStrategy, DecisionSource, dict[str, Any]]:
    by_id = {item.entity_id: item for item in decisions}
    defaults = {item.category: item for item in category_defaults}
    decision = by_id.get(entity.id)

    if decision is not None:
        if decision.action == "KEEP" and decision.strategy is None:
            return TransformationStrategy.KEEP, decision.source, decision.parameters
        if decision.strategy is not None:
            strategy = decision.strategy
            if decision.action == "KEEP":
                strategy = TransformationStrategy.KEEP
            return strategy, decision.source, decision.parameters
        if decision.action == "REDACT":
            # Legacy: REDACT + global method
            if legacy_method == "LABEL":
                return TransformationStrategy.PLACEHOLDER, decision.source, {}
            return TransformationStrategy.REDACT, decision.source, {}

    if entity.type in defaults:
        default = defaults[entity.type]
        return default.strategy, DecisionSource.DEFAULT, default.parameters

    if entity.recommended:
        if legacy_method == "LABEL":
            return TransformationStrategy.PLACEHOLDER, DecisionSource.DEFAULT, {}
        strategy = entity.recommended_strategy or recommended_strategy(
            entity.type, role_confident=entity.role_confident
        )
        return strategy, DecisionSource.DEFAULT, {}

    return TransformationStrategy.KEEP, DecisionSource.DEFAULT, {}


def build_operations(
    text: str,
    entities: list[EntityCandidate],
    decisions: list[RedactionDecision],
    category_defaults: list[CategoryTransformDefault],
    manual_redactions: list[ManualRedaction],
    *,
    locale: str,
    legacy_method: str | None = None,
    initials_font_size: float | None = None,
    tag_locale: str | None = None,
    state: ResolutionState | None = None,
) -> list[TransformOp]:
    counters: dict[str, int] = {}
    planned: list[
        tuple[EntityCandidate, TransformationStrategy, DecisionSource, dict[str, Any]]
    ] = []

    for entity in entities:
        strategy, source, parameters = resolve_strategy_for_entity(
            entity, decisions, category_defaults, legacy_method
        )
        allowed = set(allowed_strategies(entity.type))
        if strategy not in allowed and strategy != TransformationStrategy.KEEP:
            strategy = TransformationStrategy.REDACT

        if strategy in {
            TransformationStrategy.INITIALS,
            TransformationStrategy.PLACEHOLDER,
        }:
            parameters = dict(parameters or {})
            if parameters.get("font_size") is None:
                detected = entity.attributes.get("font_size")
                if detected is not None:
                    parameters["font_size"] = detected
                elif initials_font_size is not None:
                    parameters["font_size"] = initials_font_size
        planned.append((entity, strategy, source, parameters))

    placeholder_entities = [
        entity
        for entity, strategy, _source, _parameters in planned
        if strategy == TransformationStrategy.PLACEHOLDER
    ]
    registry = build_document_tag_registry(
        entities,
        placeholder_entities,
        tag_locale or locale,
        state=state,
    )

    operations: list[TransformOp] = []
    for entity, strategy, source, parameters in planned:
        op = transform_entity(
            text,
            entity,
            strategy,
            locale=locale,
            counters=counters,
            parameters=parameters,
            registry=registry,
        )
        if op is None:
            continue
        op.source = source.value
        operations.append(op)

    for manual in manual_redactions:
        found = False
        has_custom = bool(manual.replacement)
        if (
            manual.start is not None
            and 0 <= manual.start < len(text)
            and text.startswith(manual.text, manual.start)
        ):
            starts = [manual.start]
        else:
            starts = []
            cursor = 0
            while True:
                start = text.find(manual.text, cursor)
                if start < 0:
                    break
                starts.append(start)
                cursor = start + max(1, len(manual.text))
        for start in starts:
            found = True
            end = start + len(manual.text)
            if has_custom:
                replacement = manual.replacement  # type: ignore[assignment]
                strategy = TransformationStrategy.REDACT  # text_rebuild path
                export_path = "text_rebuild"
            else:
                replacement = redact_value(manual.text)
                strategy = TransformationStrategy.REDACT
                export_path = "secure_pdf" if legacy_method != "LABEL" else "text_rebuild"
            operations.append(
                TransformOp(
                    entity_id=None,
                    category="MANUAL",
                    strategy=strategy,
                    start=start,
                    end=end,
                    replacement=replacement,
                    original=manual.text,
                    export_path=export_path,
                    source=DecisionSource.USER_OVERRIDE.value,
                )
            )
        if not found and manual.rectangles:
            operations.append(
                TransformOp(
                    entity_id=None,
                    category="MANUAL",
                    strategy=TransformationStrategy.REDACT,
                    start=0,
                    end=0,
                    replacement=manual.replacement or "",
                    original=manual.text,
                    export_path="text_rebuild" if has_custom else "secure_pdf",
                    source=DecisionSource.USER_OVERRIDE.value,
                )
            )

    return _dedupe_operations(operations)


def _operation_priority(operation: TransformOp) -> tuple[int, int, int]:
    """User overrides win over default overlap losers."""
    user = 1 if operation.source == DecisionSource.USER_OVERRIDE.value else 0
    rewrite = 0
    length = operation.end - operation.start
    return (user, rewrite, length)


def _dedupe_operations(operations: list[TransformOp]) -> list[TransformOp]:
    accepted: list[TransformOp] = []
    for operation in sorted(
        operations,
        key=lambda item: (-_operation_priority(item)[0], -_operation_priority(item)[1], item.start, -_operation_priority(item)[2]),
    ):
        if operation.start == operation.end:
            accepted.append(operation)
            continue
        if any(
            operation.start < other.end and operation.end > other.start
            for other in accepted
        ):
            continue
        accepted.append(operation)
    return accepted


def apply_operations(text: str, operations: list[TransformOp]) -> str:
    """Apply replacements from right to left so earlier offsets stay valid.

    Replacing a span changes string length (offset drift). Example::

        original:  sanık Mehmet Yılmaz'ın tanığı Ayşe Demir
                   start=6  end=19          start=30 end=45
        after 1:   sanık [KİŞİ_1]'in tanığı Ayşe Demir
                   # first span shrank; a left-to-right pass would miss Ayşe

    Operations are therefore sorted by ``end`` (then ``start``) descending.
    Later coordinates still match the original text; earlier ones sit in a
    prefix that was never shifted.
    """
    output = text
    for operation in sorted(
        operations,
        key=lambda item: (item.end, item.start),
        reverse=True,
    ):
        if operation.start == operation.end or operation.start >= len(output):
            continue
        output = output[: operation.start] + operation.replacement + output[operation.end :]
    return output


def apply_transforms(text: str, operations: list[TransformOp]) -> str:
    """Alias for :func:`apply_operations`."""
    return apply_operations(text, operations)


def requires_text_rebuild(operations: list[TransformOp], document_is_pdf: bool) -> bool:
    if not document_is_pdf:
        return True
    transforming = [
        op
        for op in operations
        if op.strategy != TransformationStrategy.KEEP
    ]
    if not transforming:
        return False
    return any(op.export_path != "secure_pdf" for op in transforming)


def seed_category_defaults(
    entities: list[EntityCandidate],
) -> list[CategoryTransformDefault]:
    seen: set[EntityType] = set()
    defaults: list[CategoryTransformDefault] = []
    for entity in entities:
        if entity.type in seen:
            continue
        seen.add(entity.type)
        strategy = entity.recommended_strategy or recommended_strategy(
            entity.type, role_confident=entity.role_confident
        )
        defaults.append(
            CategoryTransformDefault(category=entity.type, strategy=strategy)
        )
    return defaults
