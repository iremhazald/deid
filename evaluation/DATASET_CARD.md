# Dataset card

Version 2.0. The corpus is `evaluation/test_corpus.jsonl`. Annotation rules are
in [ANNOTATION_GUIDELINES.md](ANNOTATION_GUIDELINES.md). The review file is
[REVIEW.md](REVIEW.md).

Every document is synthetic. Offsets are Unicode code points, 0-based, and
end-exclusive: `text[start:end]` equals the gold text. A label is one
`EntityType`. DeID does not claim compliance with any data protection law.

## Composition

112 documents. Turkish 62, English 50. Each language has a dev split and a
test split of 15 documents.

| Language | Split | Documents | Easy | Medium | Hard | Gold spans |
| --- | --- | --- | --- | --- | --- | --- |
| Turkish | dev | 47 | 19 | 18 | 10 | 191 |
| Turkish | test | 15 | 5 | 7 | 3 | 95 |
| English | dev | 35 | 14 | 14 | 7 | 209 |
| English | test | 15 | 6 | 6 | 3 | 86 |

Turkish spans are 286. English spans are 295. The Turkish dev split contains
the original 34 documents plus later dev documents. `tr-test-medical-001` and
`tr-test-contract-001` were written as test documents, then moved to dev after
their detector results had been seen. `tr-test-medical-002` (medium medical
report) and `tr-test-contract-002` (hard employment contract) replace them on
the test split.

Person-name spans, counting `PERSON_NAME`, `ALIAS`, `CLAIMANT_NAME`,
`DEFENDANT_NAME`, `LAWYER_NAME`, `JUDGE_NAME`, `WITNESS_NAME`, and
`EXPERT_NAME`:

| Language | Dev | Test | Total |
| --- | --- | --- | --- |
| Turkish | 60 | 17 | 77 |
| English | 74 | 33 | 107 |

`COURT_NAME` and `COMPANY_NAME` are not in that total.

Turkish gold counts: `PERSON_NAME` 45, `CLAIMANT_NAME` 6, `DEFENDANT_NAME` 8,
`LAWYER_NAME` 7, `JUDGE_NAME` 4, `WITNESS_NAME` 4, `EXPERT_NAME` 2, `ALIAS` 1,
`EMAIL` 25, `PHONE_NUMBER` 24, `IBAN` 31, `NATIONAL_ID` 24, `ADDRESS` 19,
`CASE_NUMBER` 16, `DATE_OF_BIRTH` 16, `COURT_NAME` 10, `COMPANY_NAME` 7,
`FILE_NUMBER` 5, `OTHER_IDENTIFIER` 5, `DECISION_NUMBER` 4, `LOCATION` 4,
`EMPLOYEE_ID` 3, `ORGANISATION` 3, `DATE` 2, `POSTAL_CODE` 2, and one each of
`BANK_ACCOUNT`, `CREDIT_CARD`, `CUSTOMER_ID`, `IP_ADDRESS`, `PASSPORT_NUMBER`,
`PROFESSIONAL_ID`, `TAX_IDENTIFIER`, `URL`, `VEHICLE_PLATE`.

English gold counts: `PERSON_NAME` 51, `EMAIL` 37, `PHONE_NUMBER` 35,
`ADDRESS` 32, `IBAN` 31, `CASE_NUMBER` 19, `CLAIMANT_NAME` 15,
`DEFENDANT_NAME` 15, `LAWYER_NAME` 15, `DATE_OF_BIRTH` 14, `NATIONAL_ID` 10,
`PASSPORT_NUMBER` 10, `JUDGE_NAME` 7, `WITNESS_NAME` 4.

Documents with no gold span:

| Id | Language | Split |
| --- | --- | --- |
| `tr-empty-001` | Turkish | dev |
| `tr-test-neg-salary-001` | Turkish | test |
| `tr-test-neg-salary-002` | Turkish | test |
| `tr-test-neg-checksum-001` | Turkish | test |
| `tr-test-neg-statute-001` | Turkish | test |
| `en-dev-neg-statute-001` | English | dev |
| `en-dev-neg-invoice-001` | English | dev |
| `en-dev-neg-checksum-001` | English | dev |
| `en-test-neg-salary-001` | English | test |
| `en-test-neg-salary-002` | English | test |

### Document types

