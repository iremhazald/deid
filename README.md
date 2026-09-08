# DeID

Local-first legal document de-identification for Turkish and English PDFs.

De-identify Turkish and English legal PDFs using deterministic detection,
local NER, evidence-based resolution, and human review — without sending
documents to external AI services.

## Why DeID

Legal documents contain sensitive identifiers, personal data, legal-role
information, and contextual references that should be reviewed before sharing
with external systems or third parties.

DeID provides a local-first review and transformation workflow. Documents are
processed locally using deterministic detection rules and on-device NER models.
DeID does not send document content to external generative AI services for
detection.

## What It Does

- **Turkish and English legal documents** — Deterministic detectors for legal
  roles, structured identifiers, courts, addresses, and document references in
  both Turkish and English legal contexts
- **47 entity types** — People, legal roles, government IDs, contact information,
  financial identifiers, legal references, addresses, organisations, and dates
- **Local NER** — Turkish BERTurk and English spaCy models run on-device as
  supplementary candidate generators
- **Evidence-based resolution** — Findings are scored by structural evidence,
  not confidence percentages
- **Human review** — Review detected findings, override recommendations, add
  manual findings, and resolve ambiguous identities before export
- **Secure PDF transformation** — Content redaction with PDF object cleanup,
  not visual overlays
- **Residual validation** — Re-extraction and detector rescan after transformation
- **Bilingual interface** — Turkish and English UI with document-language-aware
  placeholder tags

## How It Works

```
PDF (native or scanned)
         ↓
Text extraction + local OCR (RapidOCR)
         ↓
Deterministic detection (global + language-specific)
         +
Local NER (Turkish BERTurk or English spaCy)
         ↓
Evidence scoring and candidate resolution
         ↓
Human review and manual findings
         ↓
Transformation (redact / placeholder / initials / partial mask)
         ↓
Secure PDF transformation with object cleanup
         ↓
Residual validation (re-extract + rescan)
         ↓
Export validated PDF + audit report
```

See [docs/architecture.md](docs/architecture.md) for detailed pipeline documentation.

## Detection Architecture

### Deterministic Detection

Deterministic detectors handle structured identifiers and legal-document context:

- **Structured identifiers** — TCKN, IBAN, credit cards, phone numbers, emails
  with checksum and format validation
- **Legal roles** — Claimant, defendant, judge, lawyer, witness, expert with
  role-aware evidence
- **Legal references** — Case numbers, file numbers, court names, decision references
- **Addresses** — Composite address detection with street types and postal codes
- **Companies and organisations** — Legal suffixes, institution patterns
- **False-positive suppression** — Court names, legal terms, and procedural
  headings are not misidentified as person names

Deterministic validators retain authority: an invalid IBAN remains invalid even
if NER fires nearby. Evidence scores are structural weights, not confidence
percentages.

See [docs/ENGLISH_DETERMINISTIC_LEGAL_PACK.md](docs/ENGLISH_DETERMINISTIC_LEGAL_PACK.md)
for English-General detection documentation.

### Local NER

On-device named-entity recognition supplements deterministic detection:

| Language | Model | Runtime |
|----------|-------|---------|
| Turkish | `akdeniz27/bert-base-turkish-cased-ner` | ONNX Runtime |
| English | `en_core_web_sm` | spaCy |

- Models run locally; only the relevant language model is loaded
- NER is a candidate generator — it does not replace deterministic detection
- If NER is unavailable, detection completes deterministically without external
  fallback
- No cloud NER fallback

See [docs/LOCAL_NER_IMPLEMENTATION.md](docs/LOCAL_NER_IMPLEMENTATION.md) for
installation and configuration details.

## Human-in-the-Loop Review

DeID requires human review before export:

- Review detected findings with evidence details
- Change transformation strategy per category, entity, or occurrence
- Add manual findings for content the detectors missed
- Remove incorrect detections
- Resolve possible person matches with conservative suggestions
- Preview transformations before committing

DeID does not perform automatic coreference resolution. Ambiguous references
(`John`, `Mr Smith`, `J. Smith`) are presented as possible matches for user
confirmation rather than silently merged.

## Transformation Methods

| Method | Description |
|--------|-------------|
| **Redact** | Remove content completely |
| **Placeholder** | Replace with labeled tag (`[PERSON_1]`, `[KİŞİ_1]`) |
| **Initials** | Show initials only (`John Smith` → `J.S.`) |
| **Partial Mask** | Mask portion of value (`123-456-7890` → `123-***-7890`) |

