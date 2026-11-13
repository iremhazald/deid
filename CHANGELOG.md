# Changelog

All notable changes and improvements to the DeID LegalTech platform.

## [Unreleased]

- English phone detection now allows one function word (`at`, `on`, or `to`)
  between the label and the number, the verb `telephoned` with an optional
  `to`, and the phrase `call me on`. The number must contain 10 to 15 digits.
  `or` after an email, and a bare `call`, are unchanged. The label cannot
  match inside a longer word, so `telephone` does not fire on `telephoned`.
  On the phones already in the corpus, dev recall moved from 3/28 to 14/28
  and test recall from 0/10 to 4/10, with precision 100% both times. The
  ten-phone holdout, scored on its own, is 6/10. There is no new false
  positive. Turkish scores did not move.
- Katılan in a criminal case is now `VICTIM_NAME`, matching the guidelines.
  Müdahil is `VICTIM_NAME` only when the text is criminal. Fer'i müdahil
  stays `INTERVENOR_NAME`. Attendance (`toplantıya katılan`) is still not a
  person. Turkish strict precision moved from 90.64% to 91.39% and recall
  from 80.40% to 81.06% (242 / 25 / 59 to 244 / 23 / 57). Dev gained one
  true positive and lost one false positive; test did the same. English
  scores did not move. Victim recall is 4/4 and intervenor has no false
  positives.
- The approved role relabel is gold only. Turkish strict precision moved from
  87.35% to 91.30% and recall from 77.27% to 80.77% (221 / 32 / 65 to
  231 / 22 / 55). Detectors did not change. `MELTEM ARI` in
  `tr-dev-caption-001` was already the claimant under the old rules
  (`DAVACI`); labeling her `PERSON_NAME` was a gold error before these role
  types existed. The attendance names in `tr-names-only-001` were not
  relabeled.
- Role-coverage examples were added to the gold set for roles that had no
  example, in both dev and test, plus three directly labeled English phone
  numbers on dev. Turkish strict precision moved from 91.30% to 90.64% and
  recall from 80.77% to 80.40% (231 / 22 / 55 to 242 / 25 / 59). Detectors
  did not change. The three labeled English numbers are detected. The other
  35 English phone spans are still missed.
- The residual check no longer reports a placeholder this export just wrote.
  `[GİZLENDİ]`, `[REDACTED]`, and the tag tokens are not new findings. A name
  that is still present is still reported. This covers the DOCX and UDF
  text-copy exports.
- The English national-id label no longer matches inside a longer word.
  "national identifier" is not read as "national id" plus the rest of the
  word. English national-id recall on this gold is 0/10, and Turkish scores
  did not move.
- Eleven legal-role person labels were added to the existing schema: victim,
  complainant, suspect, accused, intervenor, legal representative, mediator,
  interpreter, enforcement officer, notary, and arbitrator. `sanık` is
  `ACCUSED_NAME`. `davalı` stays `DEFENDANT_NAME`. `müşteki` stays separate
  from `CLAIMANT_NAME`. A role word without a name is not a person finding.
  Detection still depends on the document context and does not guarantee that
  every role mention is found or correctly classified.
- CI now scores the product rules-only path. On this gold set that measurement
  is 90.83% precision and 76.22% recall, against 86.17% and 76.22% on the
  legacy path. Recall is unchanged. The precision difference is the product
  merge, not a detector change. `--legacy` remains report-only for one release.
  An English gate for email, phone, IBAN, and national ID is not armed: phone
  recall is 0%, IBAN recall is 77.42%, and national-id recall is 60%.
- A detected date of birth that stays visible now counts in the
  re-identification score. A calendar date still counts separately. The
  legacy-harness metrics did not move.
- The Turkish gold relabel moved the legacy-harness precision from 80.85% to
  88.30% and recall from 62.81% to 68.03% (121 gold spans to 122). Detectors,
  rules, and thresholds did not change. The same sentence belongs in
  `evaluation/DATASET_CARD.md` when that card is written.
- Salary left the evaluation scope. The three `SALARY_INFORMATION` labels in
  `tr-salary-001` were removed and the amounts stayed in the text. Legacy-harness
  recall moved from 68.03% to 69.75%. Precision stayed 88.30% (true positives
  83, false positives 11, false negatives 39 to 36). That move is a scope
  change, not a system improvement.
