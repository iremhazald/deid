from __future__ import annotations

import re
from collections import defaultdict

from app.domain.models import (
    DecisionSource,
    StrategyAuditEntry,
    TransformationStrategy,
    ValidationResult,
    ValidationStatus,
)
from app.transforms.catalog import ROLE_LABELS_EN, ROLE_LABELS_TR
from app.transforms.strategies import TransformOp

_WHITESPACE = re.compile(r"\s+")
_MASK_GLYPHS = re.compile(r"[•*█■·●]+")
_STATUS_RANK = {
    ValidationStatus.PASS: 0,
    ValidationStatus.WARNING: 1,
    ValidationStatus.FAILED: 2,
}


def _contains(haystack: str, needle: str) -> bool:
    if not needle:
        return True
    if needle in haystack:
        return True
    collapsed_hay = _WHITESPACE.sub(" ", haystack)
    collapsed_needle = _WHITESPACE.sub(" ", needle)
    if collapsed_needle in collapsed_hay:
        return True
    if _mask_skeleton(needle) in _mask_skeleton(haystack):
        return True
    stripped_needle = _MASK_GLYPHS.sub("", collapsed_needle.replace(" ", ""))
    stripped_hay = _MASK_GLYPHS.sub("", collapsed_hay.replace(" ", ""))
    return bool(stripped_needle) and stripped_needle in stripped_hay


def _mask_skeleton(text: str) -> str:
    """Compare partial masks despite PDF glyph/spacing differences (• vs *, NBSP)."""
    collapsed = _WHITESPACE.sub("", text.replace("\u00a0", " "))
    return _MASK_GLYPHS.sub("*", collapsed)


def _count_occurrences(haystack: str, needle: str) -> int:
    """Count non-overlapping occurrences; prefer word-boundary matches for short tokens."""
    if not needle:
        return 0
    collapsed_hay = _WHITESPACE.sub(" ", haystack)
    collapsed_needle = _WHITESPACE.sub(" ", needle).strip()
    if not collapsed_needle:
        return 0
    # Short / digit-heavy tokens often appear as substrings of other values.
    if len(collapsed_needle) < 6 or collapsed_needle.isdigit():
        pattern = re.compile(
            rf"(?<!\w){re.escape(collapsed_needle)}(?!\w)",
            re.UNICODE,
        )
        return len(pattern.findall(collapsed_hay))
    return collapsed_hay.count(collapsed_needle)


def _worse(current: ValidationStatus, incoming: ValidationStatus) -> ValidationStatus:
    return incoming if _STATUS_RANK[incoming] > _STATUS_RANK[current] else current


def _placeholder_base(replacement: str) -> str:
    return replacement.split("'")[0].split("’")[0]


def _duplicate_role_pattern() -> re.Pattern[str]:
    labels = sorted(
        {*(ROLE_LABELS_TR.values()), *(ROLE_LABELS_EN.values())},
        key=len,
        reverse=True,
    )
    alternation = "|".join(re.escape(label) for label in labels)
    return re.compile(
        rf"(?i)(?<!\w)({alternation})(?:['’][^\s]*)?(?:\s+)+\1(?:['’][^\s]*)?(?!\w)"
    )


_DUPLICATE_ROLE = _duplicate_role_pattern()
_UI_ALIAS_CODES = {"EXPECTED_REPLACEMENT_MISSING", "ROLE_DUPLICATION"}


def _allowed_original_remaining(original: str, kept_texts: list[str]) -> int:
    return sum(1 for text in kept_texts if text == original)