Placeholder tags follow the resolved document language with Turkish suffix
harmony where applicable (`[KİŞİ_1]'in`, `[KİŞİ_2]'e`).

## Privacy Model

DeID is local-first:

- **Detection** — Deterministic rules and NER run locally
- **OCR** — RapidOCR runs locally (no external OCR service)
- **Processing** — No document content is sent to external generative AI services
- **Storage** — Active jobs are stored in a temporary directory and removed after
  a configurable TTL (default: 24 hours) or at process shutdown
- **Export** — Validated outputs and audit reports are persisted to the configured
  output directory

Local-first describes the processing architecture. It does not itself guarantee
legal anonymization or regulatory compliance. De-identification reduces
identifiability but does not guarantee that re-identification is impossible.

## Language Support

UI language and document language are independent:

- **Document language** — Turkish or English (determines detector and NER routing)
- **UI language** — Turkish (`/`) or English (`/en`)

Placeholder tags follow the document language, not the interface language.

## Quick Start

Requirements: Python 3.11+, Node.js 20+

```bash
# Clone and enter the repository
git clone <repository-url>
cd deid

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install Python dependencies
pip install -r apps/api/requirements.txt

# Install Node dependencies
cd apps/web && npm install && cd ../..

# Start development server (API + Web UI)
npm run dev
```

Open http://localhost:5173/ for Turkish or http://localhost:5173/en for English.

### Local NER Model Setup

For full local NER support in the normal `LOCAL_CONTEXT` scan:

```bash
# From apps/api directory
pip install -e ".[local-ner]"
python -m spacy download en_core_web_sm
```

The Turkish checkpoint is downloaded to the Hugging Face cache on first use.
See [docs/LOCAL_NER_IMPLEMENTATION.md](docs/LOCAL_NER_IMPLEMENTATION.md) for
offline setup and configuration.

## Configuration

Copy `.env.example` to `.env` (created automatically by `npm run dev`).

| Variable | Default | Description |
|----------|---------|-------------|
| `REDACTION_JOB_TTL_SECONDS` | `86400` | Job expiry (24 hours) |
| `REDACTION_OUTPUT_DIR` | `outputs` | Where validated exports are saved |
| `REDACTION_MAX_FILE_MB` | `25` | Maximum upload size |

See `.env.example` for NER configuration options.

## Project Structure

```
deid/
├── apps/
│   ├── api/                 # Python FastAPI backend
│   │   ├── app/
│   │   │   ├── detectors/   # Deterministic detection rules
│   │   │   ├── ner/         # Local NER providers
│   │   │   ├── transforms/  # PDF transformation
│   │   │   └── services/    # Pipeline orchestration
│   │   └── requirements.txt
│   └── web/                 # React frontend
│       └── src/
├── docs/
│   ├── architecture.md
│   ├── LOCAL_NER_IMPLEMENTATION.md
│   └── ENGLISH_DETERMINISTIC_LEGAL_PACK.md
├── evaluation/              # Synthetic evaluation corpus
├── scripts/
└── LICENSE
```

## Documentation

- [Architecture](docs/architecture.md) — Detection pipeline and privacy boundary
- [Local NER](docs/LOCAL_NER_IMPLEMENTATION.md) — On-device NER setup and configuration
- [English Detection](docs/ENGLISH_DETERMINISTIC_LEGAL_PACK.md) — English-General
  deterministic legal pack

## Testing

The public `evaluation/` directory contains a synthetic corpus and
deterministic detection benchmark. The larger internal regression suite is
excluded because parts of its test corpus were derived from private legal
documents; no private test data is included in this repository.

```bash
# Run frontend tests
npm run test:web
```

## Limitations

- **Detection accuracy** — Automated detection may produce false positives and
  false negatives. Human review is required.
- **OCR quality** — Detection and redaction accuracy depends on OCR quality for
  scanned documents.
- **Not anonymization** — De-identification reduces identifiability but does not
  guarantee that re-identification is impossible. Contextual and quasi-identifying
  information may remain.
- **PDF focus** — V1 focuses on PDF workflows.
- **English coverage** — English support is English-General, not jurisdiction-
  specific (no UK NINO, US SSN, etc.).
- **Ambiguous identities** — Abbreviated or partial name references may require
  manual resolution.
- **No coreference** — NER does not automatically link `Mehmet`, `M. Yılmaz`,
  and `Mehmet Yılmaz`.

## License

[Apache License 2.0](LICENSE)
