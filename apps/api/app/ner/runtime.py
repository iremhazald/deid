"""LOCAL_CONTEXT orchestration: NER → candidates → existing scoring/resolve.

Insertion point (pipeline._build_analysis): after deterministic detectors,
structural labels, custom terms, court letterheads and QR codes; before
merge_rule_candidates / repeats / assign_resolved_entities / apply_policy.

RULES_ONLY never calls this module.
"""

from __future__ import annotations

import logging

from app.detectors.registry import PageText
from app.detectors.scoring.context import DocumentIndex
from app.detectors.scoring.evaluate import attach_score, evaluate_candidate
from app.detectors.scoring.models import HardValidation, ScoredCandidate, ScoringDecision
from app.detectors.scoring.policy import HIGH_CONFIDENCE_STRUCTURED_SOURCE, candidate_class_for
from app.detectors.scoring.resolve import resolve_scored
from app.detectors.legal.merge import detector_rank
from app.domain.models import EntityCandidate, EntityType
from app.ner.adapter import detector_for, ner_prediction_to_candidate
from app.ner.instrumentation import (
    log_ner_metrics,
    log_ner_samples,
    log_ner_status,
    timed_ms,
)
from app.ner.models import (
    LocalNERError,
    LocalNERErrorCode,
    LocalNERMetrics,
    LocalNERRun,
    LocalNERStatus,
    NERPrediction,
)
from app.ner.provider import ner_registry

logger = logging.getLogger(__name__)

_HARD_AUTHORITY_TYPES = frozenset(
    {
        EntityType.NATIONAL_ID,
        EntityType.TAX_IDENTIFIER,
        EntityType.IBAN,
        EntityType.CREDIT_CARD,
        EntityType.BANK_ACCOUNT,
        EntityType.EMAIL,
        EntityType.PHONE_NUMBER,
        EntityType.URL,
        EntityType.IP_ADDRESS,
        EntityType.CASE_NUMBER,
        EntityType.FILE_NUMBER,
        EntityType.DECISION_NUMBER,
        EntityType.UYAP_ACCESS,
        EntityType.SYSTEM_URL,
        EntityType.PROFESSIONAL_ID,
    }
)

_USER_SAFE_UNAVAILABLE = (
    "Local Context Scan needs a language model installed on this computer. "
    "Standard Scan still works without it."
)
_USER_SAFE_FAILED = (
    "Local Context Scan could not finish the on-device language pass. "
    "Rule-based findings are still shown."
)
_USER_SAFE_LANGUAGE = (
    "Local Context Scan needs an explicit document language of Turkish or English."
)


def normalize_document_language(raw: str | None) -> str | None:
    from app.language.resolve import normalize_requested_language

    normalized = normalize_requested_language(raw)
    if normalized in {"tr", "en"}:
        return normalized
    return None