- Salary is no longer a detected or masked type. It left `EntityType`, the tag
  catalog, the placeholder prefixes, the review labels, and the
  re-identification quasi-identifier set. The legacy-harness metrics did not
  move on that code change.
- DeID V2 Phase 3 (not released): UYAP UDF files can be uploaded and are reviewed
  as extracted text in the existing text workspace. DeID does not reproduce the
  original UYAP layout and does not preserve or reissue the electronic
  signature. UDF export is not supported. The transformed text can be copied,
  and a new PDF can be downloaded from that text. No external AI or document
  service is used.
- DeID V2 Phase 2 (not released): DOCX can be uploaded and is reviewed as
  extracted text in the existing text workspace. Word formatting and page
  layout are not preserved. Headers and footers are appended after the body.
  Images, text boxes, comments, footnotes, equations, SmartArt, and embedded
  objects may not be extracted and are not inspected. Copy text uses the same
  document-language REDACT tokens as PDF text review. "Download new DOCX" and
  "Download PDF" create new documents from that transformed text; they are not
  a redaction of the original Word file. No external AI service is used.
- DeID V2 Phase 1 (not released): after a PDF is selected, choose the existing page workspace
  or a text workspace. Text review uses the same local extraction, OCR, and
  detection pipeline. The result can be copied as plain text. REDACT in that
  copied text is `[GİZLENDİ]` or `[REDACTED]` according to the document
  language. Secure PDF export stays on the page workspace. DeID does not send
  the copied text to an external AI service.
- DeID V1 removes generative LLM / OpenAI-compatible privacy review (`HYBRID`,
  `/api/ai/*`, enrich-ai, provider settings). Normal scan remains `LOCAL_CONTEXT`
  (deterministic detectors + on-device NER).
- Removed unsupported semantic categories that depended on LLM review:
  `BIOMETRIC_INFORMATION`, `GENETIC_INFORMATION`, `RELIGIOUS_INFORMATION`,
  `POLITICAL_INFORMATION`, `TRADE_UNION_INFORMATION`, `SEXUAL_LIFE_INFORMATION`,
  `ETHNIC_ORIGIN`.
- GDPR / GDPR+KVKK profiles recommend leftover URLs; KVKK and GENERAL do not.

## [0.3.0] - 2026-08-20

### 🚀 Major Features

#### Pseudonymization Strategy
- **New transformation strategy: PSEUDONYM** - Replace PII with realistic but fake values
  - Realistic Turkish name generation (e.g., "Mehmet Yılmaz" → "Ahmet Kaya")
  - Gender-aware name selection based on original text patterns
  - Organization pseudonym generation
  - Deterministic: same entity always gets same pseudonym across document
  - Case-level consistency via secret key stored per job
  - Falls back to placeholder if generator unavailable
- Added to `PERSON_STRATEGIES` catalog for all person-type entities
- Full i18n support (Turkish and English UI labels)
- Test suite: `test_pseudonym_strategy.py`

#### Locale Pack System
- **Extensible multi-jurisdiction architecture** for easy addition of new countries
- Built-in packs:
  - `global`: Jurisdiction-agnostic patterns (email, URL, IPv4, IBAN, Luhn)
  - `tr`: Turkish legal documents (TCKN, Turkish IBAN, court names, addresses)
- Registry system: `register_locale_pack()`, `list_locale_packs()`
- API endpoint: `GET /api/locales` to list available locale packs
- Documentation: `docs/locale-packs.md` with German pack example
- Backward-compatible: existing code uses legacy DETECTORS if locale_ids not specified

#### Re-identification Risk Assessment
- **Privacy risk scoring** based on quasi-identifier analysis
- Risk levels: low / medium / high / critical
- Scoring factors:
  - Direct identifiers (NATIONAL_ID, EMAIL, IBAN, etc.) → critical risk
  - Quasi-identifier combinations (DATE + ADDRESS + HEALTH_INFO) → high risk
  - Sensitive data combinations get risk boost
- API endpoint: `POST /api/jobs/{job_id}/risk-assessment`
- Returns warnings and actionable recommendations
- Implementation: `apps/api/app/privacy/reidentification.py`

