"""Lightweight local-NER timing. Never logs full document text."""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator

from app.ner.models import LocalNERMetrics

logger = logging.getLogger(__name__)

_DEBUG_ENV = "DEID_NER_DEBUG"
_SAMPLE_LIMIT = 30


def ner_debug_enabled() -> bool:
    if os.environ.get(_DEBUG_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    try:
        from app.core.config import get_settings

        return bool(get_settings().deid_ner_debug)
    except Exception:
        return False


@contextmanager
def timed_ms() -> Iterator[list[float]]:
    bucket = [0.0]
    started = time.perf_counter()
    try:
        yield bucket
    finally:
        bucket[0] = (time.perf_counter() - started) * 1000.0


def log_ner_metrics(
    *,
    language: str,
    provider: str,
    load_ms: float | None,
    inference_ms: float | None,
    characters: int,
    tokens: int | None,
    raw_predictions: int,
    candidates: int,
    status: str | None = None,
    model_id: str | None = None,
    provider_class: str | None = None,
    chunks: int | None = None,
    accept: int | None = None,
    review: int | None = None,
    ignore: int | None = None,
    survived_merge: int | None = None,
    predict_called: bool | None = None,
    model_loaded: bool | None = None,
) -> None:
    logger.info(
        "[local-ner] mode=LOCAL_CONTEXT language=%s provider=%s model=%s "
        "status=%s chunks=%s raw_entities=%s candidates=%s accept=%s review=%s "
        "ignore=%s survived_merge=%s predict_called=%s model_loaded=%s "
        "load_ms=%s inference_ms=%s chars=%s tokens=%s",
        language,
        provider_class or provider,
        model_id or "-",
        status or "-",
        chunks if chunks is not None else "-",
        raw_predictions,
        candidates,
        accept if accept is not None else "-",
        review if review is not None else "-",
        ignore if ignore is not None else "-",
        survived_merge if survived_merge is not None else "-",
        _yes_no(predict_called),
        _yes_no(model_loaded),
        None if load_ms is None else round(load_ms, 1),
        None if inference_ms is None else round(inference_ms, 1),
        characters,
        tokens,
    )


def log_ner_run_metrics(metrics: LocalNERMetrics, *, language: str, status: str) -> None:
    log_ner_metrics(
        language=language,
        provider=metrics.provider_class or "-",
        load_ms=metrics.load_ms,
        inference_ms=metrics.inference_ms,
        characters=metrics.characters,
        tokens=metrics.tokens,
        raw_predictions=metrics.raw_prediction_count,
        candidates=metrics.candidate_count,
        status=status,
        model_id=None,
        provider_class=metrics.provider_class,
        chunks=metrics.chunk_count,
        accept=metrics.accept_count,
        review=metrics.review_count,
        ignore=metrics.ignore_count,
        survived_merge=metrics.survived_merge_count,
        predict_called=metrics.predict_called,
        model_loaded=metrics.model_loaded,
    )


def log_ner_status(
    *,
    language: str | None,
    provider: str | None,
    provider_class: str | None,
    model_id: str | None,
    status: str,
    error_code: str | None = None,
    predict_called: bool = False,
    model_loaded: bool = False,
) -> None:
    logger.warning(
        "[local-ner] mode=LOCAL_CONTEXT language=%s provider=%s model=%s "
        "status=%s error=%s predict_called=%s model_loaded=%s",
        language or "-",
        provider_class or provider or "-",
        model_id or "-",
        status,
        error_code or "-",
        _yes_no(predict_called),
        _yes_no(model_loaded),
    )


def log_ner_samples(predictions, *, limit: int = _SAMPLE_LIMIT) -> None:
    """Bounded development samples. Gated by DEID_NER_DEBUG. Not a UI surface."""
    if not ner_debug_enabled() or not predictions:
        return
    shown = list(predictions)[:limit]
    for index, item in enumerate(shown, start=1):
        logger.info(
            "[local-ner-sample] %s/%s text=%r label=%s start=%s end=%s",
            index,
            min(len(predictions), limit),
            item.text,
            item.label,
            item.start,
            item.end,
        )


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "-"
    return "YES" if value else "NO"