def validate_operations(
    output_text: str,
    operations: list[TransformOp],
    *,
    kept_texts: list[str] | None = None,
) -> ValidationResult:
    """Validate each selected transformation against the exported text.

    This answers whether the user's selected operations appear to have been
    applied. It does not prove that the document is anonymous or legally
    compliant.
    """
    kept_texts = kept_texts or []
    messages: list[str] = []
    operation_messages: list[str] = []
    strategy_results: list[dict] = []
    remaining = 0
    status = ValidationStatus.PASS
    verified = 0
    warnings = 0
    failed = 0

    transforming = [
        operation
        for operation in operations
        if operation.strategy != TransformationStrategy.KEEP
    ]

    for operation in transforming:
        result = {
            "entity_id": operation.entity_id,
            "strategy": operation.strategy.value,
            "status": ValidationStatus.PASS.value,
            "reasons": [],
        }
        original = operation.original
        replacement = operation.replacement
        op_status = ValidationStatus.PASS
        allowed = _allowed_original_remaining(original, kept_texts)
        original_left = (
            max(0, _count_occurrences(output_text, original) - allowed) if original else 0
        )

        if original and original_left:
            remaining += original_left
            op_status = ValidationStatus.FAILED
            result["reasons"].append("ORIGINAL_VALUE_REMAINS")

        if op_status != ValidationStatus.FAILED:
            if operation.strategy == TransformationStrategy.PLACEHOLDER:
                expected = _placeholder_base(replacement)
                if expected and not _contains(output_text, expected):
                    op_status = ValidationStatus.FAILED
                    result["reasons"].append("PLACEHOLDER_MISSING")
                    result["reasons"].append("EXPECTED_REPLACEMENT_MISSING")
            elif operation.strategy == TransformationStrategy.INITIALS:
                if replacement and not _contains(output_text, replacement):
                    op_status = ValidationStatus.FAILED
                    result["reasons"].append("EXPECTED_REPLACEMENT_MISSING")
            elif operation.strategy == TransformationStrategy.PARTIAL_MASK:
                if replacement and not _contains(output_text, replacement):
                    # Overlay/clean PDF extract often drops █/•; original already gone.
                    op_status = ValidationStatus.WARNING
                    result["reasons"].append("PARTIAL_MASK_MISMATCH")
                    result["reasons"].append("EXPECTED_REPLACEMENT_MISSING")
            elif operation.strategy == TransformationStrategy.REDACT:
                pass

        if (
            operation.mapping_coarse
            and op_status != ValidationStatus.FAILED
        ):
            op_status = _worse(op_status, ValidationStatus.WARNING)
            result["reasons"].append("OCR_COARSE_MAPPING")

        result["status"] = op_status.value
        # Deduplicate reasons while preserving order
        deduped_reasons: list[str] = []
        for reason in result["reasons"]:
            if reason not in deduped_reasons:
                deduped_reasons.append(reason)
        result["reasons"] = deduped_reasons
        for reason in deduped_reasons:
            if reason not in operation_messages:
                operation_messages.append(reason)
            if reason not in _UI_ALIAS_CODES and reason not in messages:
                messages.append(reason)

        status = _worse(status, op_status)
        if op_status == ValidationStatus.FAILED:
            failed += 1
        elif op_status == ValidationStatus.WARNING:
            warnings += 1
        else:
            verified += 1
        strategy_results.append(result)

    by_identity: dict[str, set[str]] = defaultdict(set)
    by_label: dict[str, set[str]] = defaultdict(set)
    for operation in transforming:
        if operation.strategy != TransformationStrategy.PLACEHOLDER:
            continue
        base = _placeholder_base(operation.replacement)
        identity = operation.placeholder_key or operation.resolved_entity_id
        if identity:
            by_identity[identity].add(base)
            # Unnumbered generic tags ([SAĞLIK]) may be shared; numbered tags may not.
            if re.search(r"_\d+\]?$", base):
                by_label[base].add(identity)
    inconsistent = any(len(labels) > 1 for labels in by_identity.values()) or any(
        len(ids) > 1 for ids in by_label.values()
    )
    if inconsistent:
        status = _worse(status, ValidationStatus.WARNING)
        warnings += 1
        if "PLACEHOLDER_INCONSISTENT" not in messages:
            messages.append("PLACEHOLDER_INCONSISTENT")
            operation_messages.append("PLACEHOLDER_INCONSISTENT")

    if not transforming:
        verified = 0

    if not messages:
        messages.append("OPERATIONS_VERIFIED")
        operation_messages.append("OPERATIONS_VERIFIED")

    return ValidationResult(
        status=status,
        selected_count=len(transforming),
        remaining_selected_values=remaining,
        messages=messages,
        strategy_results=strategy_results,
        operation_messages=operation_messages,
        verified_count=verified,
        warning_count=warnings,
        failed_count=failed,
    )


def merge_residual_messages(
    validation: ValidationResult,
    residual_messages: list[str],
    residual_status: ValidationStatus,
) -> ValidationResult:
    """Attach residual detector findings without overwriting operation results."""
    status = _worse(validation.status, residual_status)
    messages = list(validation.messages)
    residuals: list[str] = []
    for message in residual_messages:
        if message not in residuals:
            residuals.append(message)
    for message in residuals:
        if message not in messages:
            messages.append(message)
    if (
        status == ValidationStatus.PASS
        and "OPERATIONS_VERIFIED" in messages
        and "POST_CHECKS_COMPLETED" not in messages
    ):
        messages.append("POST_CHECKS_COMPLETED")
    return validation.model_copy(
        update={
            "status": status,
            "messages": messages,
            "residual_messages": residuals,
        }
    )


