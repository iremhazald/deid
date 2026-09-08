# DeID V1 Architecture

## Overview

DeID V1 is a local-first legal document de-identification application. Detection
combines deterministic rules with on-device named-entity recognition (NER). There
is no generative LLM or external AI review path.

## Detection Pipeline

The normal product scan mode is `LOCAL_CONTEXT`.

1. **Input validation.** Verify PDF type, signature, size, corruption, and
   encryption.
2. **Text extraction.** Extract native PDF text and run local RapidOCR on
   scanned or image-based pages.
3. **Deterministic detection.** Run independent global and language-specific
   (Turkish or English) detector registries. Score is an evidence weight, not a
   confidence percentage.
4. **Local NER.** On `LOCAL_CONTEXT`, run on-device NER as an additional
   candidate generator: Turkish BERTurk or English spaCy, selected by document
   language. If NER is unavailable (missing model/dependencies), the scan
   completes deterministically without external fallback; the mode remains
   `LOCAL_CONTEXT`.
5. **Candidate resolution.** Normalize and conservatively deduplicate exact
   span/type matches.
6. **Profile recommendations.** Apply versioned privacy-profile recommendations
   independently from detection. Detected entities receive recommended actions
   based on type and evidence strength.
7. **Human review.** Users review detected entities and recommendations, confirm
   or override suggested actions, and add manual findings where necessary.
8. **PDF transformation.** Map accepted spans to native/OCR regions and apply
   content and image-pixel redactions with secure PDF object cleanup.
9. **Validation.** Re-extract the transformed output, rerun relevant detectors,
   and return PASS, WARNING, or FAILED.
10. **Export.** Persist the validated redacted PDF and a raw-value-free JSON
    audit report to the configured output directory.

`RULES_ONLY` is an internal/test/debug mode that skips NER. It is not a
user-facing product mode.

## Request Responsiveness

Document parsing, OCR, detector passes, candidate consolidation, hashing, and
export writing are CPU-bound and run in a worker thread, so one large document
cannot stall the event loop and make the API unreachable.

## Limitations

- V1 focuses on PDF workflows.
- Automated detection may produce false positives and false negatives.
- OCR quality can affect detection and redaction accuracy for scanned documents.
- Ambiguous person or entity relationships may require human resolution.
- De-identification does not guarantee anonymization.
- Human review is required before sharing or exporting sensitive documents.

Unmappable selected spans block export. A failed validation does not persist a
downloadable output.

## Privacy Boundary

The FastAPI process stores active jobs in an operating-system temporary
directory for a configured TTL (`REDACTION_JOB_TTL_SECONDS`, default 24 hours)
and removes leftover jobs at process shutdown.

Validated redacted outputs and audit reports are automatically persisted to
`REDACTION_OUTPUT_DIR` (default: `outputs`).

For hostile multi-user or internet-facing deployment, the in-memory job store
and local process boundary are insufficient. Add authentication, per-user
authorization, isolated workers, encrypted storage, malware scanning, and an
external secrets manager before deployment.
