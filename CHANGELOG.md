# Changelog

All notable changes and improvements to the DeID LegalTech platform.

## [Unreleased]

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
