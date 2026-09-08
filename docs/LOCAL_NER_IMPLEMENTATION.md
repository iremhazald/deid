# Local NER Implementation

## Overview

On-device named-entity recognition (NER) is used by `LOCAL_CONTEXT`, the normal
product scan mode. NER is a supplementary candidate generator. It does not
replace deterministic detection, does not validate structured identifiers, and
does not perform masking or redaction.

There is no generative LLM, external AI, or cloud NER fallback.

## Modes

| Mode | NER | Purpose |
|------|-----|---------|
| `LOCAL_CONTEXT` | Turkish BERTurk or English spaCy | Normal product scan |
| `RULES_ONLY` | None | Internal/test/debug mode |

`RULES_ONLY` never loads NER models. `HYBRID` is not a V1 product mode.

## Providers

| Language | Provider | Default Model | License |
|----------|----------|---------------|---------|
| Turkish | `TurkishBerturkNERProvider` | `akdeniz27/bert-base-turkish-cased-ner` | MIT |
| English | `EnglishSpacyNERProvider` | `en_core_web_sm` | MIT-style (Explosion) |

The Turkish checkpoint is NER-finetuned BERTurk with `PER` / `ORG` / `LOC`
labels. The default inference backend is ONNX Runtime (CPU).

## Pipeline Integration

NER runs after deterministic detection in `LOCAL_CONTEXT` mode:

1. Deterministic detectors and evidence scoring
2. Structural detectors, custom terms, verification
3. PDF letterhead / QR detection
4. **Local NER** (`run_local_ner_layer`)
   - Select provider by document language (`tr` or `en`)
   - Generate predictions
   - Convert to `EntityCandidate` via `ner_prediction_to_candidate`
   - Evaluate through existing `evaluate_candidate` / `decide`
   - Resolve overlaps against hard identifiers and existing candidates
5. Merge candidates, name pairs, repeats
6. Assign resolved entities and apply policy

NER candidates are evaluated through the same evidence-scoring pipeline as
deterministic candidates. NER never directly writes redaction operations.

## Installation

From `apps/api`:

```bash
pip install -e ".[local-ner]"
python -m spacy download en_core_web_sm
```

Language-specific extras:

```bash
pip install -e ".[local-ner-tr]"    # Turkish: transformers + onnxruntime
pip install -e ".[local-ner-en]"    # English: spaCy
```

Cache the Turkish checkpoint (`model.onnx`, tokenizer, and config) before
offline use. A previous PyTorch-only cache (`model.safetensors`) is not
sufficient for the ONNX backend.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEID_TR_NER_MODEL` | `akdeniz27/bert-base-turkish-cased-ner` | Turkish checkpoint |
| `DEID_TR_NER_BACKEND` | `onnx` | Turkish backend (`onnx` or `pytorch`) |
| `DEID_EN_NER_MODEL` | `en_core_web_sm` | spaCy model name |
| `DEID_NER_LOCAL_FILES_ONLY` | `true` | Refuse downloads at inference |
| `DEID_NER_MAX_CHARS_PER_CHUNK` | `1200` | Long-page chunk size |
| `DEID_NER_CHUNK_OVERLAP_CHARS` | `80` | Chunk overlap |

## Language Routing

Document language determines the NER provider:

- `tr` → Turkish BERTurk provider
- `en` → English spaCy provider

Document language is resolved from the `document_language` request field, not
from UI language. See `docs/DOCUMENT_LANGUAGE_ROUTING.md` for details on
document-language resolution.

Unknown or unsupported language values return `LOCAL_NER_LANGUAGE_UNSUPPORTED`.
Only the matching provider is loaded.

## Lazy Loading and Offline Behaviour

The API process starts with no NER models loaded. The first `LOCAL_CONTEXT`
scan for a language loads the corresponding provider and caches it in memory.
Subsequent scans reuse the loaded model. Only the requested language is loaded.

With `DEID_NER_LOCAL_FILES_ONLY=true` (default), inference uses only locally
cached model assets. If required assets are missing, the scan completes with
deterministic findings and reports `local_ner_status=UNAVAILABLE`. There is no
external download during user scans and no cloud fallback.

## Model-Unavailable Behaviour

If local NER is unavailable (missing model, missing dependencies, or inference
error):

- The scan completes with deterministic findings
- The mode remains `LOCAL_CONTEXT`
- A non-blocking status is returned (`UNAVAILABLE` or `FAILED`)
- There is no automatic fallback to external services

The user does not need to select a different scan mode.

## Evidence and Scoring

NER predictions become `EntityCandidate` entries with detector `LOCAL_NER_TR` or
`LOCAL_NER_EN`. Evidence codes include:

- `ner_person`, `ner_organisation`, `ner_location`
- `ner_high_model_score` / `ner_weak_model_score` (optional)
- `ner_legal_context` (optional)

`ner_model_score` is metadata only. It is not displayed as a confidence
percentage and is not the DeID decision. The decision remains `ACCEPT` /
`REVIEW` / `IGNORE` based on the evidence-scoring pipeline.

Hard validators retain authority: an invalid IBAN cannot become valid because
NER fired nearby. Structured types (TCKN, VKN, IBAN, card, case/file numbers,
phone, email, URL, IP, UYAP) are never mapped from NER labels.

## Supported Labels

| NER Label | DeID Entity Type |
|-----------|------------------|
| `PER`, `PERSON` | `PERSON_NAME` |
| `ORG`, `ORGANISATION`, `ORGANIZATION` | `ORGANISATION` |
| `LOC`, `LOCATION`, `GPE` | `LOCATION` |

Other labels (`DATE`, `LAW`, `MONEY`, `NORP`, `EVENT`, `PRODUCT`, etc.) are
ignored.

## Limitations

- Local NER is supplementary and may produce false positives or false negatives.
- Model assets must be cached locally before offline inference.
- NER does not perform coreference resolution (`Mehmet`, `M. Yılmaz`, and
  `Mehmet Yılmaz` are not automatically linked).
- NER does not infer legal roles from identity alone.
- Ambiguous identities require downstream human resolution.
- `resolved_entity_id` uses normalized-surface grouping, not semantic identity.
