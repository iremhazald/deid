# English-General Deterministic Legal Pack

**Language:** English  
**Jurisdiction:** General (not UK, US, CA, or AU)

This pack provides deterministic detection of legal-document structures and
sensitive information in English documents. It does not redesign scan modes,
NER, scoring, transformation policy, OCR, or PDF redaction.

---

## Scope

The pack detects legal-document structures and sensitive surfaces that can be
identified deterministically from:

- labels
- legal roles
- formatting
- local context
- structured identifiers
- legal-reference syntax
- address grammar
- dates in identity contexts
- document-local exact full-name repeats

It is model-free. It does not call spaCy, transformers, BERT, an LLM, or any
network API.

Legal roles are **evidence**, not identity. `Claimant: John Smith` yields
`John Smith` as `PERSON_NAME` with `en_legal_role_label` / `en_party_label`
evidence. It does **not** create `[CLAIMANT_1]` and does not assert that later
`John`, `J. Smith`, or `Mr Smith` are the same person.

---

## Why English-General

English legal documents share role labels, caption grammar, company suffixes,
and address tokens across jurisdictions. National identifiers, postcodes, and
docket syntax do not.

V1 implements one jurisdiction-neutral pack (`locale_id = "en"`). Jurisdiction-
specific identifiers such as UK National Insurance Numbers or US Social Security
Numbers are intentionally not validated by this pack.

---

## Runtime Integration

Detector routing follows the selected document language, not the interface
language.

When document language is English:

```
locale_ids = ["global", "en"]
→ GLOBAL_STRUCTURED + EN_LEGAL_STRUCTURE
```

Pipeline integration:

1. `run_detectors` with locale packs (global + English-General)
2. `run_structural_detectors` (language-agnostic LABEL:VALUE)
3. Custom terms, PDF letterhead/QR when applicable
4. **`RULES_ONLY`** — stop (no NER)
5. **`LOCAL_CONTEXT`** — `run_local_ner_layer` (English spaCy) after
   deterministic candidates; same evidence scoring and merge

Scoring uses the existing engine (`apply_scoring` → `evaluate_candidate` →
`resolve_scored`). There is no separate `english_confidence` or `english_score`.

---

## Supported Categories

Mapped to the existing entity catalog.

| Category | Detector(s) | Notes |
|----------|-------------|-------|
| PERSON_NAME / LAWYER_NAME / JUDGE_NAME / EXPERT_NAME | `EN_ROLE_PERSON`, `EN_LEGAL_PARTY`, `EN_TITLED_PERSON`, `EN_SIGNATURE_PERSON`, `EN_NARRATIVE_PERSON` | Role is evidence only |
| COMPANY_NAME | `EN_COMPANY_SUFFIX` | Suffix grammar |
| ORGANISATION | `EN_ORGANISATION` | Institution phrases |
| COURT_NAME | `EN_COURT` | No country inferred |
| ADDRESS | `EN_ADDRESS` | Composite house-number + street type and/or label |
| POSTAL_CODE | `EN_POSTAL_CODE` | Label required |
| CASE_NUMBER / FILE_NUMBER | `EN_CASE_NUMBER`, `EN_FILE_NUMBER` | Label + plausible value |
| DATE_OF_BIRTH / BIRTH_PLACE | `EN_BIRTH` | Birth context required |
| PASSPORT_NUMBER | `EN_PASSPORT` | Label required |
| NATIONAL_ID | `EN_NATIONAL_ID` | Labeled only; no format validator |
| PHONE_NUMBER | `EN_PHONE_CONTEXT` | English contact labels |
| BANK_ACCOUNT / FINANCIAL_IDENTIFIER | `EN_ACCOUNT` | Labeled only; REVIEW-class |
| EMAIL / URL / IBAN / CARD | Global detectors | English labels add context evidence |

`SIGNATURE` is not emitted for the printed name. `Signed by: Michael Jones` is
`PERSON_NAME` with `en_signature_context`.

---

## Legal Role Vocabulary

**Parties:** Claimant, Plaintiff, Defendant, Applicant, Respondent, Petitioner,
Appellant, Appellee, Complainant, Accused, Suspect, Witness, Deponent, Affiant

**Representatives:** Counsel, Counsel for the Claimant/Defendant/Applicant/
Respondent, Attorney, Attorney-at-Law, Lawyer, Solicitor, Barrister, Advocate,
Legal Representative, Representative

**Decision-makers:** Employment Judge, Judge, Justice, Magistrate, Arbitrator,
Mediator, Registrar, Clerk

**Experts:** Expert, Expert Witness, Consultant, Interpreter, Translator

These labels never become role-specific pseudonyms inside the detector.

---

## Person-Detection Evidence

A person candidate is emitted only with structure — not from a bare TitleCase
bigram.

Courtesy titles and legal-role labels may introduce a **titled name body**:

- `TITLE + INITIAL(S) + optional particle + surname` (`Mr J Allsop`, `Mr TJ McAuliffe`)
- `TITLE + surname` (`Mr Osborne`)
- `Employment Judge` / `Judge` / `Justice` / `Magistrate` / `Arbitrator` + surname

