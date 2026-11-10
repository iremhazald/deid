# Detection evaluation

Annotation rules are in [ANNOTATION_GUIDELINES.md](ANNOTATION_GUIDELINES.md).
Pending label and offset decisions are in
[RELABEL_PROPOSALS.md](RELABEL_PROPOSALS.md). None of those proposals are
applied to the corpus yet.

Benchmark data must be synthetic or properly licensed and de-identified. Each
JSONL record should use this shape:

```json
{
  "id": "synthetic-tr-contract-001",
  "language": "tr",
  "difficulty": "medium",
  "document_type": "contract",
  "text": "Synthetic snippet",
  "gold_entities": [
    {
      "text": "Synthetic value",
      "type": "PERSON_NAME",
      "start": 0,
      "end": 15,
      "expected_detector": "TR_PERSON_NAME"
    }
  ]
}
```

## Synthetic Value Requirements

Gold corpus values for checksum-validated entity types **must pass production
validators**:

- **NATIONAL_ID (TCKN)**: 11-digit Turkish ID numbers must satisfy the
  checksum algorithm in `app/detectors/checksum.py:validate_tckn`
- **IBAN**: Must satisfy MOD-97 checksum per ISO 13616
- **CREDIT_CARD**: Full card numbers must satisfy Luhn algorithm (partial
  "last 4 digits" references are not CREDIT_CARD entities)

Invalid synthetic values will cause false negatives in evaluation because
production validators correctly reject them.

## RULES_ONLY vs LOCAL_CONTEXT

The `evaluate_rules.py` harness runs **RULES_ONLY** mode (deterministic
pattern detection without NER). This mode can reliably detect:

- Structured identifiers: NATIONAL_ID, IBAN, EMAIL, PHONE_NUMBER, CREDIT_CARD,
  IP_ADDRESS, URL, VEHICLE_PLATE, POSTAL_CODE, TAX_IDENTIFIER
- Names with legal role context: "Sanık: Ali Demir", "Yargıç: Hasan Kılıç"
- Company names with legal suffixes: "ABC Teknoloji A.Ş."

Categories that **require NER** for full coverage (isolated names without role
context, locations, dates in prose) should be evaluated in **LOCAL_CONTEXT**
mode which includes local NER models.

## Matching

A prediction matches a gold entity when both have the same type and the span
overlap IoU is **at least 0.5**. Each prediction is paired with the unmatched
gold span that has the highest IoU. An overlap of exactly 0.5 counts. This
strict match is what the CI gates use, and the gates use Turkish documents.

The same run also reports a person-family match. `PERSON_NAME`, `FIRST_NAME`,
`LAST_NAME`, `ALIAS`, `CLAIMANT_NAME`, `DEFENDANT_NAME`, `LAWYER_NAME`,
`JUDGE_NAME`, `PROSECUTOR_NAME`, `COURT_CLERK_NAME`, `VICTIM_NAME`,
`COMPLAINANT_NAME`, `SUSPECT_NAME`, `ACCUSED_NAME`, `INTERVENOR_NAME`,
`LEGAL_REPRESENTATIVE_NAME`, `MEDIATOR_NAME`, `INTERPRETER_NAME`,
`ENFORCEMENT_OFFICER_NAME`, `NOTARY_NAME`, `ARBITRATOR_NAME`, `WITNESS_NAME`,
and `EXPERT_NAME` count as one type. The
difference shows whether a person was missed or only the role was wrong.
Person-family numbers are not gated. The product path scores English and
does not merge it into the Turkish total. `--legacy` does not score English.

## Thresholds

- Turkish strict precision ≥ 75%
- Turkish strict recall ≥ 50% (rules-only has inherent limitations)
- Critical category recall ≥ 95% for: NATIONAL_ID, IBAN, EMAIL, PHONE_NUMBER

PERSON_NAME and CREDIT_CARD are excluded from critical 95% recall gates because:
- PERSON_NAME: Isolated names require NER; rules detect only role-prefixed names
- CREDIT_CARD: Partial card references ("last 4 digits") are not full cards

Each category line prints its gold count. Precision, recall, and F1 are also
printed by difficulty and by document type. A category, difficulty, or document
type with fewer than 10 gold entities is marked `low sample`. The flag does
not fail CI.

## Running

```bash
python evaluation/evaluate_rules.py
python evaluation/evaluate_rules.py --output evaluation/runs/custom.json
python evaluation/evaluate_rules.py --compare evaluation/runs/before.json evaluation/runs/after.json
python evaluation/evaluate_rules.py --legacy
python evaluation/evaluate_rules.py --product
python evaluation/evaluate_rules.py --e2e
```

The default command is the CI gate. It scores the product rules-only path:
deterministic detectors for the document language, then the product merge.
`--legacy` runs the previous list and is report-only for one release.
`--product` also runs local NER and is not gated. If that model is missing,
the run fails instead of presenting rules-only numbers as the NER result.
`--e2e` redacts one synthetic PDF and one DOCX and fails when a structured
identifier or a role-prefixed name remains. Other remaining gold values are
known gaps. Before scoring, it checks every gold span: `text[start:end]` must
equal the gold text, and every label must be an `EntityType` on the scope
list in `ANNOTATION_GUIDELINES.md`. A label that is not an `EntityType` fails
that check.
A failed check stops the run, so CI fails before any metric is printed. Each run writes `evaluation/runs/<utc>-product_rules.json`.
`--compare` prints precision, recall, F1, and count deltas between two saved
files and does not apply the gates.

Configurations to compare:

1. deterministic only (`RULES_ONLY`) — CI-gated
2. deterministic + local NER (`LOCAL_CONTEXT`) — not CI-gated (requires models)

V1 does not evaluate an external or generative LLM path.

## Part 4

The CI command is now the product rules-only path. `--legacy` keeps the
previous detector list as a report for one release and does not gate CI.

On this gold set the legacy path is 86.17% precision and 76.22% recall
(218 true positives, 35 false positives, 68 false negatives). The product
rules-only path is 90.83% precision and 76.22% recall (218 true positives,
22 false positives, 68 false negatives). Recall is unchanged. The precision
move is the product merge dropping false positives, not a detector change.

English is scored on this path and is not merged into the Turkish total.
A separate English gate for `EMAIL`, `PHONE_NUMBER`, `IBAN`, and
`NATIONAL_ID` is the intended next check. It is not armed: on the product
rules-only path email recall is 100%, phone recall is 0%, IBAN recall is
77.42%, and national-id recall is 60%. Arming the 95% bar would fail CI.
