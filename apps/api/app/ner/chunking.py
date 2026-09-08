"""Offset-preserving chunking for long pages.

Source offsets stay in the original page string. Chunks never rewrite
Unicode. Overlapping predictions are merged conservatively.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from app.ner.models import NERPrediction


@dataclass(frozen=True)
class TextChunk:
    text: str
    origin: int


def iter_char_chunks(text: str, *, max_chars: int, overlap: int) -> Iterator[TextChunk]:
    if max_chars <= 0:
        yield TextChunk(text=text, origin=0)
        return
    if len(text) <= max_chars:
        yield TextChunk(text=text, origin=0)
        return
    step = max(1, max_chars - max(0, overlap))
    start = 0
    length = len(text)
    while start < length:
        end = min(length, start + max_chars)
        if end < length:
            boundary = text.rfind(" ", start + max(1, max_chars // 2), end)
            if boundary > start:
                end = boundary
        yield TextChunk(text=text[start:end], origin=start)
        if end >= length:
            break
        start = max(start + 1, end - max(0, overlap))


def remap_prediction(prediction: NERPrediction, origin: int, source: str) -> NERPrediction | None:
    start = origin + prediction.start
    end = origin + prediction.end
    if start < 0 or end > len(source) or end <= start:
        return None
    surface = source[start:end]
    if not surface or surface != prediction.text:
        if prediction.text and source[start:end] != prediction.text:
            # Prefer the source slice when the model decoded a slightly
            # different subword surface but reported usable offsets.
            if _offsets_look_safe(source, start, end, prediction.text):
                surface = source[start:end]
            else:
                return None
    return NERPrediction(
        start=start,
        end=end,
        text=surface,
        label=prediction.label,
        score=prediction.score,
        language=prediction.language,
        provider=prediction.provider,
        model_id=prediction.model_id,
    )


def _offsets_look_safe(source: str, start: int, end: int, reported: str) -> bool:
    surface = source[start:end]
    if not surface.strip():
        return False
    compact_surface = "".join(surface.split())
    compact_reported = "".join(reported.split())
    return compact_surface == compact_reported or compact_reported in compact_surface


def dedupe_predictions(predictions: list[NERPrediction]) -> list[NERPrediction]:
    """Keep the longer span (then higher score) when two NER hits overlap."""
    ordered = sorted(
        predictions,
        key=lambda item: (
            item.end - item.start,
            item.score if item.score is not None else 0.0,
            -item.start,
        ),
        reverse=True,
    )
    kept: list[NERPrediction] = []
    for item in ordered:
        if any(item.start < other.end and other.start < item.end for other in kept):
            continue
        kept.append(item)
    return sorted(kept, key=lambda item: (item.start, item.end))


def predict_chunked(
    text: str,
    predict_fn: Callable[[str], list[NERPrediction]],
    *,
    max_chars: int,
    overlap: int,
) -> list[NERPrediction]:
    collected: list[NERPrediction] = []
    for chunk in iter_char_chunks(text, max_chars=max_chars, overlap=overlap):
        for raw in predict_fn(chunk.text):
            remapped = remap_prediction(raw, chunk.origin, text)
            if remapped is not None:
                collected.append(remapped)
    return dedupe_predictions(collected)