The emitted span is the name body. Titles and roles stay outside the span.
Single-letter initials are not globally repeatable. `McAuliffe`-style surnames
use a surname-token rule (`Mc`/`Mac` + capital), not a dictionary.

Evidence codes:

| Code | Typical Source |
|------|----------------|
| `en_legal_role_label` | Role adjacent to a name |
| `en_party_label` | Party / caption block |
| `en_counsel_context` | Counsel / solicitor / attorney |
| `en_title_context` | Mr, Mrs, Ms, Miss, Mx, Dr, Prof, Sir, Dame; also `Justice`, `Judge` |
| `en_signature_context` | Signed / Signed by / Signature / Name of Signatory |
| `en_legal_narrative_context` | Bounded cues (`the witness … stated`, `appeared`) |
| `en_first_name_lexicon` | Optional given-name signal |
| `en_matter_heading` | Nearby `IN THE MATTER OF` |
| `en_document_repeat` | Existing exact-surface repeat layer |

`identity_resolved` is always `false`. No deterministic coreference. No fuzzy
matching. Exact normalized repeats of an already-accepted full name may be
covered by the existing repeat layer. `John`, `Mr Smith`, `J. Smith`, and
`Johnny Smith` are not merged.

---

## Negative Evidence

Organisation / court / legal-term context suppresses weak PERSON interpretations:

- Supreme Court, High Court, Court of Appeal / Appeals, Employment Tribunal(s)
- Procedural headings (`JUDGMENT ON APPLICATION BY`, `NOTICE OF HEARING`)
- Standalone role words (`Counsel`, `Solicitor`, `Barrister`)
- Names inside trading-as / DBA constructions
- Ministry of Justice, Department of Justice, Legal Department
- Human Rights Act, Civil Procedure Rules
- United Kingdom, United States
- Company-suffix surfaces (`ACME Limited`)
- Street-type last tokens (`King Street` is not a person)

`Justice Brown` remains PERSON (title + name). `Ministry of Justice` does not
yield PERSON `Justice`.

---

## Legal References

Principle: **legal label + plausible value** ≫ naked alphanumeric.

Labels include Case/Claim/File/Reference/Matter/Docket/Proceeding No(Number),
Application No, Appeal No, `Reference`, and `Ref.` / `Ref`.

Labels require a trailing lexical boundary. `Ref` does not match inside
`referred` / `refused` / `reflected`.

A plausible value needs a digit or a reference separator (`/`, `-`, `.`).
Ordinary lowercase English words are not file numbers.

Rejected as case/file numbers: list markers (`1.`, `2.`), hierarchical paragraph
markers (`67.8.`, `102.4.1`), bare years (`2026`), short date-like pairs
(`10/20`).

Cited-authority context is an internal span annotation (`cited_authority_context`).
Strong citation evidence marks nested PERSON/COMPANY/ORG for policy KEEP.
KEEP is span-local: no coreference, no public/private-person inference.

---

## Courts and Institutions

Recognized structures include Supreme/High/District/Circuit/County/Family/
Commercial/Civil/Criminal Court, Court of Appeal(s), Employment Tribunal(s)/
Court, Labour Court, Administrative/Constitutional Court, Arbitration Tribunal.

Generic `the Tribunal` / `this Tribunal` / `the Court` are not promoted as
maskable institutions.

`IN THE … COURT` / `BEFORE THE … TRIBUNAL` headings are accepted.

`X Court` / `X Tribunal` requires a closed adjective set or a heading cue, so
`tennis court` is not a court.

`High Court` is `COURT_NAME`. If `Court` is immediately followed by a street
type (`High Court Road`), the span is not emitted as a court. No country is
asserted.

English-General courts default to **KEEP** transformation policy.

---

## Addresses

Composite evidence:

- house number + street name + street type (`25 King Street, London`)
- unit + street (`Flat 4, 18 Baker Street`)
- address labels (`Address`, `Address for Service`, `Postal Address`)

`Court` / `Ct` is **not** treated as a street type when the phrase is a legal
court (`High Court`). Postal-code-like values are emitted only under explicit
labels (Postal Code / Postcode / ZIP / ZIP Code). There is no world postcode
detector.

---

## Birth Information

`DATE_OF_BIRTH` requires birth context: Date of Birth, DOB, D.O.B., Birth Date,
Born, Born on.

`BIRTH_PLACE` requires Place of Birth, Birthplace, or Born in.

Negative contexts (not DOB): Hearing Date, Decision Date, Order Date, Filing
Date, Service Date, Contract Date, Execution Date.

Nationality is never inferred.

---

## Identity and Financial Identifiers

| Input | Result |
|-------|--------|
| `Passport No: X1234567` | `PASSPORT_NUMBER` candidate |
| Naked `X1234567` | not a passport |
| `National ID: …` / `ID Number: …` | `NATIONAL_ID` (labeled only; no format validator) |
| Unlabeled alphanumeric | not a national ID |

