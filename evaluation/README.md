# Detection evaluation

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

## Thresholds

- Overall precision ≥ 75%
- Overall recall ≥ 50% (rules-only has inherent limitations)
- Critical category recall ≥ 95% for: NATIONAL_ID, IBAN, EMAIL, PHONE_NUMBER

PERSON_NAME and CREDIT_CARD are excluded from critical 95% recall gates because:
- PERSON_NAME: Isolated names require NER; rules detect only role-prefixed names
- CREDIT_CARD: Partial card references ("last 4 digits") are not full cards

## Running

```bash
python evaluation/evaluate_rules.py
```

Configurations to compare:

1. deterministic only (`RULES_ONLY`) — CI-gated
2. deterministic + local NER (`LOCAL_CONTEXT`) — not CI-gated (requires models)

V1 does not evaluate an external or generative LLM path.