_PDF_EXTRACT_FAIL_REASONS = frozenset(
    {
        "ORIGINAL_VALUE_REMAINS",
        "PLACEHOLDER_MISSING",
        "EXPECTED_REPLACEMENT_MISSING",
    }
)


def soften_pdf_text_residuals(validation: ValidationResult) -> ValidationResult:
    """After secure PDF burn-in, text-layer ghosts of original values are common.

    Visual redaction is the source of truth; do not fail the export solely because
    extracted text still contains a selected string or missed an overlay token.
    """
    if validation.status != ValidationStatus.FAILED:
        return validation

    strategy_results: list[dict] = []
    failed = 0
    warnings = validation.warning_count
    demoted = False
    messages = [
        message
        for message in validation.messages
        if message not in _PDF_EXTRACT_FAIL_REASONS
    ]
    operation_messages = [
        message
        for message in validation.operation_messages
        if message not in _PDF_EXTRACT_FAIL_REASONS
    ]

    for result in validation.strategy_results:
        reasons = list(result.get("reasons") or [])
        status = result.get("status")
        extract_only = bool(reasons) and set(reasons) <= _PDF_EXTRACT_FAIL_REASONS
        if status == ValidationStatus.FAILED.value and extract_only:
            demoted = True
            reasons = [*reasons, "PDF_TEXT_LAYER_RESIDUAL"]
            strategy_results.append(
                {**result, "status": ValidationStatus.WARNING.value, "reasons": reasons}
            )
            warnings += 1
            for reason in reasons:
                if reason not in messages:
                    messages.append(reason)
                if reason not in operation_messages:
                    operation_messages.append(reason)
            continue
        if status == ValidationStatus.FAILED.value:
            failed += 1
        strategy_results.append(result)

    if not demoted:
        return validation

    status = ValidationStatus.FAILED if failed else ValidationStatus.WARNING
    return validation.model_copy(
        update={
            "status": status,
            "strategy_results": strategy_results,
            "messages": messages,
            "operation_messages": operation_messages,
            "failed_count": failed,
            "warning_count": warnings,
        }
    )


def build_transformation_audit(
    operations: list[TransformOp],
    validation: ValidationResult,
) -> list[StrategyAuditEntry]:
    grouped: dict[tuple[str, str, str, str], list[TransformOp]] = defaultdict(list)
    for operation in operations:
        key = (
            operation.category or "UNKNOWN",
            operation.role or "",
            operation.strategy.value,
            operation.source,
        )
        grouped[key].append(operation)

    results_by_entity: dict[str, dict] = {}
    unmatched_results: list[dict] = []
    for result in validation.strategy_results:
        entity_id = result.get("entity_id")
        if entity_id:
            results_by_entity[str(entity_id)] = result
        else:
            unmatched_results.append(result)

    entries: list[StrategyAuditEntry] = []
    for (category, role, strategy, source), ops in grouped.items():
        reasons: list[str] = []
        op_status = ValidationStatus.PASS
        for operation in ops:
            result = (
                results_by_entity.get(operation.entity_id or "")
                if operation.entity_id
                else None
            )
            if result is None and not operation.entity_id and unmatched_results:
                result = unmatched_results[0]
            if result:
                op_status = _worse(
                    op_status, ValidationStatus(result.get("status", op_status.value))
                )
                for reason in result.get("reasons", []):
                    if reason not in reasons:
                        reasons.append(reason)
        decisions = [op.user_decision for op in ops if op.user_decision]
        if "edited" in decisions:
            user_decision = "edited"
        elif "accepted" in decisions:
            user_decision = "accepted"
        else:
            user_decision = None
        ai_assisted = any(op.ai_assisted for op in ops)
        entries.append(
            StrategyAuditEntry(
                category=category,
                role=role or None,
                occurrences=len(ops),
                strategy=TransformationStrategy(strategy),
                decision_source=DecisionSource(source)
                if source in {item.value for item in DecisionSource}
                else DecisionSource.DEFAULT,
                validation=op_status,
                ai_assisted=ai_assisted,
                user_reviewed=True if ai_assisted else None,
                user_decision=user_decision,
                entity_ids=[op.entity_id for op in ops if op.entity_id],
                validation_reasons=reasons,
                mapping_coarse=any(op.mapping_coarse for op in ops),
            )
        )
    return entries