English `NATIONAL_ID` does **not** run the TCKN checksum. Invalid hard-validated
IBANs / cards remain IGNORE; English labels cannot rescue them.

---

## Companies and Organisations

Suffixes: `Ltd`, `Limited`, `LLC`, `LLP`, `Inc`, `Incorporated`, `Corp`,
`Corporation`, `PLC`, `P.L.C.`, `LP`, `L.P.`

The left-hand name must be proper-name or ALLCAPS structure (`Wechseln Limited`,
`ACME Limited`, `Brown & Co Ltd`). Ordinary prose that happens to end in
`limited` is not a company.

`t/a` / `trading as` / `doing business as` / `d/b/a` / `DBA` marks the following
business name as `COMPANY_NAME`. A human-looking surface inside that span
(`Andrew Hill` in `t/a the Andrew Hill Salon`) is not PERSON. The same surface
may still be PERSON in narrative.

---

## Conflict Resolution

English detectors are ranked above `LOCAL_NER_EN` and `STRUCTURAL_*` so the same
span does not become two UI findings.

| Surface | Preferred |
|---------|-----------|
| Employment Tribunals / London Employment Tribunal | COURT / institution |
| `t/a the Andrew Hill Salon` | COMPANY trading name |
| King Street | ADDRESS |
| Justice Brown | PERSON (title) |
| Ministry of Justice | ORGANISATION |
| High Court | COURT |
| High Court Road (no house number) | not a court; not a strong address |
| Dr Andrew Brown | PERSON |
| Brown & Co Ltd | COMPANY / ORGANISATION |

Turkish `_drop_courts_without_chamber` does **not** apply to `EN_*` courts.

---

## Local NER Coexistence

| Mode | Deterministic EN pack | spaCy `en_core_web_sm` |
|------|----------------------|------------------------|
| `RULES_ONLY` | yes | **no** (not imported) |
| `LOCAL_CONTEXT` | yes | yes, as a candidate generator |

Same-span PERSON from the pack and spaCy is merged by `_consolidate_candidates`.
Deterministic rank wins; NER may add `ner_overlap_existing_rule` evidence.
`RULES_ONLY` does not import spaCy.

---

## OCR Behaviour

Rules run on whatever text the existing OCR path already produced. No new OCR
engine. No LLM auto-correction. No fuzzy OCR matching in V1.

---

## Known Limitations

- English narrative person generation is bounded. Untitled names without
  role/title/signature/narrative cues are not swept.
- Initials and `Mc`/`Mac` surnames are generated only from titled or legal-role
  grammar.
- Labeled account / routing / sort-code values are not format-validated.
- `IN THE MATTER OF` only adds weak nearby evidence; following text is not
  classified as PII merely because of the heading.
- Detection may produce false positives and false negatives.

---

## Intentionally Unsupported

Do not treat these as implemented:

- unlabeled national IDs
- arbitrary passport formats without a label
- universal postal codes
- universal bank-account / sort-code / routing validation
- SSN
- UK National Insurance Number
- UK Companies House validation
- US jurisdiction-specific docket syntax
- full legal-citation parser (only a bounded `cited_authority_context` layer)
- UKEAT / EWHC as standalone identifiers
- deterministic coreference
- role identity linking (`[CLAIMANT_1]`)
- fuzzy person matching
- semantic health / special-category detection

---

## Rule Groups

Nine modular groups under `apps/api/app/detectors/en/`:

1. `structural.py` — dash/stacked party lines, caption `BETWEEN` / `v.` / `vs.`, matter heading
2. `legal_roles.py` — role + name
3. `legal_references.py` — labeled case/file references
4. `person_candidates.py` — titles, signatures, bounded narrative cues
5. `addresses.py` — composite address + labeled postcode
6. `identifiers.py` — DOB, birth place, passport, labeled national ID, phone labels, labeled accounts
7. `courts.py` — court / tribunal structures
8. `organisations.py` — company suffixes and institution phrases
9. `citations.py` — `cited_authority_context` on nested PERSON/COMPANY/ORG

Orchestrator: `detect_english_legal` registered as `EN_LEGAL_STRUCTURE` on
`ENGLISH_PACK`.

---

## Examples

**ACCEPT (typical):** `Claimant: John Smith`; `Mr John Smith`; `Case No: ABC-2026-001`;
`High Court`; `ACME Limited`; `25 King Street, London`; `Date of Birth: 12 March 1985`;
`Passport No: X1234567`; `Signed by: Michael Jones`; valid global email/IBAN/card.

**REVIEW (typical):** labeled `Account Number` / `Sort Code` / `Routing Number`
without a hard validator (`EN_ACCOUNT` skips the high-confidence floor).

**Intentionally ignored:** `Supreme Court` as PERSON; `1.` / `2026` as case
numbers; naked `X1234567` as passport; `Hearing Date: 12 March 1985` as DOB;
`IBAN: TR00…` (invalid) even with an English label; `John` / `J. Smith` as
linked identity.