| Turkish document type | Dev | Test |
| --- | --- | --- |
| address | 1 | 0 |
| bilirkişi raporu | 0 | 1 |
| case_file | 1 | 0 |
| complaint | 1 | 0 |
| contact | 1 | 0 |
| contract | 4 | 0 |
| correspondence | 2 | 0 |
| court | 1 | 0 |
| court decision | 0 | 1 |
| demand letter | 1 | 0 |
| document | 2 | 0 |
| email correspondence | 3 | 1 |
| employment contract | 2 | 1 |
| form | 4 | 0 |
| generic | 1 | 0 |
| hearing minutes | 1 | 1 |
| hr_file | 1 | 0 |
| icra | 1 | 1 |
| ihtarname | 0 | 1 |
| investigation | 1 | 0 |
| invoice | 1 | 0 |
| log | 1 | 0 |
| medical | 2 | 0 |
| medical report | 2 | 1 |
| minutes | 1 | 0 |
| payroll | 1 | 1 |
| petition | 3 | 2 |
| power of attorney | 0 | 1 |
| privacy notice | 1 | 2 |
| report | 1 | 0 |
| settlement agreement | 0 | 1 |
| ticket | 1 | 0 |
| travel | 1 | 0 |
| verdict | 4 | 0 |

| English document type | Dev | Test |
| --- | --- | --- |
| NDA | 3 | 1 |
| board minutes | 2 | 1 |
| court order | 3 | 1 |
| demand letter | 3 | 1 |
| email thread | 2 | 2 |
| employment agreement | 4 | 2 |
| engagement letter | 3 | 1 |
| judgment extract | 2 | 1 |
| letter before action | 3 | 1 |
| privacy notice | 2 | 1 |
| settlement agreement | 3 | 1 |
| share purchase extract | 2 | 1 |
| witness statement | 3 | 1 |

## What the gold labels

The guidelines are the labeling standard. They are independent of what a
detector currently returns. A miss against these labels stays a miss.

Health details, criminal history, religion, trade-union membership, political
opinion, and salary amounts are out of scope. They stay in the text without a
label, and salary amounts are not counted in the re-identification score.
`tr-salary-001` still contains 25.000 TL, 18.750 TL, and 22.000 TL.
`tr-test-contract-002` still contains 54.500 TL. English employment agreements
still contain a yearly pay figure. `tr-test-medical-002` still contains the
diagnosis "akut farenjit". The empty salary notes above are the same choice
on a page that names nobody.

Titles stay outside the name span. A Turkish suffix stays outside the name
(`Ahmet'in` labels `Ahmet`). A role phrase with no person is not a name.
`COURT_NAME` is the full court caption. A role type is used only when the
role is clear from the text. A failed checksum is not `NATIONAL_ID`, `IBAN`,
or `CREDIT_CARD`, and it is not `OTHER_IDENTIFIER`. Nested spans are allowed,
including a postal code inside an address.

## How the identifiers were built

Turkish national IDs pass `validate_tckn`. English national IDs are not run
through that function.

