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
at least 0.5. The CI gates use that strict match on Turkish documents.
A second, ungated match treats every person-name type as one family.
English documents are reported and are not gated. The same run also
reports both matches by corpus split, for each language this path scores.
Each run writes a JSON result file. The legacy detector list does not
include the English pack, so this command does not score English documents.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
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
BOUNDARY_IOU = 0.8
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

# Strict gates stay on these types. The family match collapses them to one type.
PERSON_NAME_TYPES = frozenset(
    {
        "PERSON_NAME",
        "FIRST_NAME",
        "LAST_NAME",
        "ALIAS",
        "CLAIMANT_NAME",
        "DEFENDANT_NAME",
        "LAWYER_NAME",
        "JUDGE_NAME",
        "PROSECUTOR_NAME",
        "COURT_CLERK_NAME",
        "VICTIM_NAME",
        "COMPLAINANT_NAME",
        "SUSPECT_NAME",
        "ACCUSED_NAME",
        "COMPLAINANT_ACCUSED_NAME",
        "INTERVENOR_NAME",
        "LEGAL_REPRESENTATIVE_NAME",
        "MEDIATOR_NAME",
        "INTERPRETER_NAME",
        "ENFORCEMENT_OFFICER_NAME",
        "NOTARY_NAME",
        "ARBITRATOR_NAME",
        "WITNESS_NAME",
        "EXPERT_NAME",
    }
)
PERSON_FAMILY = "PERSON"

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


def _greedy_matches(
    predicted: set[tuple[int, int, str]],
    gold: set[tuple[int, int, str]],
    iou_threshold: float = IOU_THRESHOLD,
) -> list[tuple[tuple[int, int, str], tuple[int, int, str], float]]:
    """Same-type pairs. Each prediction keeps its best unmatched gold span."""
    pred_list = list(predicted)
    gold_list = list(gold)
    matched_gold: set[int] = set()
    pairs: list[tuple[tuple[int, int, str], tuple[int, int, str], float]] = []

    for pred in pred_list:
        best_index: int | None = None
        best_iou = -1.0
        best_gold: tuple[int, int, str] | None = None
        for index, gold_span in enumerate(gold_list):
            if pred[2] != gold_span[2] or index in matched_gold:
                continue
            iou = overlap_iou(pred[0], pred[1], gold_span[0], gold_span[1])
            if iou >= iou_threshold and iou > best_iou:
                best_iou = iou
                best_index = index
                best_gold = gold_span
        if best_index is not None and best_gold is not None:
            matched_gold.add(best_index)
            pairs.append((pred, best_gold, best_iou))
    return pairs


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
    matched = len(_greedy_matches(predicted, gold, iou_threshold))
    return matched, len(predicted) - matched, len(gold) - matched


async def detect_rules_only(text: str) -> set[tuple[int, int, str]]:
    """Run deterministic + structural detectors, return normalized entities."""
    pages = [PageText(page=0, text=text, document_offset=0)]
    deterministic, _ = run_detectors(pages)
    structural = run_structural_detectors(pages)
    all_entities = list(deterministic) + list(structural)
    return {(e.start, e.end, e.type.value) for e in all_entities}