def run_local_ner_layer(
    pages: list[PageText],
    existing: list[EntityCandidate],
    language: str | None,
) -> LocalNERRun:
    """Discover NER candidates and score them with the existing evidence engine."""
    resolved_language = normalize_document_language(language)
    if resolved_language is None:
        log_ner_status(
            language=language,
            provider=None,
            provider_class=None,
            model_id=None,
            status=LocalNERStatus.FAILED.value,
            error_code=LocalNERErrorCode.LOCAL_NER_LANGUAGE_UNSUPPORTED,
        )
        return LocalNERRun(
            status=LocalNERStatus.FAILED,
            language=language,
            error_code=LocalNERErrorCode.LOCAL_NER_LANGUAGE_UNSUPPORTED,
            error_message=_USER_SAFE_LANGUAGE,
        )
    registry = ner_registry()
    try:
        provider = registry.provider_for(resolved_language)
    except ValueError:
        log_ner_status(
            language=resolved_language,
            provider=None,
            provider_class=None,
            model_id=None,
            status=LocalNERStatus.FAILED.value,
            error_code=LocalNERErrorCode.LOCAL_NER_LANGUAGE_UNSUPPORTED,
        )
        return LocalNERRun(
            status=LocalNERStatus.FAILED,
            language=resolved_language,
            error_code=LocalNERErrorCode.LOCAL_NER_LANGUAGE_UNSUPPORTED,
            error_message=_USER_SAFE_LANGUAGE,
        )
    provider_class = type(provider).__name__
    if not provider.is_available():
        log_ner_status(
            language=resolved_language,
            provider=provider.provider_name,
            provider_class=provider_class,
            model_id=provider.model_id,
            status=LocalNERStatus.UNAVAILABLE.value,
            error_code=LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
            model_loaded=bool(getattr(provider, "loaded", False)),
        )
        return LocalNERRun(
            status=LocalNERStatus.UNAVAILABLE,
            language=resolved_language,
            provider=provider.provider_name,
            model_id=provider.model_id,
            error_code=LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
            error_message=_USER_SAFE_UNAVAILABLE,
        )
    characters = sum(len(page.text) for page in pages)
    load_ms = provider.last_load_ms
    predict_before = int(getattr(provider, "predict_calls", 0) or 0)
    chunks_before = int(getattr(provider, "chunks_seen", 0) or 0)
    try:
        with timed_ms() as inference:
            paged = _predict_pages(provider, pages, resolved_language)
        predict_called = int(getattr(provider, "predict_calls", 0) or 0) > predict_before
        if not predict_called:
            predict_called = bool(pages)
        if not provider.loaded:
            log_ner_status(
                language=resolved_language,
                provider=provider.provider_name,
                provider_class=provider_class,
                model_id=provider.model_id,
                status=LocalNERStatus.FAILED.value,
                error_code=LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                predict_called=predict_called,
                model_loaded=False,
            )
            return LocalNERRun(
                status=LocalNERStatus.FAILED,
                language=resolved_language,
                provider=provider.provider_name,
                model_id=provider.model_id,
                error_code=LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
                error_message=_USER_SAFE_FAILED,
            )
        load_ms = provider.last_load_ms if load_ms is None else load_ms
        predictions = [item for _, group in paged for item in group]
        raw_candidates = _predictions_to_candidates(paged, resolved_language)
        for item in raw_candidates:
            if _overlaps_existing(item, existing):
                item.attributes["ner_overlap_existing_rule"] = True
        scored, accept, review, ignore = _score_ner_candidates_counted(
            pages, raw_candidates, existing
        )
        merged = resolve_ner_with_existing(existing, scored)
        chunk_count = int(getattr(provider, "chunks_seen", 0) or 0) - chunks_before
        if chunk_count <= 0:
            chunk_count = _count_expected_chunks(pages)
        metrics = LocalNERMetrics(
            load_ms=load_ms,
            inference_ms=inference[0],
            characters=characters,
            raw_prediction_count=len(predictions),
            candidate_count=len(merged),
            chunk_count=chunk_count,
            converted_candidate_count=len(raw_candidates),
            accept_count=accept,
            review_count=review,
            ignore_count=ignore,
            survived_merge_count=len(merged),
            predict_called=predict_called,
            model_loaded=bool(provider.loaded),
            provider_class=provider_class,
        )
        log_ner_metrics(
            language=resolved_language,
            provider=provider.provider_name,
            load_ms=metrics.load_ms,
            inference_ms=metrics.inference_ms,
            characters=characters,
            tokens=None,
            raw_predictions=len(predictions),
            candidates=len(raw_candidates),
            status=LocalNERStatus.COMPLETED.value,
            model_id=provider.model_id,
            provider_class=provider_class,
            chunks=chunk_count,
            accept=accept,
            review=review,
            ignore=ignore,
            survived_merge=len(merged),
            predict_called=predict_called,
            model_loaded=bool(provider.loaded),
        )
        log_ner_samples(predictions)
        return LocalNERRun(
            status=LocalNERStatus.COMPLETED,
            language=resolved_language,
            provider=provider.provider_name,
            model_id=provider.model_id,
            candidates=merged,
            candidate_count=len(merged),
            metrics=metrics,
            detectors=[detector_for(resolved_language)],
        )
    except LocalNERError as exc:
        status = (
            LocalNERStatus.UNAVAILABLE
            if exc.code
            in {
                LocalNERErrorCode.LOCAL_NER_MODEL_UNAVAILABLE,
                LocalNERErrorCode.LOCAL_NER_DEPENDENCY_MISSING,
            }
            else LocalNERStatus.FAILED
        )
        message = (
            _USER_SAFE_UNAVAILABLE
            if status == LocalNERStatus.UNAVAILABLE
            else _USER_SAFE_FAILED
        )
        logger.warning(
            "[local-ner] provider initialization or inference error code=%s",
            exc.code,
            exc_info=True,
        )
        log_ner_status(
            language=resolved_language,
            provider=provider.provider_name,
            provider_class=provider_class,
            model_id=provider.model_id,
            status=status.value,
            error_code=exc.code,
            predict_called=int(getattr(provider, "predict_calls", 0) or 0) > predict_before,
            model_loaded=bool(getattr(provider, "loaded", False)),
        )
        return LocalNERRun(
            status=status,
            language=resolved_language,
            provider=provider.provider_name,
            model_id=provider.model_id,
            error_code=exc.code,
            error_message=message,
        )
    except Exception:
        logger.exception(
            "[local-ner] unhandled NER exception language=%s provider=%s model=%s",
            resolved_language,
            provider.provider_name,
            provider.model_id,
        )
        log_ner_status(
            language=resolved_language,
            provider=provider.provider_name,
            provider_class=provider_class,
            model_id=provider.model_id,
            status=LocalNERStatus.FAILED.value,
            error_code=LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
            predict_called=int(getattr(provider, "predict_calls", 0) or 0) > predict_before,
            model_loaded=bool(getattr(provider, "loaded", False)),
        )
        return LocalNERRun(
            status=LocalNERStatus.FAILED,
            language=resolved_language,
            provider=provider.provider_name,
            model_id=provider.model_id,
            error_code=LocalNERErrorCode.LOCAL_NER_INFERENCE_FAILED,
            error_message=_USER_SAFE_FAILED,
        )