The six English Social Security-shaped values use area 666, a group other
than 00, and a serial other than 0000 (`666-11-1001` through `666-16-1006`).
The Social Security Administration does not assign area 000, area 666, or
area 900–999, and it does not assign group 00 or serial 0000
(<https://www.ssa.gov/employer/randomizationfaqs.html>). Numbers beginning
with 9 are Individual Taxpayer Identification Numbers, so this set does not
use them (<https://www.irs.gov/tin/taxpayer-identification-numbers-tin>,
IRS Publication 1915).

The four English national-insurance-shaped values use prefix ZZ and a suffix
in A–D (`ZZ100000A` through `ZZ100003D`). HMRC does not use the prefixes BG,
GB, KN, NK, NT, TN, or ZZ; D, F, I, Q, U, and V do not appear in either
letter; O is not used as the second letter; the suffix is A–D
(<https://www.gov.uk/hmrc-internal-manuals/national-insurance-manual/nim39110>).

Every IBAN passes the ISO 13616 MOD-97 check in `validate_iban`. Twenty-nine
Turkish IBANs use the five-digit bank code 99999, which is not a code on the
TCMB Ödeme Sistemleri Katılımcıları list for 2026. The two older Turkish
IBANs use 00061 and 00062. All 31 English IBANs are GB, length 22, with bank
identifier TEST, sort code 009900, and an eight-digit account. TEST is not a
real bank code, and the sort code is the fictional 009900. No real bank code
or SWIFT example is used.

English phones are either in the Ofcom drama range `07700 900000`–`07700 900999`
(seven numbers) or a US number whose exchange is 555 and whose line is in
`0100`–`0199` (twenty-eight numbers, all `202-555-01xx`). Email domains are
`example.com` (19) and `example.org` (18).

## Review

`REVIEW.md` has the text of ten Turkish test documents and ten English test
documents, with an empty table for each language. Agreement is not measured.
The tables stay empty until they are filled in.

## How the numbers were measured

The CI gate is Turkish only, on a strict match: same type, greedy, IoU at
least 0.5. The thresholds are precision at least 75%, recall at least 50%,
and recall at least 95% for `NATIONAL_ID`, `IBAN`, `EMAIL`, and
`PHONE_NUMBER`. A person-family match is printed and is not gated. English
is scored on the product path and is not added to the Turkish total. A
separate English gate for those four types is the intended next check. It is
not armed.

A category, difficulty, or document type with fewer than 10 gold entities is
marked `low sample`. The flag does not fail CI.

### Metric history

These figures are Turkish strict matches. The source column says whether the
move came from the gold set or from the system.

| Stage | Precision | Recall | Counts | Source |
| --- | --- | --- | --- | --- |
| Legacy harness, original 34 documents, before the relabel | 80.85% | 62.81% | 121 gold spans | Baseline on that gold set |
| After the Turkish relabel | 88.30% | 68.03% | 122 gold spans | Gold. Detectors, rules, and thresholds did not change. |
| After the three `SALARY_INFORMATION` labels left `tr-salary-001` | 88.30% | 69.75% | 83 true positives, 11 false positives, 36 false negatives | Gold scope. The amounts stayed in the text. Removing the salary type from the program did not move the harness. |
| Legacy harness on the current 62 Turkish documents | 86.17% | 76.22% | 218 / 35 / 68 | Gold. The harness was the previous detector list. |
| Product rules-only path, 22 October | 90.83% | 76.22% | 218 / 22 / 68 | Measurement. Recall is the same. The precision move is the product merge dropping false positives. |
| After the 11 November detector changes | 87.35% | 77.27% | 221 / 32 / 65 | System. The gold file did not change. |

On the 34-document set, after the salary labels were removed, the ungated
person-family match was precision 89.36% and recall 70.59% (84 / 10 / 35).
On the 22 October product path the ungated Turkish person-family match was
precision 93.75% and recall 78.67%. After the 11 November detectors it is
precision 94.86% and recall 83.92% (240 / 13 / 46). That move is the system.

The same gold file, split by `dev` and `test`, shows where that system change
landed. Turkish test strict precision moved from 90.48% to 93.10% and recall
from 80.00% to 85.26% (76 / 8 / 19 to 81 / 6 / 14). Turkish dev strict
precision moved from 91.03% to 84.34% and recall from 74.35% to 73.30%
(142 / 14 / 49 to 140 / 26 / 51). The test split improved on both precision
and recall. The dev precision drop is extra false positives.

The sentence-final email change is a system change. On the 34-document set
the legacy numbers stayed 88.30% precision and 69.75% recall, because that
set has no address at the end of a sentence. Turkish email recall on the
current product path is 25/25.

English on the product rules-only path, report only, after the 11 November
detectors: precision 72.89%, recall 41.02% (121 true positives, 45 false
positives, 174 false negatives). Person-family precision 86.14%, recall
48.47% (143 / 23 / 152). Against the 22 October path, strict recall is
unchanged and there is one more false positive; person-family recall gained
one true positive. Those moves are the system. Email recall is 100% (37).
Phone recall is 0% (0/35). IBAN recall is 77.42% (24/31). National-id recall
is 60% (6/10). Those six counted hits are the phrase "national identifier"
followed by an area-666 number. The rule takes "national id" as a prefix of
"identifier" and returns "entifier" plus the number. IoU with the gold number
is 0.55, so the pair counts, and the wider span is not a second false
positive. The four misses are the ZZ numbers introduced as "national
insurance number". Arming a 95% English gate on this path would fail CI.
`--legacy` does not score English.