def _metrics_from_counts(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def boundary_report(
    detected: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]],
) -> dict[str, Any]:
    """Strict matches whose IoU is below 0.8. This does not change the 0.5 rule."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    low: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for doc, predicted, gold in detected:
        language = str(doc.get("language", "tr"))
        text = str(doc.get("text", ""))
        for pred, gold_span, iou in _greedy_matches(predicted, gold):
            label = gold_span[2]
            counts[language][label] += 1
            if iou >= BOUNDARY_IOU:
                continue
            low[language][label].append(
                {
                    "document": doc.get("id"),
                    "gold": text[gold_span[0] : gold_span[1]],
                    "gold_span": [gold_span[0], gold_span[1]],
                    "predicted": text[pred[0] : pred[1]],
                    "predicted_span": [pred[0], pred[1]],
                    "iou": round(iou, 3),
                }
            )
    report: dict[str, Any] = {}
    for language in sorted(set(counts) | set(low)):
        categories = sorted(set(counts[language]) | set(low[language]))
        report[language] = {
            category: {
                "matches": counts[language][category],
                "below": len(low[language][category]),
                "items": sorted(
                    low[language][category],
                    key=lambda row: (
                        str(row["document"]),
                        row["gold_span"][0],
                        row["predicted_span"][0],
                    ),
                ),
            }
            for category in categories
        }
    return report


def _as_family(entities: set[tuple[int, int, str]]) -> set[tuple[int, int, str]]:
    """Collapse person-name types so a wrong role is not a miss."""
    return {(start, end, PERSON_FAMILY if label in PERSON_NAME_TYPES else label) for start, end, label in entities}


def _score_pairs(
    pairs: list[tuple[set[tuple[int, int, str]], set[tuple[int, int, str]]]],
) -> dict[str, Any]:
    category_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    overall_tp, overall_fp, overall_fn = 0, 0, 0
    for predicted, gold in pairs:
        tp, fp, fn = match_entities_with_overlap(predicted, gold)
        overall_tp += tp
        overall_fp += fp
        overall_fn += fn
        pred_by_cat: dict[str, set[tuple[int, int, str]]] = defaultdict(set)
        gold_by_cat: dict[str, set[tuple[int, int, str]]] = defaultdict(set)
        for entity in predicted:
            pred_by_cat[entity[2]].add(entity)
        for entity in gold:
            gold_by_cat[entity[2]].add(entity)
        for category in set(pred_by_cat) | set(gold_by_cat):
            cat_tp, cat_fp, cat_fn = match_entities_with_overlap(
                pred_by_cat[category], gold_by_cat[category]
            )
            category_stats[category]["tp"] += cat_tp
            category_stats[category]["fp"] += cat_fp
            category_stats[category]["fn"] += cat_fn
    by_category = {
        category: _metrics_from_counts(stats["tp"], stats["fp"], stats["fn"])
        for category, stats in category_stats.items()
    }
    return {
        "overall": _metrics_from_counts(overall_tp, overall_fp, overall_fn),
        "by_category": by_category,
    }


async def evaluate() -> dict[str, Any]:
    """Evaluate rule-based detection. Gates use strict Turkish matches."""
    corpus = load_corpus()
    integrity = corpus_integrity_errors(corpus)
    if integrity:
        print("GOLD INTEGRITY FAILED:")
        for error in integrity:
            print(f"  - {error}")
        raise SystemExit(1)

    detected: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]] = []
    for doc in corpus:
        gold_entities = {normalize_entity(entity) for entity in doc["gold_entities"]}
        if doc.get("language") == "en":
            detected.append((doc, set(), set()))
            continue
        predicted_entities = await detect_rules_only(doc["text"])
        detected.append((doc, predicted_entities, gold_entities))

    def pairs_for(language: str, *, family: bool) -> list[tuple[set, set]]:
        selected = []
        for doc, predicted, gold in detected:
            if doc.get("language", "tr") != language:
                continue
            if family:
                predicted = _as_family(predicted)
                gold = _as_family(gold)
            selected.append((predicted, gold))
        return selected

    by_language: dict[str, Any] = {}
    languages = sorted({str(doc.get("language", "tr")) for doc, _, _ in detected})
    for language in languages:
        documents = [doc for doc, _, _ in detected if doc.get("language", "tr") == language]
        if language == "en":
            # The legacy detector list has no English pack. A score here would
            # look like an English result and is not one.
            by_language[language] = {
                "corpus_size": len(documents),
                "detectors_loaded": False,
            }
            continue
        by_language[language] = {
            "corpus_size": len(documents),
            "strict": _score_pairs(pairs_for(language, family=False)),
            "person_family": _score_pairs(pairs_for(language, family=True)),
        }

    turkish = by_language.get("tr")
    if turkish is None:
        raise SystemExit("GOLD INTEGRITY FAILED:\n  - no Turkish documents to gate")
    turkish_rows = [
        (doc, predicted, gold)
        for doc, predicted, gold in detected
        if doc.get("language", "tr") == "tr"
    ]
    support: dict[str, dict[str, int]] = defaultdict(dict)
    for doc in corpus:
        language = str(doc.get("language", "tr"))
        counts: Counter[str] = Counter(entity["type"] for entity in doc["gold_entities"])
        for label, count in counts.items():
            support[language][label] = support[language].get(label, 0) + count
    for language in support:
        support[language] = dict(sorted(support[language].items()))
    return {
        "corpus_size": turkish["corpus_size"],
        "overall": turkish["strict"]["overall"],
        "by_category": turkish["strict"]["by_category"],
        "by_language": by_language,
        "by_split": by_split_report(
            [row for row in detected if row[0].get("language") != "en"]
        ),
        "by_difficulty": _slice_table(turkish_rows, "difficulty"),
        "by_document_type": _slice_table(turkish_rows, "document_type"),
        "gold_support": dict(support),
        "boundary": boundary_report(detected),
        "path_label": "Path: legacy detectors plus unmerged structural hits",
        "gate_label": "Gates: strict match, Turkish documents",
    }


async def evaluate_product_rules() -> dict[str, Any]:
    """Product rules-only path. English is scored here and is not gated."""
    from app.domain.models import DetectionMode

    corpus = load_corpus()
    integrity = corpus_integrity_errors(corpus)
    if integrity:
        print("GOLD INTEGRITY FAILED:")
        for error in integrity:
            print(f"  - {error}")
        raise SystemExit(1)

    detected: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]] = []
    for doc in corpus:
        gold_entities = {normalize_entity(entity) for entity in doc["gold_entities"]}
        predicted, _analysis = await _product_predictions(
            doc["text"], str(doc.get("language", "tr")), DetectionMode.RULES_ONLY
        )
        detected.append((doc, predicted, gold_entities))

    def pairs_for(language: str, *, family: bool) -> list[tuple[set, set]]:
        selected = []
        for doc, predicted, gold in detected:
            if doc.get("language", "tr") != language:
                continue
            if family:
                predicted = _as_family(predicted)
                gold = _as_family(gold)
            selected.append((predicted, gold))
        return selected

    by_language: dict[str, Any] = {}
    languages = sorted({str(doc.get("language", "tr")) for doc, _, _ in detected})
    for language in languages:
        documents = [doc for doc, _, _ in detected if doc.get("language", "tr") == language]
        by_language[language] = {
            "corpus_size": len(documents),
            "detectors_loaded": True,
            "strict": _score_pairs(pairs_for(language, family=False)),
            "person_family": _score_pairs(pairs_for(language, family=True)),
        }
    turkish = by_language["tr"]
    turkish_rows = [
        (doc, predicted, gold)
        for doc, predicted, gold in detected
        if doc.get("language", "tr") == "tr"
    ]
    support: dict[str, dict[str, int]] = defaultdict(dict)
    for doc in corpus:
        language = str(doc.get("language", "tr"))
        counts: Counter[str] = Counter(entity["type"] for entity in doc["gold_entities"])
        for label, count in counts.items():
            support[language][label] = support[language].get(label, 0) + count
    for language in support:
        support[language] = dict(sorted(support[language].items()))
    return {
        "corpus_size": turkish["corpus_size"],
        "overall": turkish["strict"]["overall"],
        "by_category": turkish["strict"]["by_category"],
        "by_language": by_language,
        "by_split": by_split_report(detected),
        "by_difficulty": _slice_table(turkish_rows, "difficulty"),
        "by_document_type": _slice_table(turkish_rows, "document_type"),
        "gold_support": dict(support),
        "boundary": boundary_report(detected),
        "path_label": "Path: product rules-only",
        "gate_label": "Gates: strict match, Turkish documents",
    }


async def run_product_gate(output: Path | None) -> int:
    results = await evaluate_product_rules()
    failures = gate_failures(results)
    passed = print_results(results)
    report = build_report(results, failures)
    report["harness"] = "product_rules"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = save_report(report, output or (RUNS_DIR / f"{stamp}-product_rules.json"))
    print(f"Saved: {path}")
    return 0 if passed else 1


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


def _print_overall(title: str, scored: dict[str, Any]) -> None:
    overall = scored["overall"]
    print(title)
    print(f"  Precision: {overall['precision']:.2%}")
    print(f"  Recall:    {overall['recall']:.2%}")
    print(f"  F1 Score:  {overall['f1']:.2%}")
    print(f"  TP: {overall['tp']}, FP: {overall['fp']}, FN: {overall['fn']}")


def _print_categories(scored: dict[str, Any]) -> None:
    for category in sorted(scored["by_category"]):
        metrics = scored["by_category"][category]
        print(f"\n  {category}:")
        print(f"    Precision: {metrics['precision']:.2%}")
        print(f"    Recall:    {metrics['recall']:.2%}")
        print(f"    F1:        {metrics['f1']:.2%}")
        print(f"    TP: {metrics['tp']}, FP: {metrics['fp']}, FN: {metrics['fn']}")
        gold = metrics["tp"] + metrics["fn"]
        print(f"    Gold: {gold}")
        if gold < 10:
            print("    low sample")


def _score_row_pairs(
    rows: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]],
    *,
    family: bool,
) -> dict[str, Any]:
    pairs: list[tuple[set[tuple[int, int, str]], set[tuple[int, int, str]]]] = []
    for _doc, predicted, gold in rows:
        if family:
            predicted = _as_family(predicted)
            gold = _as_family(gold)
        pairs.append((predicted, gold))
    return _score_pairs(pairs)


def by_split_report(
    rows: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]],
) -> dict[str, Any]:
    """Strict and person-family scores for each language and corpus split.

    Languages that this path does not score must be left out of ``rows``.
    """
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for doc, predicted, gold in rows:
        language = str(doc.get("language", "tr"))
        split = str(doc.get("split", ""))
        grouped[language][split].append((doc, predicted, gold))
    report: dict[str, Any] = {}
    for language in sorted(grouped):
        report[language] = {}
        for split in sorted(grouped[language]):
            split_rows = grouped[language][split]
            report[language][split] = {
                "documents": len(split_rows),
                "strict": _score_row_pairs(split_rows, family=False),
                "person_family": _score_row_pairs(split_rows, family=True),
            }
    return report


def _slice_table(
    rows: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]],
    key: str,
) -> dict[str, Any]:
    buckets: dict[str, list[tuple[set[tuple[int, int, str]], set[tuple[int, int, str]]]]] = defaultdict(list)
    for doc, predicted, gold in rows:
        buckets[str(doc.get(key, ""))].append((predicted, gold))
    table: dict[str, Any] = {}
    for name, pairs in sorted(buckets.items()):
        scored = _score_pairs(pairs)["overall"]
        gold_count = sum(len(gold) for _predicted, gold in pairs)
        table[name] = {**scored, "gold": gold_count, "low_sample": gold_count < 10}
    return table


def _print_slices(results: dict[str, Any]) -> None:
    for title, key in (("BY DIFFICULTY (Turkish strict)", "by_difficulty"), ("BY DOCUMENT TYPE (Turkish strict)", "by_document_type")):
        table = results.get(key) or {}
        if not table:
            continue
        print("\n" + "=" * 60)
        print(title)
        for name, metrics in table.items():
            flag = "  low sample" if metrics.get("low_sample") else ""
            print(
                f"  {name}: gold {metrics['gold']}  P {metrics['precision']:.2%}  "
                f"R {metrics['recall']:.2%}  F1 {metrics['f1']:.2%}{flag}"
            )


def _print_by_split(results: dict[str, Any]) -> None:
    table = results.get("by_split") or {}
    if not table:
        return
    print("\n" + "=" * 60)
    print("BY SPLIT (strict and person-family)")
    for language in table:
        for split, scored in table[language].items():
            print(f"  {language} / {split} ({scored['documents']} documents)")
            for label, key in (("strict", "strict"), ("person-family", "person_family")):
                overall = scored[key]["overall"]
                gold = overall["tp"] + overall["fn"]
                print(
                    f"    {label}: gold {gold}  P {overall['precision']:.2%}  "
                    f"R {overall['recall']:.2%}  F1 {overall['f1']:.2%}  "
                    f"TP {overall['tp']} FP {overall['fp']} FN {overall['fn']}"
                )


def _print_gold_support(results: dict[str, Any]) -> None:
    support = results.get("gold_support") or {}
    if not support:
        return
    print("\n" + "=" * 60)
    print("GOLD SUPPORT")
    for language, counts in support.items():
        print(f"  {language}:")
        for label, count in counts.items():
            flag = "  low sample" if count < 10 else ""
            print(f"    {label}: {count}{flag}")


def _print_boundary(results: dict[str, Any]) -> None:
    boundary = results.get("boundary") or {}
    print("\n" + "=" * 60)
    print("BOUNDARY (report only; IoU below 0.8; the 0.5 rule and the gates are unchanged)")
    if not boundary:
        print("  none")
        return
    for language, categories in boundary.items():
        print(f"  {language}:")
        for category, scored in categories.items():
            print(f"    {category}: {scored['below']} of {scored['matches']}")
            for item in scored["items"]:
                print(
                    f"      - {item['document']} gold {item['gold_span'][0]}:{item['gold_span'][1]} "
                    f"{item['gold']!r} predicted {item['predicted_span'][0]}:{item['predicted_span'][1]} "
                    f"{item['predicted']!r} IoU {item['iou']:.3f}"
                )


def print_results(results: dict[str, Any]) -> bool:
    """Pretty-print evaluation results. Status words are ASCII for Windows consoles."""
    print("\n" + "=" * 60)
    print("RULES-ONLY DETECTION EVALUATION")
    print(results.get("path_label", "Path: legacy detectors plus unmerged structural hits"))
    print(results.get("gate_label", "Gates: strict match, Turkish documents"))
    print("=" * 60)
    print(f"Corpus size: {results['corpus_size']} Turkish documents\n")

    _print_overall("OVERALL METRICS (strict):", {"overall": results["overall"]})
    print("\nPER-CATEGORY METRICS:")
    _print_categories({"by_category": results["by_category"]})

    by_language = results.get("by_language") or {}
    turkish = by_language.get("tr")
    if turkish is not None:
        print("\n" + "=" * 60)
        print("TURKISH PERSON-FAMILY MATCH (not gated)")
        _print_overall("OVERALL:", turkish["person_family"])
    _print_slices(results)
    _print_by_split(results)
    _print_boundary(results)
    _print_gold_support(results)
    english = by_language.get("en")
    if english is not None and english["corpus_size"]:
        print("\n" + "=" * 60)
        if english.get("detectors_loaded") is False:
            print("English detectors not loaded on this path")
        else:
            print(f"ENGLISH REPORT ONLY ({english['corpus_size']} documents, not gated)")
            _print_overall("STRICT:", english["strict"])
            _print_overall("PERSON-FAMILY:", english["person_family"])
            print("English gate is not armed.")

    print("\n" + "=" * 60)

    failures = gate_failures(results)
    overall = results["overall"]
    by_cat = results["by_category"]
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
        "by_language": results.get("by_language", {}),
        "by_split": results.get("by_split", {}),
        "by_difficulty": results.get("by_difficulty", {}),
        "by_document_type": results.get("by_document_type", {}),
        "gold_support": results.get("gold_support", {}),
        "boundary": results.get("boundary", {}),
        "gate_language": "tr",
        "gate_match": "strict",
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


STRUCTURED_TYPES = frozenset(
    {
        "NATIONAL_ID",
        "IBAN",
        "EMAIL",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "IP_ADDRESS",
        "URL",
        "VEHICLE_PLATE",
        "POSTAL_CODE",
        "TAX_IDENTIFIER",
        "BANK_ACCOUNT",
    }
)
_ROLE_CUES = (
    "davacı",
    "davalı",
    "alacaklı",
    "borçlu",
    "sanık",
    "av.",
    "avukat",
    "hâkim",
    "hakim",
    "tanık",
    "bilirkişi",
    "keşide",
    "müvekkil",
    "claimant",
    "defendant",
    "plaintiff",
    "judge",
    "justice",
    "solicitor",
    "counsel",
    "witness",
    "appellant",
    "petitioner",
)


def _rules_expected(text: str, entity: dict[str, Any]) -> bool:
    """Structured identifiers and role-prefixed names are what rules-only should remove."""
    label = str(entity["type"])
    if label in STRUCTURED_TYPES:
        return True
    value = str(entity["text"])
    if label == "COMPANY_NAME" and any(mark in value for mark in ("A.Ş.", "Ltd", "Şti")):
        return True
    if label not in PERSON_NAME_TYPES:
        return False
    window = text[max(0, int(entity["start"]) - 80) : int(entity["start"])].casefold()
    return any(cue in window for cue in _ROLE_CUES)


async def _product_predictions(text: str, language: str, mode: Any) -> tuple[set[tuple[int, int, str]], Any]:
    from app.domain.models import PrivacyProfile
    from app.services.jobs import JobStore
    from app.services.pipeline import analyze_textual_document

    store = JobStore(3600)
    job = store.create_text(text)
    job.requested_document_language = language
    job.locale = language
    try:
        analysis = await analyze_textual_document(job, PrivacyProfile.GENERAL, None, mode)
    finally:
        store.delete(job.id)
    predicted = {(entity.start, entity.end, entity.type.value) for entity in analysis.entities}
    return predicted, analysis


def _print_mode_line(label: str, metrics: dict[str, Any]) -> None:
    print(
        f"  {label}: P {metrics['precision']:.2%}  R {metrics['recall']:.2%}  "
        f"F1 {metrics['f1']:.2%}  TP {metrics['tp']} FP {metrics['fp']} FN {metrics['fn']}"
    )


async def run_product(output: Path | None) -> int:
    """Score the product pipeline. This is not the CI gate."""
    from app.domain.models import DetectionMode, LocalNERStatus

    corpus = load_corpus()
    integrity = corpus_integrity_errors(corpus)
    if integrity:
        print("GOLD INTEGRITY FAILED:")
        for error in integrity:
            print(f"  - {error}")
        return 1

    print("\n" + "=" * 60)
    print("PRODUCT PIPELINE (local only, not gated)")
    print("=" * 60)
    rules_rows: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]] = []
    for doc in corpus:
        gold = {normalize_entity(entity) for entity in doc["gold_entities"]}
        predicted, _analysis = await _product_predictions(
            doc["text"], str(doc.get("language", "tr")), DetectionMode.RULES_ONLY
        )
        rules_rows.append((doc, predicted, gold))

    probe = next(doc for doc in corpus if doc.get("language", "tr") == "tr")
    _probe_predicted, probe_analysis = await _product_predictions(
        probe["text"], "tr", DetectionMode.LOCAL_CONTEXT
    )
    ner_status = probe_analysis.local_ner_status
    ner_code = probe_analysis.local_ner_error_code or ""
    print(f"NER status: {ner_status.value} {ner_code}".rstrip())
    if ner_status in {LocalNERStatus.UNAVAILABLE, LocalNERStatus.FAILED}:
        print("LOCAL_CONTEXT did not run. Rules-only numbers are not a substitute.")
        _print_product_scores("RULES_ONLY", rules_rows)
        return 1

    context_rows: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]] = []
    context_rows.append((probe, _probe_predicted, {normalize_entity(entity) for entity in probe["gold_entities"]}))
    for doc in corpus:
        if doc is probe:
            continue
        gold = {normalize_entity(entity) for entity in doc["gold_entities"]}
        predicted, analysis = await _product_predictions(
            doc["text"], str(doc.get("language", "tr")), DetectionMode.LOCAL_CONTEXT
        )
        if analysis.local_ner_status in {LocalNERStatus.UNAVAILABLE, LocalNERStatus.FAILED}:
            print(f"NER status: {analysis.local_ner_status.value} {analysis.local_ner_error_code or ''}".rstrip())
            print("LOCAL_CONTEXT did not run. Rules-only numbers are not a substitute.")
            return 1
        context_rows.append((doc, predicted, gold))

    _print_product_scores("RULES_ONLY", rules_rows)
    _print_product_scores("LOCAL_CONTEXT", context_rows)
    report = {
        "harness": "product",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ner_status": ner_status.value,
        "rules_only": _language_report(rules_rows),
        "local_context": _language_report(context_rows),
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = save_report(report, output or (RUNS_DIR / f"{stamp}-product.json"))
    print(f"Saved: {path}")
    return 0


def _language_pairs(
    rows: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]],
    language: str,
    *,
    family: bool,
) -> list[tuple[set[tuple[int, int, str]], set[tuple[int, int, str]]]]:
    selected = []
    for doc, predicted, gold in rows:
        if doc.get("language", "tr") != language:
            continue
        if family:
            predicted = _as_family(predicted)
            gold = _as_family(gold)
        selected.append((predicted, gold))
    return selected


def _language_report(
    rows: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]],
) -> dict[str, Any]:
    report: dict[str, Any] = {}
    languages = sorted({str(doc.get("language", "tr")) for doc, _, _ in rows})
    for language in languages:
        language_rows = [row for row in rows if row[0].get("language", "tr") == language]
        report[language] = {
            "strict": _score_pairs(_language_pairs(rows, language, family=False)),
            "person_family": _score_pairs(_language_pairs(rows, language, family=True)),
            "by_split": by_split_report(language_rows).get(language, {}),
        }
    return report


def _print_product_scores(
    mode: str,
    rows: list[tuple[dict[str, Any], set[tuple[int, int, str]], set[tuple[int, int, str]]]],
) -> None:
    print(f"\n{mode}")
    for language in ("tr", "en"):
        pairs = _language_pairs(rows, language, family=False)
        if not pairs:
            continue
        scored = _score_pairs(pairs)
        label = "Turkish strict" if language == "tr" else "English strict (report only)"
        _print_mode_line(label, scored["overall"])
        family = _score_pairs(_language_pairs(rows, language, family=True))
        _print_mode_line("  person-family", family["overall"])
        language_rows = [row for row in rows if row[0].get("language", "tr") == language]
        for split, scored in by_split_report(language_rows).get(language, {}).items():
            _print_mode_line(f"  {split} strict", scored["strict"]["overall"])
            _print_mode_line(f"  {split} person-family", scored["person_family"]["overall"])


def _font_file() -> Path | None:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _write_pdf(path: Path, text: str, font_file: Path) -> None:
    import pymupdf

    document = pymupdf.open()
    remaining = text
    while remaining:
        page = document.new_page()
        page.insert_font(fontname="body", fontfile=str(font_file))
        leftover = page.insert_textbox(
            pymupdf.Rect(50, 50, 560, 800), remaining, fontname="body", fontsize=11
        )
        if not isinstance(leftover, str) or leftover == remaining:
            break
        remaining = leftover
    document.save(path)
    document.close()


def _write_docx(path: Path, text: str) -> None:
    from docx import Document

    document = Document()
    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)
    document.save(path)


def _write_udf(path: Path, text: str) -> None:
    """One paragraph per line, the same text the PDF and DOCX fixtures use."""
    paragraphs: list[str] = []
    cursor = 0
    for line in text.splitlines(keepends=True) or [text]:
        paragraphs.append(
            f'<paragraph><content startOffset="{cursor}" length="{len(line)}"/></paragraph>'
        )
        cursor += len(line)
    _write_udf_package(path, text, "".join(paragraphs))


def _write_sectioned_udf(path: Path) -> None:
    """The same icra values, in two sections with a table between them."""
    sections = [
        [
            "İCRA TAKİP TALEBİ\n",
            "Ankara 6. İcra Dairesine,\n",
        ],
        [
            "Borçlu: Cemre Dağ.\n",
            "Dosya no: 2024/771.\n",
            "Tahsilat önce TR58 9999 9000 0000 0000 0000 09 hesabına, "
            "bakiye kalırsa TR31 9999 9000 0000 0000 0000 10 hesabına aktarılsın.\n",
        ],
    ]
    rows = [
        ["Alacaklı: Yıldız Mert", "T.C. 10000000764"],
        [
            "adres: Tunalı Hilmi Caddesi No: 90 Kavaklıdere/Ankara",
            "e-posta yildiz.mert@example.com",
        ],
        ["telefon +90 532 010 1103"],
    ]
    parts: list[str] = []
    elements: list[str] = []

    def take(text: str) -> tuple[int, int]:
        start = sum(len(part) for part in parts)
        parts.append(text)
        return start, len(text)

    def paragraph(text: str) -> str:
        start, length = take(text)
        return f'<paragraph><content startOffset="{start}" length="{length}"/></paragraph>'

    for lines in sections[:1]:
        elements.append("<section>" + "".join(paragraph(line) for line in lines) + "</section>")
    table_rows: list[str] = []
    for row in rows:
        cells = []
        for cell in row:
            cells.append(f"<cell>{paragraph(cell)}</cell>")
        table_rows.append("<row>" + "".join(cells) + "</row>")
    elements.append("<table>" + "".join(table_rows) + "</table>")
    for lines in sections[1:]:
        elements.append("<section>" + "".join(paragraph(line) for line in lines) + "</section>")
    _write_udf_package(path, "".join(parts), "".join(elements))


def _write_udf_package(path: Path, text: str, elements: str) -> None:
    import zipfile

    if "]]>" in text:
        raise ValueError("synthetic UDF text cannot contain a CDATA terminator")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<template format_id="1.8">'
        f"<content><![CDATA[{text}]]></content>"
        f"<elements>{elements}</elements>"
        "</template>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("content.xml", xml.encode("utf-8"))


def _read_pdf_text(path: Path) -> str:
    import pymupdf

    document = pymupdf.open(path)
    try:
        return "\n".join(page.get_text() for page in document)
    finally:
        document.close()


def _read_docx_text(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


async def run_e2e() -> int:
    """Redact one PDF, one DOCX, and two UDFs. Rules-expected leaks fail."""
    from app.domain.models import (
        DetectionMode,
        DocumentKind,
        PrivacyProfile,
        RedactionDecision,
        RedactionRequest,
        TransformationStrategy,
    )
    from app.services.jobs import JobStore
    from app.services.pipeline import analyze_pdf, analyze_textual_document, apply_transformations
    from app.services.udf_package import extract_udf_text

    corpus = load_corpus()
    source = next(
        (
            doc
            for doc in corpus
            if doc.get("id") == "tr-test-icra-001"
        ),
        None,
    )
    if source is None:
        print("E2E source document tr-test-icra-001 is not in the corpus")
        return 1
    font = _font_file()
    if font is None:
        print("E2E needs a Unicode font and did not find one")
        return 1

    import tempfile

    leaks: list[str] = []
    gaps: list[str] = []
    masked: list[str] = []
    extraction_missing: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pdf_path = root / "sample.pdf"
        docx_path = root / "sample.docx"
        udf_path = root / "sample.udf"
        udf_table_path = root / "sample-table.udf"
        _write_pdf(pdf_path, source["text"], font)
        _write_docx(docx_path, source["text"])
        _write_udf(udf_path, source["text"])
        _write_sectioned_udf(udf_table_path)
        missing_by_label: dict[str, set[str]] = {}
        for label, path in (("UDF", udf_path), ("UDF-TABLE", udf_table_path)):
            udf_text = extract_udf_text(path).text
            print(f"{label} text extraction missing:")
            missing: set[str] = set()
            if label == "UDF-TABLE" and "\t" not in udf_text:
                print("  - table was not rendered")
                return 1
            for entity in source["gold_entities"]:
                if entity["text"] in udf_text:
                    continue
                item = f"{label} {entity['type']} {entity['text']}"
                extraction_missing.append(item)
                missing.add(entity["text"])
                print(f"  - {item}")
            if not missing:
                print("  none")
            missing_by_label[label] = missing
        for label, kind, path, reader, output_format in (
            ("PDF", "PDF", pdf_path, _read_pdf_text, "PDF"),
            ("DOCX", "DOCX", docx_path, _read_docx_text, "DOCX"),
            ("UDF", "UDF", udf_path, _read_pdf_text, "PDF"),
            ("UDF-TABLE", "UDF", udf_table_path, _read_pdf_text, "PDF"),
        ):
            store = JobStore(3600)
            job = store.create(path.name, path.read_bytes(), DocumentKind[kind])
            job.requested_document_language = "tr"
            job.locale = "tr"
            try:
                if kind == "PDF":
                    analysis = await analyze_pdf(job, PrivacyProfile.GENERAL, None, DetectionMode.RULES_ONLY)
                else:
                    analysis = await analyze_textual_document(
                        job, PrivacyProfile.GENERAL, None, DetectionMode.RULES_ONLY
                    )
                decisions = [
                    RedactionDecision(
                        entity_id=entity.id,
                        action="REDACT",
                        strategy=TransformationStrategy.REDACT,
                    )
                    for entity in analysis.entities
                ]
                if not decisions:
                    print(f"{label}: the product found nothing to redact")
                    return 1
                _output, audit = await apply_transformations(
                    job,
                    RedactionRequest(decisions=decisions, output_format=output_format),
                    None,
                )
                extracted = reader(job.output_path)
                validation = audit.validation
                print(
                    f"{label} residual status: {validation.status.value} "
                    f"messages={len(validation.residual_messages)}"
                )
            finally:
                store.delete(job.id)
            for entity in source["gold_entities"]:
                item = f"{label} {entity['type']} {entity['text']}"
                if entity["text"] not in extracted:
                    if label in missing_by_label and entity["text"] not in missing_by_label[label]:
                        masked.append(item)
                    continue
                if _rules_expected(source["text"], entity):
                    leaks.append(item)
                else:
                    gaps.append(item)
    print("\nRules-expected leaks:")
    if leaks:
        for item in leaks:
            print(f"  - {item}")
    else:
        print("  none")
    print("Known gaps (NER-needed, not a failure):")
    if gaps:
        for item in gaps:
            print(f"  - {item}")
    else:
        print("  none")
    print("UDF gold values masked:")
    if masked:
        for item in masked:
            print(f"  - {item}")
    else:
        print("  none")
    for label in ("UDF", "UDF-TABLE"):
        accounted = (
            sum(item.startswith(f"{label} ") for item in extraction_missing)
            + sum(item.startswith(f"{label} ") for item in masked)
            + sum(item.startswith(f"{label} ") for item in gaps)
            + sum(item.startswith(f"{label} ") for item in leaks)
        )
        if accounted != len(source["gold_entities"]):
            print(
                f"{label} gold values were not all accounted for "
                f"({accounted} of {len(source['gold_entities'])})"
            )
            return 1
    return 1 if leaks or extraction_missing else 0


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
    parser.add_argument(
        "--product",
        action="store_true",
        help="Local only. Score the product pipeline in RULES_ONLY and LOCAL_CONTEXT. Not the CI gate.",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Report-only legacy detector path. Not the CI gate.",
    )
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="Local only. Redact one synthetic PDF, one DOCX, and two UDFs through the product export and check for leaks.",
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
    if args.product and args.e2e or args.legacy and (args.product or args.e2e):
        raise SystemExit("Pass only one of --legacy, --product, and --e2e")
    if args.product:
        code = asyncio.run(run_product(args.output))
        if code:
            raise SystemExit(code)
        return
    if args.e2e:
        code = asyncio.run(run_e2e())
        if code:
            raise SystemExit(code)
        return
    if args.legacy:
        asyncio.run(run_evaluation(args.output))
        print("Legacy path is report-only for one release and is not the CI gate.")
        return
    code = asyncio.run(run_product_gate(args.output))
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
