"""
Minimal evaluation harness for rule-based detection.

Usage:
    python evaluation/evaluate_rules.py

Output:
    Precision, recall, F1 per category and overall.
    Fails if precision drops below threshold (for CI).
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.detectors.registry import PageText, run_detectors
from app.detectors.structural import run_structural_detectors
from app.domain.models import EntityType


CORPUS_PATH = Path(__file__).parent / "test_corpus.jsonl"
PRECISION_THRESHOLD = 0.75  # CI fails if precision < 75%
# Overall recall threshold is set to 50% for RULES_ONLY evaluation because:
# - Deterministic rules can only detect entities with clear syntactic patterns
#   (NATIONAL_ID, IBAN, EMAIL, PHONE, etc.) or legal role context (names)
# - NER-dependent categories (PERSON_NAME without context, LOCATION, DATE, etc.)
#   require LOCAL_CONTEXT mode with NER models
# - Critical high-recall gates (95%) are applied per-category for pattern-based types
RECALL_THRESHOLD = 0.50  # CI fails if overall recall < 50%

# Critical categories that must have high recall (PII leakage risk)
# NOTE: PERSON_NAME is excluded because isolated person names without legal role
# context require NER detection. The RULES_ONLY benchmark measures deterministic
# pattern-based detection, not NER capabilities. PERSON_NAME recall is better
# evaluated in LOCAL_CONTEXT mode which includes NER.
# CREDIT_CARD is excluded because partial card references (last 4 digits) cannot
# be validated with Luhn checksum. Full credit card detection with Luhn is tested.
CRITICAL_CATEGORIES = {
    "NATIONAL_ID",
    "IBAN",
    "EMAIL",
    "PHONE_NUMBER",
}
CRITICAL_RECALL_THRESHOLD = 0.95  # 95% recall for critical PII categories


def load_corpus() -> list[dict[str, Any]]:
    """Load JSONL test corpus."""
    with CORPUS_PATH.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def normalize_entity(entity: dict[str, Any]) -> tuple[int, int, str]:
    """(start, end, type) tuple for deduplication."""
    return (entity["start"], entity["end"], entity["type"])


def overlap_iou(pred_start: int, pred_end: int, gold_start: int, gold_end: int) -> float:
    """Calculate intersection-over-union for two spans."""
    intersection = max(0, min(pred_end, gold_end) - max(pred_start, gold_start))
    union = max(pred_end, gold_end) - min(pred_start, gold_start)
    return intersection / union if union > 0 else 0.0


def match_entities_with_overlap(
    predicted: set[tuple[int, int, str]],
    gold: set[tuple[int, int, str]],
    iou_threshold: float = 0.5,
) -> tuple[int, int, int]:
    """Match predicted and gold entities with IoU overlap.
    
    Returns: (true_positives, false_positives, false_negatives)
    """
    pred_list = list(predicted)
    gold_list = list(gold)
    matched_gold = set()
    matched_pred = set()
    
    # Find matches with IoU >= threshold
    for i, (p_start, p_end, p_type) in enumerate(pred_list):
        best_match = None
        best_iou = iou_threshold
        
        for j, (g_start, g_end, g_type) in enumerate(gold_list):
            if p_type != g_type:
                continue
            if j in matched_gold:
                continue
            
            iou = overlap_iou(p_start, p_end, g_start, g_end)
            if iou > best_iou:
                best_iou = iou
                best_match = j
        
        if best_match is not None:
            matched_pred.add(i)
            matched_gold.add(best_match)
    
    tp = len(matched_pred)
    fp = len(pred_list) - tp
    fn = len(gold_list) - len(matched_gold)
    
    return tp, fp, fn


async def detect_rules_only(text: str) -> set[tuple[int, int, str]]:
    """Run deterministic + structural detectors, return normalized entities."""
    pages = [PageText(page=0, text=text, document_offset=0)]
    deterministic, _ = run_detectors(pages)
    structural = run_structural_detectors(pages)
    all_entities = list(deterministic) + list(structural)
    return {(e.start, e.end, e.type.value) for e in all_entities}


def compute_metrics(
    predicted: set[tuple[int, int, str]],
    gold: set[tuple[int, int, str]],
) -> dict[str, float]:
    """Compute precision, recall, F1."""
    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


async def evaluate() -> dict[str, Any]:
    """Evaluate rule-based detection on corpus with overlap-based matching."""
    corpus = load_corpus()
    category_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )
    overall_tp, overall_fp, overall_fn = 0, 0, 0

    for doc in corpus:
        text = doc["text"]
        gold_entities = {normalize_entity(e) for e in doc["gold_entities"]}
        predicted_entities = await detect_rules_only(text)

        # Use overlap-based matching instead of exact match
        tp, fp, fn = match_entities_with_overlap(predicted_entities, gold_entities)
        overall_tp += tp
        overall_fp += fp
        overall_fn += fn

        # Per-category stats with overlap matching
        # Group by category first
        pred_by_cat: dict[str, set[tuple[int, int, str]]] = defaultdict(set)
        gold_by_cat: dict[str, set[tuple[int, int, str]]] = defaultdict(set)
        
        for entity in predicted_entities:
            pred_by_cat[entity[2]].add(entity)
        for entity in gold_entities:
            gold_by_cat[entity[2]].add(entity)
        
        # Match per category
        all_categories = set(pred_by_cat.keys()) | set(gold_by_cat.keys())
        for category in all_categories:
            cat_tp, cat_fp, cat_fn = match_entities_with_overlap(
                pred_by_cat[category], gold_by_cat[category]
            )
            category_stats[category]["tp"] += cat_tp
            category_stats[category]["fp"] += cat_fp
            category_stats[category]["fn"] += cat_fn

    # Compute per-category metrics
    category_metrics = {}
    for category, stats in category_stats.items():
        tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        category_metrics[category] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

    # Overall metrics
    overall_precision = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) > 0 else 0.0
    overall_recall = overall_tp / (overall_tp + overall_fn) if (overall_tp + overall_fn) > 0 else 0.0
    overall_f1 = (2 * overall_precision * overall_recall / (overall_precision + overall_recall)) if (overall_precision + overall_recall) > 0 else 0.0

    return {
        "corpus_size": len(corpus),
        "overall": {
            "precision": overall_precision,
            "recall": overall_recall,
            "f1": overall_f1,
            "tp": overall_tp,
            "fp": overall_fp,
            "fn": overall_fn,
        },
        "by_category": category_metrics,
    }


def print_results(results: dict[str, Any]) -> bool:
    """Pretty-print evaluation results."""
    print("\n" + "=" * 60)
    print("RULES-ONLY DETECTION EVALUATION")
    print("=" * 60)
    print(f"Corpus size: {results['corpus_size']} documents\n")

    overall = results["overall"]
    print("OVERALL METRICS:")
    print(f"  Precision: {overall['precision']:.2%}")
    print(f"  Recall:    {overall['recall']:.2%}")
    print(f"  F1 Score:  {overall['f1']:.2%}")
    print(f"  TP: {overall['tp']}, FP: {overall['fp']}, FN: {overall['fn']}\n")

    print("PER-CATEGORY METRICS:")
    by_cat = results["by_category"]
    for category in sorted(by_cat.keys()):
        metrics = by_cat[category]
        print(f"\n  {category}:")
        print(f"    Precision: {metrics['precision']:.2%}")
        print(f"    Recall:    {metrics['recall']:.2%}")
        print(f"    F1:        {metrics['f1']:.2%}")
        print(f"    TP: {metrics['tp']}, FP: {metrics['fp']}, FN: {metrics['fn']}")

    print("\n" + "=" * 60)

    # CI threshold checks
    failures = []
    
    # Check overall precision
    if overall["precision"] < PRECISION_THRESHOLD:
        failures.append(f"Overall precision ({overall['precision']:.2%}) < threshold ({PRECISION_THRESHOLD:.0%})")
    else:
        print(f"✓ PASS: Overall precision ({overall['precision']:.2%}) >= {PRECISION_THRESHOLD:.0%}")
    
    # Check overall recall (MORE CRITICAL for redaction tool)
    if overall["recall"] < RECALL_THRESHOLD:
        failures.append(f"Overall recall ({overall['recall']:.2%}) < threshold ({RECALL_THRESHOLD:.0%})")
    else:
        print(f"✓ PASS: Overall recall ({overall['recall']:.2%}) >= {RECALL_THRESHOLD:.0%}")
    
    # Check critical category recall
    by_cat = results["by_category"]
    for category in CRITICAL_CATEGORIES:
        if category in by_cat:
            cat_recall = by_cat[category]["recall"]
            if cat_recall < CRITICAL_RECALL_THRESHOLD:
                failures.append(
                    f"{category} recall ({cat_recall:.2%}) < critical threshold ({CRITICAL_RECALL_THRESHOLD:.0%})"
                )
            else:
                print(f"✓ PASS: {category} recall ({cat_recall:.2%}) >= {CRITICAL_RECALL_THRESHOLD:.0%}")
    
    if failures:
        print("\n" + "=" * 60)
        print("❌ FAILED CHECKS:")
        for failure in failures:
            print(f"  - {failure}")
        print("\nRule changes may cause PII leakage (low recall) or too many false positives!")
        return False
    else:
        print("\n" + "=" * 60)
        print("✅ ALL CHECKS PASSED")
        return True


async def main() -> None:
    """Run evaluation."""
    results = await evaluate()
    passed = print_results(results)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
