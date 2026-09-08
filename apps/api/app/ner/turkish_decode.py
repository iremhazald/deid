"""BIO / subword aggregation matching Hugging Face ``aggregation_strategy="simple"``.

Rules (same as ``transformers.pipelines.token_classification``):

1. Softmax over the 7-class logits, then per-token argmax.
2. Special tokens (CLS / SEP / PAD) are dropped via ``special_tokens_mask``.
3. Tokens with empty or missing offset mappings are dropped (no fuzzy search).
4. Adjacent tokens merge when the current tag equals the previous tag and the
   current BIO prefix is not ``B-``. Two consecutive ``B-PER`` spans stay
   separate. ``O`` tokens stay in the stream so they break merges.
5. Entity score is the mean of the winning-class token probabilities.
6. ``O`` groups are discarded after merge. ``##`` pieces are never exposed:
   the surface is always the source slice ``text[start:end]``.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

_IGNORE_LABELS = frozenset({"O"})


def softmax_logits(logits: np.ndarray) -> np.ndarray:
    maxes = np.max(logits, axis=-1, keepdims=True)
    shifted = np.exp(logits - maxes)
    return shifted / shifted.sum(axis=-1, keepdims=True)


def _get_tag(entity_name: str) -> tuple[str, str]:
    if entity_name.startswith("B-"):
        return "B", entity_name[2:]
    if entity_name.startswith("I-"):
        return "I", entity_name[2:]
    return "I", entity_name


def _group_sub_entities(entities: list[dict[str, Any]]) -> dict[str, Any]:
    label = str(entities[0]["entity"]).split("-", 1)[-1]
    scores = [float(item["score"]) for item in entities]
    return {
        "entity_group": label,
        "score": float(np.mean(scores)),
        "start": int(entities[0]["start"]),
        "end": int(entities[-1]["end"]),
    }


def group_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not entities:
        return []
    grouped: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for entity in entities:
        if not current:
            current.append(entity)
            continue
        bi, tag = _get_tag(str(entity["entity"]))
        _last_bi, last_tag = _get_tag(str(current[-1]["entity"]))
        if tag == last_tag and bi != "B":
            current.append(entity)
            continue
        grouped.append(_group_sub_entities(current))
        current = [entity]
    if current:
        grouped.append(_group_sub_entities(current))
    return grouped


def decode_token_classification(
    text: str,
    *,
    scores: np.ndarray,
    offset_mapping: Sequence[tuple[int, int] | Sequence[int]],
    special_tokens_mask: Sequence[int] | np.ndarray,
    id2label: Mapping[int, str],
) -> list[dict[str, Any]]:
    """Turn per-token scores into pipeline-shaped entity dicts."""
    if scores.ndim != 2:
        raise ValueError("scores must have shape [sequence, num_labels]")
    if len(offset_mapping) != scores.shape[0] or len(special_tokens_mask) != scores.shape[0]:
        raise ValueError("offset_mapping, special_tokens_mask, and scores length must match")

    raw: list[dict[str, Any]] = []
    for index, token_scores in enumerate(scores):
        if int(special_tokens_mask[index]):
            continue
        start_end = offset_mapping[index]
        try:
            start = int(start_end[0])
            end = int(start_end[1])
        except (TypeError, ValueError, IndexError):
            continue
        if end <= start or start < 0 or end > len(text):
            continue
        entity_idx = int(np.argmax(token_scores))
        label = id2label.get(entity_idx)
        if label is None:
            continue
        raw.append(
            {
                "entity": str(label),
                "score": float(token_scores[entity_idx]),
                "start": start,
                "end": end,
            }
        )

    grouped = group_entities(raw)
    return [
        item
        for item in grouped
        if item["entity_group"] not in _IGNORE_LABELS
    ]