def _predict_pages(
    provider, pages: list[PageText], language: str
) -> list[tuple[PageText, list[NERPrediction]]]:
    return [(page, provider.predict(page.text, language)) for page in pages]


def _predictions_to_candidates(
    paged: list[tuple[PageText, list[NERPrediction]]],
    language: str,
) -> list[EntityCandidate]:
    candidates: list[EntityCandidate] = []
    for page, predictions in paged:
        for prediction in predictions:
            converted = ner_prediction_to_candidate(
                prediction, page, document_language=language
            )
            if converted is not None:
                candidates.append(converted)
    return candidates


def _overlaps(left: EntityCandidate, right: EntityCandidate) -> bool:
    return left.page == right.page and left.start < right.end and right.start < left.end


def _overlaps_existing(item: EntityCandidate, existing: list[EntityCandidate]) -> bool:
    return any(_overlaps(item, other) for other in existing)


def score_ner_candidates(
    pages: list[PageText],
    ner_candidates: list[EntityCandidate],
    existing: list[EntityCandidate],
) -> list[EntityCandidate]:
    """Run the existing evidence scorer on NER candidates only."""
    scored, _accept, _review, _ignore = _score_ner_candidates_counted(
        pages, ner_candidates, existing
    )
    return scored


def _score_ner_candidates_counted(
    pages: list[PageText],
    ner_candidates: list[EntityCandidate],
    existing: list[EntityCandidate],
) -> tuple[list[EntityCandidate], int, int, int]:
    """Same scoring path as score_ner_candidates, plus decision counters."""
    if not ner_candidates:
        return [], 0, 0, 0
    index = DocumentIndex.build(pages, list(existing) + list(ner_candidates))
    accept = review = ignore = 0
    kept: list[EntityCandidate] = []
    for item in ner_candidates:
        evaluated = evaluate_candidate(item, index)
        if evaluated.decision == ScoringDecision.ACCEPT:
            accept += 1
        elif evaluated.decision == ScoringDecision.REVIEW:
            review += 1
        else:
            ignore += 1
        if evaluated.decision != ScoringDecision.IGNORE:
            kept.append(attach_score(evaluated.entity, evaluated))
    return kept, accept, review, ignore