### 🐛 Critical Bug Fixes

#### Turkish Advanced Detector Fixes
- **Fixed YARGIÇ detection** (was using incorrect Unicode `Č` instead of `Ç`)
  - "Yargıç Ayşe Demir" now correctly detected as JUDGE_NAME
  - Added SAVCI (prosecutor) detection
- **Vehicle plate validation** now requires valid Turkish province codes (01-81)
  - Invalid codes like 99, 00 no longer match
- **Date detection** now context-aware to reduce false positives
  - Only detects dates with birth/identity context keywords
  - Filters out court hearing dates and other procedural dates
- Test suite: `test_turkish_advanced_fixes.py`

### 🔬 Evaluation & Quality

#### Recall-Gated Evaluation
- **Overlap-based entity matching** instead of exact offset match
  - Uses Intersection-over-Union (IoU) for span comparison
  - Tolerates 1-2 character offset differences
  - More realistic recall measurement
- **Multiple threshold gates:**
  - Overall precision ≥ 75%
  - **Overall recall ≥ 85%** (NEW - prioritizes catching PII)
  - **Critical categories recall ≥ 95%** (NATIONAL_ID, EMAIL, PHONE, IBAN, etc.)
- Prevents low-recall rule changes from merging (PII leakage risk)
- Enhanced CI reporting with ✓/❌ per check

### 🐳 DevOps & Deployment

#### Docker Support
- **Multi-stage Dockerfile** with optimized build
  - Backend: Python 3.11 + PyMuPDF + RapidOCR
  - Frontend: Node 20 build → static assets
  - Final image: ~500MB runtime
- **docker-compose.yml** with one-command startup
  - Optional Ollama service for local AI
  - Health checks and auto-restart
  - Volume mounts for redacted outputs
- **.dockerignore** for efficient builds
- **Health check endpoint** integrated
- Documentation: `docs/ollama-setup.md`

#### CI/CD Pipeline
- **GitHub Actions workflow** (`.github/workflows/ci.yml`)
  - Backend tests (pytest + coverage)
  - **Evaluation harness** with recall/precision gates (blocks bad rule changes)
  - Frontend tests (Vitest + TypeScript)
  - Linting (ruff + ESLint)
  - Docker build test
- Runs on push and PR to main/develop branches

### 📚 Documentation

#### New Guides
- **Locale Pack System** (`docs/locale-packs.md`)
  - How to create a new jurisdiction pack
  - Example: German legal documents pack
  - Guidelines for precision, checksum sources, testing
- **Ollama Setup** (`docs/ollama-setup.md`)
  - Fully offline AI with Ollama
  - Docker Compose integration
  - Model recommendations (llama3.2, qwen2.5)
  - Performance tuning (CPU vs GPU)
  - Troubleshooting guide
- **PDF Visual Highlight Guide** (`docs/pdf-visual-highlight-guide.md`)
  - Implementation guide for bounding-box overlays
  - Backend API + frontend React components
  - Currently deferred but ready to implement

### 🔧 Minor Improvements

- **Version consistency:** Fixed FastAPI version mismatch (now 0.2.2 everywhere)
- **Frontend locales:** Added PSEUDONYM strategy translations (tr/en)
- **README:** Updated with Docker instructions and Ollama setup
- Added `__init__.py` for detector packs module structure
- Created `apps/api/app/privacy/` module for re-identification logic

### 🧪 Testing

New test files:
- `test_turkish_advanced_fixes.py` - Turkish detector bug fixes
- `test_pseudonym_strategy.py` - Pseudonym generation and consistency

Updated:
- `evaluate_rules.py` - Overlap-based matching + recall gates

### 🚧 Known Limitations

- Pseudonym maps are not yet encrypted at rest (per-job secret in memory only)
- Locale pack UI selection not yet exposed in frontend
- PDF visual highlights still deferred (API design documented)
- Re-identification risk not yet shown in frontend UI

### 🔄 Backward Compatibility

All changes are backward compatible:
- Legacy `run_detectors()` without locale_ids works as before
- New PSEUDONYM strategy falls back to PLACEHOLDER if generator unavailable
- Evaluation thresholds can be adjusted in `evaluate_rules.py`

---

## [0.2.2] - Prior Release

(Previous functionality described in existing docs)
