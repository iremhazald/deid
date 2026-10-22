"""
Rules-only evaluation harness for the legacy detector list.

This command is what CI gates. It is not the product pipeline: structural
label hits are appended after ``run_detectors`` and are not passed through
the product merge. On the Turkish gold set that merge drops five false
positives and does not change recall.

Usage:
    python evaluation/evaluate_rules.py
    python evaluation/evaluate_rules.py --output evaluation/runs/custom.json
    python evaluation/evaluate_rules.py --compare before.json after.json

A prediction matches a gold span of the same type when overlap IoU is
at least 0.5. Each run writes a JSON result file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.detectors.registry import PageText, run_detectors
from app.detectors.structural import run_structural_detectors
from app.domain.models import EntityType


CORPUS_PATH = Path(__file__).parent / "test_corpus.jsonl"
RUNS_DIR = Path(__file__).parent / "runs"
IOU_THRESHOLD = 0.5
HARNESS_NAME = "legacy_rules"
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

# Gold may use every EntityType. A label that is not in the enum fails below.
# Political opinion is not an EntityType.
OUT_OF_SCOPE_TYPES: frozenset[str] = frozenset()


def load_corpus() -> list[dict[str, Any]]:
    """Load JSONL test corpus."""
    with CORPUS_PATH.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def corpus_integrity_errors(corpus: list[dict[str, Any]]) -> list[str]:
    """Reject gold rows whose span or label cannot be scored."""
    allowed = {item.value for item in EntityType}
    errors: list[str] = []
    for doc in corpus:
        doc_id = str(doc.get("id", "?"))
        text = doc.get("text")
        if not isinstance(text, str):
            errors.append(f"{doc_id}: text is missing")
            continue
        entities = doc.get("gold_entities")
        if not isinstance(entities, list):
            errors.append(f"{doc_id}: gold_entities is missing")
            continue
        for entity in entities:
            label = entity.get("type")
            value = entity.get("text")
            start = entity.get("start")
            end = entity.get("end")
            if not isinstance(label, str):
                errors.append(f"{doc_id}: a gold label is missing")
                continue
            if label not in allowed:
                errors.append(f"{doc_id}: {label} is not an EntityType")
                continue
            if label in OUT_OF_SCOPE_TYPES:
                errors.append(f"{doc_id}: {label} is outside the scope list")
                continue
            if not isinstance(value, str) or not isinstance(start, int) or not isinstance(end, int):
                errors.append(f"{doc_id}: {label} is missing text or integer offsets")
                continue
            if start < 0 or end > len(text) or start > end:
                errors.append(f"{doc_id}: {label} span {start}:{end} is outside the text")
                continue
            if text[start:end] != value:
                errors.append(
                    f"{doc_id}: {label} {start}:{end} does not match the gold text"
                )
    return errors


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
    iou_threshold: float = IOU_THRESHOLD,
) -> tuple[int, int, int]:
    """Match predicted and gold entities of the same type.

    A pair matches when IoU is at least ``iou_threshold``. Each prediction
    keeps the unmatched gold span with the greatest IoU.

    Returns: (true_positives, false_positives, false_negatives)
    """
    pred_list = list(predicted)
    gold_list = list(gold)
    matched_gold = set()
    matched_pred = set()

    for i, (p_start, p_end, p_type) in enumerate(pred_list):
        best_match = None
        best_iou = -1.0

        for j, (g_start, g_end, g_type) in enumerate(gold_list):
            if p_type != g_type:
                continue
            if j in matched_gold:
                continue

            iou = overlap_iou(p_start, p_end, g_start, g_end)
            if iou >= iou_threshold and iou > best_iou:
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


async def evaluate() -> dict[str, Any]:
    """Evaluate rule-based detection on corpus with overlap-based matching."""
    corpus = load_corpus()
    integrity = corpus_integrity_errors(corpus)
    if integrity:
        print("GOLD INTEGRITY FAILED:")
        for error in integrity:
            print(f"  - {error}")
        raise SystemExit(1)
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


def gate_failures(results: dict[str, Any]) -> list[str]:
    """Return CI gate failures. Thresholds are unchanged."""
    failures = []
    overall = results["overall"]
    if overall["precision"] < PRECISION_THRESHOLD:
        failures.append(
            f"Overall precision ({overall['precision']:.2%}) < threshold ({PRECISION_THRESHOLD:.0%})"
        )
    if overall["recall"] < RECALL_THRESHOLD:
        failures.append(
            f"Overall recall ({overall['recall']:.2%}) < threshold ({RECALL_THRESHOLD:.0%})"
        )
    by_cat = results["by_category"]
    for category in sorted(CRITICAL_CATEGORIES):
        if category not in by_cat:
            continue
        cat_recall = by_cat[category]["recall"]
        if cat_recall < CRITICAL_RECALL_THRESHOLD:
            failures.append(
                f"{category} recall ({cat_recall:.2%}) < critical threshold ({CRITICAL_RECALL_THRESHOLD:.0%})"
            )
    return failures


def print_results(results: dict[str, Any]) -> bool:
    """Pretty-print evaluation results. Status words are ASCII for Windows consoles."""
    print("\n" + "=" * 60)
    print("RULES-ONLY DETECTION EVALUATION")
    print("Path: legacy detectors plus unmerged structural hits")
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

    failures = gate_failures(results)
    if overall["precision"] >= PRECISION_THRESHOLD:
        print(f"PASS: Overall precision ({overall['precision']:.2%}) >= {PRECISION_THRESHOLD:.0%}")
    if overall["recall"] >= RECALL_THRESHOLD:
        print(f"PASS: Overall recall ({overall['recall']:.2%}) >= {RECALL_THRESHOLD:.0%}")
    for category in sorted(CRITICAL_CATEGORIES):
        if category not in by_cat:
            continue
        cat_recall = by_cat[category]["recall"]
        if cat_recall >= CRITICAL_RECALL_THRESHOLD:
            print(f"PASS: {category} recall ({cat_recall:.2%}) >= {CRITICAL_RECALL_THRESHOLD:.0%}")

    if failures:
        print("\n" + "=" * 60)
        print("FAILED CHECKS:")
        for failure in failures:
            print(f"  - {failure}")
        print("\nRule changes may cause PII leakage (low recall) or too many false positives!")
        return False
    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED")
    return True


def build_report(results: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    """JSON snapshot of one harness run. Later slices can be added beside these keys."""
    return {
        "harness": HARNESS_NAME,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "iou_threshold": IOU_THRESHOLD,
        "iou_comparison": ">=",
        "corpus_size": results["corpus_size"],
        "overall": results["overall"],
        "by_category": results["by_category"],
        "gates": {
            "precision_threshold": PRECISION_THRESHOLD,
            "recall_threshold": RECALL_THRESHOLD,
            "critical_recall_threshold": CRITICAL_RECALL_THRESHOLD,
            "critical_categories": sorted(CRITICAL_CATEGORIES),
            "passed": not failures,
            "failures": failures,
        },
    }


def default_results_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RUNS_DIR / f"{stamp}-{HARNESS_NAME}.json"


def save_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return path


def _load_report(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "overall" not in payload or "by_category" not in payload:
        raise SystemExit(f"Not an evaluation report: {path}")
    return payload


def _signed_points(after: float, before: float) -> str:
    delta = (after - before) * 100
    return f"{delta:+.2f} pp"


def _print_metric_row(label: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> None:
    if before is None or after is None:
        present = after or before or {}
        side = "after only" if before is None else "before only"
        print(
            f"  {label}: {side}  P {present.get('precision', 0):.2%}  "
            f"R {present.get('recall', 0):.2%}  F1 {present.get('f1', 0):.2%}  "
            f"TP {present.get('tp', 0)} FP {present.get('fp', 0)} FN {present.get('fn', 0)}"
        )
        return
    print(
        f"  {label}: P {before['precision']:.2%} -> {after['precision']:.2%} ({_signed_points(after['precision'], before['precision'])})"
        f"  R {before['recall']:.2%} -> {after['recall']:.2%} ({_signed_points(after['recall'], before['recall'])})"
        f"  F1 {before['f1']:.2%} -> {after['f1']:.2%} ({_signed_points(after['f1'], before['f1'])})"
    )
    print(
        f"    TP {before['tp']} -> {after['tp']} ({after['tp'] - before['tp']:+d})"
        f"  FP {before['fp']} -> {after['fp']} ({after['fp'] - before['fp']:+d})"
        f"  FN {before['fn']} -> {after['fn']} ({after['fn'] - before['fn']:+d})"
    )


def compare_reports(before_path: Path, after_path: Path) -> None:
    """Print before/after deltas. This does not apply CI gates."""
    before = _load_report(before_path)
    after = _load_report(after_path)
    print("\n" + "=" * 60)
    print("EVALUATION COMPARISON")
    print("=" * 60)
    print(f"Before: {before_path}")
    print(f"After:  {after_path}")
    before_harness = before.get("harness", "unknown")
    after_harness = after.get("harness", "unknown")
    if before_harness != after_harness:
        print(f"Harness: {before_harness} -> {after_harness}")
    print()
    _print_metric_row("OVERALL", before.get("overall"), after.get("overall"))
    print("\nPER-CATEGORY DELTAS:")
    categories = sorted(set(before.get("by_category", {})) | set(after.get("by_category", {})))
    changes = 0
    for category in categories:
        left = before.get("by_category", {}).get(category)
        right = after.get("by_category", {}).get(category)
        if left is not None and right is not None and left == right:
            continue
        changes += 1
        _print_metric_row(category, left, right)
    if changes == 0:
        print("  (no category changes)")
    before_gates = (before.get("gates") or {}).get("passed")
    after_gates = (after.get("gates") or {}).get("passed")
    print(f"\nGates passed: {before_gates} -> {after_gates}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate legacy rules-only detection.")
    parser.add_argument(
        "--output",
        type=Path,
        help="JSON path for this run. Default: evaluation/runs/<utc>-legacy_rules.json",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        type=Path,
        help="Print metric deltas between two saved runs and exit.",
    )
    return parser.parse_args(argv)


async def run_evaluation(output: Path | None) -> int:
    results = await evaluate()
    failures = gate_failures(results)
    passed = print_results(results)
    report = build_report(results, failures)
    path = save_report(report, output or default_results_path())
    print(f"Saved: {path}")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> None:
    _configure_stdio()
    args = parse_args(argv)
    if args.compare:
        compare_reports(args.compare[0], args.compare[1])
        return
    code = asyncio.run(run_evaluation(args.output))
    if code:
        raise SystemExit(code)


def _configure_stdio() -> None:
    """Keep console output readable when the Windows code page is not UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (OSError, ValueError):
            continue


if __name__ == "__main__":
    main()