def _count_expected_chunks(pages: list[PageText]) -> int:
    from app.core.config import get_settings
    from app.ner.chunking import iter_char_chunks

    settings = get_settings()
    total = 0
    for page in pages:
        if not page.text:
            continue
        total += sum(
            1
            for _ in iter_char_chunks(
                page.text,
                max_chars=settings.deid_ner_max_chars_per_chunk,
                overlap=settings.deid_ner_chunk_overlap_chars,
            )
        )
    return total


def _scored_view(entity: EntityCandidate) -> ScoredCandidate:
    attrs = entity.attributes or {}
    raw_decision = attrs.get("scoring_decision")
    try:
        decision = ScoringDecision(raw_decision) if raw_decision else (
            ScoringDecision.REVIEW if entity.needs_review else ScoringDecision.ACCEPT
        )
    except ValueError:
        decision = ScoringDecision.ACCEPT
    raw_hard = attrs.get("hard_validation")
    try:
        hard = HardValidation(raw_hard) if raw_hard else HardValidation.NOT_APPLICABLE
    except ValueError:
        hard = HardValidation.NOT_APPLICABLE
    try:
        score = int(attrs.get("evidence_score") or 0)
    except (TypeError, ValueError):
        score = 0
    return ScoredCandidate(
        entity=entity,
        candidate_class=candidate_class_for(entity.type, entity.detector),
        hard_validation=hard,
        evidence_score=score,
        decision=decision,
        conflict_reason=str(attrs.get("conflict_reason") or "") or None,
        parent_candidate_id=str(attrs.get("parent_candidate_id") or "") or None,
    )


def resolve_ner_with_existing(
    existing: list[EntityCandidate],
    ner_candidates: list[EntityCandidate],
) -> list[EntityCandidate]:
    """Keep structured-identifier authority; reuse resolve_scored for type conflicts."""
    if not ner_candidates:
        return []
    hard = [
        item
        for item in existing
        if item.type in _HARD_AUTHORITY_TYPES
        and (
            item.validated
            or (item.attributes or {}).get("hard_validation") == HardValidation.VALID
        )
    ]
    filtered: list[EntityCandidate] = []
    for item in ner_candidates:
        if any(_overlaps(item, other) for other in hard):
            continue
        if item.type in _HARD_AUTHORITY_TYPES:
            continue
        filtered.append(item)
    if not filtered:
        return []
    existing_scored = [_scored_view(item) for item in existing]
    ner_scored = [_scored_view(item) for item in filtered]
    # Prefer existing high-rank legal-role persons over a conflicting NER ORG.
    protected_people = [
        item
        for item in existing_scored
        if item.type
        in {
            EntityType.PERSON_NAME,
            EntityType.LAWYER_NAME,
            EntityType.JUDGE_NAME,
            EntityType.CLAIMANT_NAME,
            EntityType.DEFENDANT_NAME,
            EntityType.WITNESS_NAME,
            EntityType.EXPERT_NAME,
        }
        and (
            item.detector in HIGH_CONFIDENCE_STRUCTURED_SOURCE
            or detector_rank(item.detector) >= 70
        )
    ]
    usable_ner: list[ScoredCandidate] = []
    for item in ner_scored:
        if item.type == EntityType.ORGANISATION and any(
            item.page == other.page
            and item.start < other.end
            and other.start < item.end
            for other in protected_people
        ):
            continue
        usable_ner.append(item)
    resolved = resolve_scored(existing_scored + usable_ner)
    ner_ids = {item.id for item in filtered}
    kept: list[EntityCandidate] = []
    for item in resolved:
        if item.entity.id in ner_ids and item.decision != ScoringDecision.IGNORE:
            kept.append(attach_score(item.entity, item) if item.evidence else item.entity)
    return kept
