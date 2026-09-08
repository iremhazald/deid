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

Evaluation runs should report per category and overall:

- precision, recall, F1
- false-negative and false-positive rates
- latency

Configurations to compare:

1. deterministic only (`RULES_ONLY`)
2. deterministic + local NER (`LOCAL_CONTEXT`)

V1 does not evaluate an external or generative LLM path.
