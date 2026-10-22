# Annotation guidelines

Gold entities are what a careful reviewer would redact or replace in a legal
document. Offsets are Unicode code points, 0-based, and end-exclusive:
`text[start:end]` must equal the entity's `text`. A label is one `EntityType`
value from `apps/api/app/domain/models.py`. Do not invent a type.

These rules are the standard for the current Turkish gold set and for any
document added later. They are not a description of what the detectors do.
If a detector misses a span that these rules label, that miss stays a miss.

## Scope

DeID masks a defined list of personal data types. It does not claim to
comply with any data protection law.

A gold label must be one of these types. Health details, criminal history,
religion, trade-union membership, political opinion, and salary amounts are
not on the list. Leave that content unlabeled, even when it sits next to a
name or an identifier that is labeled.

Salary amounts are not masked and are not counted in the re-identification
risk score, so a salary combined with other details can still point to a
person.

Masked types, using the names in `EntityType`:

- Names: `PERSON_NAME`, `FIRST_NAME`, `LAST_NAME`, `ALIAS`, `CLAIMANT_NAME`,
  `DEFENDANT_NAME`, `LAWYER_NAME`, `JUDGE_NAME`, `WITNESS_NAME`,
  `EXPERT_NAME`
- Identifiers: `NATIONAL_ID`, `PASSPORT_NUMBER`, `TAX_IDENTIFIER`,
  `EMPLOYEE_ID`, `CUSTOMER_ID`, `PROFESSIONAL_ID`, `OTHER_IDENTIFIER`
- Contact and place: `ADDRESS`, `EMAIL`, `PHONE_NUMBER`, `POSTAL_CODE`,
  `BIRTH_PLACE`, `VEHICLE_PLATE`
- Financial: `IBAN`, `BANK_ACCOUNT`, `CREDIT_CARD`, `FINANCIAL_IDENTIFIER`
- Case and court: `COURT_NAME`, `CASE_NUMBER`, `FILE_NUMBER`,
  `DECISION_NUMBER`
- Other recorded types: `DATE`, `DATE_OF_BIRTH`, `LOCATION`, `COMPANY_NAME`,
  `ORGANISATION`, `IP_ADDRESS`, `URL`, `SYSTEM_URL`, `UETS`, `UYAP_ACCESS`,
  `QR_CODE`, `SIGNATURE`, `PORT_NUMBER`, `MONEY_AMOUNT`

`drop_retired_detections` in `apps/api/app/detectors/registry.py` removes
`MONEY_AMOUNT`. The name "retired" comes from that constant,
`RETIRED_DETECTION_TYPES`. There is no political-opinion type. Do not label
political opinion, religion, ethnicity, or trade-union membership. The
changelog records that this category was removed with the old language-model
review, and the enum value has now been removed as well.

There is no salary type. Do not label a pay amount. `DATE`, `LOCATION`,
`SYSTEM_URL`, `PORT_NUMBER`, and `MONEY_AMOUNT` may be labeled. Their
default recommendation is to leave the text visible unless a reviewer
chooses otherwise.

## What is labeled

Label a span when it identifies a natural person, a specific case, or a
contact, account, or identifier that belongs to a person or a private party.
Label a specific court caption as `COURT_NAME`. Label a company or a private
organisation that is a party, an employer, or the sender of a letter.

## What is not labeled

- Statute and article numbers: `4857 sayılı Kanun`, `m. 17`, `section 12`.
- Page counts and the noun "page": `148 pages`, `Page 4`, `sayfa 12`.
- A word that is also a name, when it is used as an ordinary noun: `bahar
  ayları`, `deniz kenarı`, `the hope of settlement`, `a rose garden`.
- A court or public institution mentioned only as the source of a rule, not
  as the forum of a case and not as a party: `İş mahkemeleri 4857 sayılı
  Kanun'a göre karar verir.`
- A checksum that fails. A number that looks like a TCKN, an IBAN, or a card
  number, but fails the production validator, is not that type and is not
  `OTHER_IDENTIFIER`.
- Prices, tax rates, and invoice totals that are not a person's pay.
- Religion, ethnicity, trade-union membership, political opinion, health
  details, criminal history, and salary amounts. They are outside the scope
  list above.
- A role title with no name: `Dr.`, `Av.`, `the claimant`, `savcı`.

A negative document contains none of the labeled categories. It may contain
the look-alikes above.

## Span boundaries

- Include the value only. Leave labels, titles, and punctuation outside the
  span unless the punctuation is inside the value (`A.Ş.`, `34 ABC 1234`).
- Titles that stay outside the name: `Dr.`, `Av.`, `Prof.`, `Mr`, `Mrs`,
  `Ms`, `Justice`, `Sayın`, `Hâkim`, `Yargıç`. `Sayın Av. Zeynep Arslan` →
  `Zeynep Arslan`.
- Phone and mail labels stay outside: `Tel:`, `GSM:`, `Telefon:`, `e-posta:`.
  `tel: 0216 555 1234` → `0216 555 1234`.
- Identity labels stay outside: `TCKN:`, `TC:`, `TC Kimlik:`, `IBAN:`,
  `Esas No:`, `E.`, `K.`, `dosya no:`.
- Turkish case suffixes stay outside the name. The span is the stem before
  the apostrophe. `Ahmet'in` → `Ahmet`. `Kaya'ya` → `Kaya`. A name written
  without an apostrophe but with a suffix glued on (`Kayanın`) is still the
  stem only when the suffix is a clear case ending; if the boundary is
  uncertain, label the whole token and note it.
- Internal spaces, dashes, and line breaks that belong to one identifier stay
  inside the span. `TR33 0006 1005 1978 6457 8413 26` is one IBAN. A TCKN
  broken across a line break is one `NATIONAL_ID`.
- Do not include a trailing comma, period, or closing parenthesis.
- ALL CAPS and ASCII-folded Turkish names are labeled as written:
  `PINAR YILMAZ`, `Sukru Ozturk`.
- A full name is one span. Do not also label the given name and the surname
  inside it. A later surname alone (`Kaya` after `Mehmet Kaya`) is
  `LAST_NAME`. A given name alone is `FIRST_NAME`.
## Nested spans

Nested spans are allowed when two in-scope types describe the same text.
A postal code inside a street address is part of the `ADDRESS` span and is
also its own `POSTAL_CODE` span. Do not nest two spans of the same type.

## Role names

Use a role type only when the role is clear from the text in that clause.
The role word stays outside the span. If the schema has no type for the
role, use `PERSON_NAME`.

### Turkish

| Role words | Type |
|---|---|
| Davacı, alacaklı | `CLAIMANT_NAME` |
| Davalı, borçlu, sanık | `DEFENDANT_NAME` |
| Av., avukat, müdafi, and vekil when the clause shows a lawyer acting in proceedings | `LAWYER_NAME` |
| Vekil appointed in a vekâletname | `PERSON_NAME` |
| Hâkim, yargıç | `JUDGE_NAME` |
| Tanık | `WITNESS_NAME` |
| Bilirkişi | `EXPERT_NAME` |
| Şikayetçi, mağdur, dilekçe sahibi, savcı, zabıt kâtibi | `PERSON_NAME` |

A vekil named in a vekâletname is the appointed agent, not a lawyer, even
when a lawyer could have been appointed. A vekil who appears as counsel in
a hearing, a petition, or a judgment is `LAWYER_NAME`.

### English

| Role words | Type |
|---|---|
| Claimant, Plaintiff, Petitioner, and Applicant when the person is a party to legal proceedings | `CLAIMANT_NAME` |
| Defendant, Accused, and Respondent when the person is a party to legal proceedings | `DEFENDANT_NAME` |
| Solicitor, Counsel, Barrister, and Attorney when it means a legal professional | `LAWYER_NAME` |
| Judge, Justice, Master, Magistrate | `JUDGE_NAME` |
| Witness | `WITNESS_NAME` |
| Expert | `EXPERT_NAME` |
| Attorney-in-fact, and an attorney appointed under a power of attorney | `PERSON_NAME` |
| Prosecutor, District Attorney, State's Attorney, Crown Prosecutor, and similar prosecutor titles | `PERSON_NAME` |
| Complainant, Victim, Clerk | `PERSON_NAME` |
| Appellant, Appellee | The first-instance role, when the text states it. Otherwise `PERSON_NAME` |
| Arbitrator, Mediator | `PERSON_NAME` |
| A job applicant, or a survey respondent | `PERSON_NAME` |

`Master` and `Justice` count only when they are the judicial title.
`Appellant` and `Appellee` do not reveal who filed the original claim: use
`CLAIMANT_NAME` or `DEFENDANT_NAME` only when the text states that
first-instance role.

There is no schema type yet for a criminal complainant, a victim, the author
of a petition (`dilekçe sahibi`), a prosecutor, a clerk, an arbitrator, or a
mediator. Those names stay `PERSON_NAME` until the schema has types for
them. `Dr.`, `Prof.`, `mimar`, and `mühendis` are not legal roles. A role
phrase with no person, such as `Hâkimler ve Savcılar Kurulu` or `the
Claimant's case`, is not a name.

## Checksums

`NATIONAL_ID`, `IBAN`, and `CREDIT_CARD` values must pass the production
validators in `app/detectors/checksum.py` (`validate_tckn`, `validate_iban`,
`validate_luhn`). Spaces and dashes are removed before the check. A failed
check is not labeled.

## Entity types

### PERSON_NAME

A person's name with no role type, or a role that has no type. Span is the
name only.

Correct: `Dr. Emre Çelik` → `Emre Çelik`.
Incorrect: `Dr. Emre Çelik` including `Dr.`.
Edge: `Deniz` is a name in `mühendis Deniz Öztürk` and is not a name in
`deniz kenarı`.

### FIRST_NAME

A given name used alone. Not the given name inside a full-name span.

Correct: `Mehmet` in `Mehmet called the office` after the person is
identified.
Incorrect: `Mehmet` inside `Mehmet Kaya` when the full name is already a span.

### LAST_NAME

A surname used alone.

Correct: `Kaya` in a later sentence after `Mehmet Kaya`.
Incorrect: `Kaya` inside the full name `Mehmet Kaya`.
Edge: `Kaya'ya` → `Kaya`.

### ALIAS

A stated nickname or false name, not the legal name.

Correct: `takma ad: 'Kartal'` → `Kartal`.
Incorrect: the legal name on the same line, which stays `PERSON_NAME` or a
role type.

### NATIONAL_ID

A national identity number that passes its validator. Turkish values are
11-digit TCKNs and must pass `validate_tckn`.

Correct: `TCKN: 12345678950` → `12345678950`.
Incorrect: `TC: 12345678950` including `TC:`, or an 11-digit number that
fails the checksum.
Edge: spaces, dashes, and a line break inside one number stay in the span.

### PASSPORT_NUMBER

A passport number, not a national ID.

Correct: `Pasaport: U12345678` → `U12345678`.
Incorrect: labeling a TCKN as a passport.

### TAX_IDENTIFIER

A tax number (VKN and equivalents), not a national ID.

Correct: `vergi no: 1234567890` → `1234567890`.
Incorrect: an 11-digit TCKN.

### EMPLOYEE_ID

An employee or personnel number.

Correct: `sicil: P-5678` → `P-5678`.
Incorrect: a customer number.

### CUSTOMER_ID

A customer number assigned to a person or account.

Correct: `Müşteri No: C-2023-45678` → `C-2023-45678`.
Incorrect: an order number or a tracking code (`OTHER_IDENTIFIER`).

### ADDRESS

A street, building, or delivery address that locates a person or a private
party. The postal code, if present, stays inside this span and is also
`POSTAL_CODE`.

Correct: `Cumhuriyet Bulvarı No:45 Daire:12 Çankaya/Ankara`.
Incorrect: the city alone when it is only a travel stop (`LOCATION`), or a
trailing comma.
Edge: a city inside the street address stays in the address. The same city
named as a route stop is `LOCATION`.

### EMAIL

Any email address, including a shared inbox.

Correct: `ahmet.yilmaz@example.com`, `info@sirket.com.tr`.
Incorrect: the label `e-posta:`.

### PHONE_NUMBER

A telephone number, including country code, trunk prefix, and separators as
written.

Correct: `+90 532 123 4567`, `(0216) 444 5678`.
Incorrect: `Tel:` or `GSM:`, or a short extension with no subscriber number.
Edge: a UK drama number (`07700 900000`–`07700 900999`) and a US `555-0100`
to `555-0199` number are labeled when they appear as phone numbers.

### POSTAL_CODE

The postal code itself. Also label the surrounding street address when there
is one.

Correct: `06100` in `Posta kodu: 06100`.
Incorrect: a year, a case number, or a page count.

### IP_ADDRESS

An IP address in a log or a record about a person or their system.

Correct: `192.168.1.100`.
Incorrect: a version number such as `1.2.3`.

### URL

A web address that is not a court or government system access string.

Correct: `https://portal.example.com/login`.
Incorrect: a UYAP access string (`UYAP_ACCESS`) or a bare institution name.

### IBAN

An IBAN that passes `validate_iban`, including internal spaces and dashes.

Correct: `TR33 0006 1005 1978 6457 8413 26`.
Incorrect: the words after it (`numaralı hesaba yapılacaktır`), or a string
that fails MOD-97.

### BANK_ACCOUNT

A bank account number that is not an IBAN. A branch code alone is not an
account.

Correct: `Hesap no: 567890123` → `567890123`.
Incorrect: `Şube kodu: 1234` → `1234`.

### CREDIT_CARD

A full card number that passes the Luhn check. The last four digits alone
are not a card number.

Correct: `5432 1098 7654 3006`.
Incorrect: `card ending 3006`.

### FINANCIAL_IDENTIFIER

A financial identifier that is not an IBAN, an account number, or a card.

Correct: a stated SWIFT or customer-bank reference that is not one of those
three.
Incorrect: an IBAN.

### Salary

Not in the scope list. Do not label a pay amount, including in a payroll
document or an employment contract. The amounts stay in the text.

There is no salary entity type. Do not use `MONEY_AMOUNT` for pay.

### Political opinion

Not in the scope list. Do not label political opinion, religion, ethnicity,
or trade-union membership. There is no political-opinion entity type.

### COURT_NAME

The proper name of the specific court that is the forum of the document.
`COURT_NAME` labels the full caption for detection. Include the city, the
ordinal, and the chamber. Stop before the docket clause. Masking only part
of that caption, such as the court number, is a masking-policy decision. It
does not change the label or the span.

Correct: `İstanbul 2. Asliye Hukuk Mahkemesi`.
Incorrect: `İstanbul 2. Asliye Hukuk Mahkemesi, Esas No: 2021/456`, or
`İş mahkemeleri` in a sentence about a statute.
Edge: a high court named as the forum is `COURT_NAME`. The same words used
only to cite a published rule are not labeled.

### CASE_NUMBER

The case or esas number, without the label.

Correct: `Esas No: 2021/456` → `2021/456`. `E.2019/234` → `2019/234`.
Incorrect: `E.` or `Esas No:`.

### FILE_NUMBER

A file or dosya number, without the label.

Correct: `dosya no: 2020/12345` → `2020/12345`.
Incorrect: a case number that the document calls esas (`CASE_NUMBER`).

### DECISION_NUMBER

A karar number, without the label.

Correct: `Karar No: 2022/789` → `2022/789`. `K.2021/567` → `2021/567`.
Incorrect: `K.` or `Karar No:`.

### JUDGE_NAME

The judge's name. The title stays outside.

Correct: `Yargıç: Hasan Kılıç` → `Hasan Kılıç`.
Incorrect: `Yargıç: Hasan Kılıç` as `PERSON_NAME`, or including `Yargıç:`.

### LAWYER_NAME

Counsel's name. `Av.` and `müdafi` stay outside.

Correct: `müdafi: Av. Murat Şahin` → `Murat Şahin`.
Incorrect: `Av. Murat Şahin` including `Av.`, or `PERSON_NAME` when the
clause calls the person counsel.

### CLAIMANT_NAME

The claiming party when the text itself shows that role: davacı, alacaklı,
claimant, plaintiff, applicant. A criminal complainant (`şikayetçi`) and a
petition author (`dilekçe sahibi`) stay `PERSON_NAME`.

Correct: `Davacı Mehmet Kaya` → `Mehmet Kaya`.
Incorrect: `Şikayetçi: Cem Acar` as `CLAIMANT_NAME`, or including `Davacı`.

### DEFENDANT_NAME

The opposing or accused party: davalı, sanık, borçlu, defendant, respondent.

Correct: `Sanık: Ali Demir` → `Ali Demir`.
Incorrect: `PERSON_NAME` for that span.

### WITNESS_NAME

A witness.

Correct: `tanık: Gökhan Şen` → `Gökhan Şen`.
Incorrect: a party or the expert.

### EXPERT_NAME

A named expert. A professional title stays outside.

Correct: `bilirkişi: Dr. Canan Öz` → `Canan Öz`.
Incorrect: including `Dr.`, or using `EXPERT_NAME` for every physician.

### SIGNATURE

A signature mark that is not itself the readable name. A readable name in a
signature block is the person or role type, not `SIGNATURE`.

Correct: an unreadable `imza` graphic described as a signature mark.
Incorrect: `İmza: [Pınar YILMAZ imzası]` labeled as `SIGNATURE` instead of
`Pınar YILMAZ` as `PERSON_NAME`.

### QR_CODE

The encoded payload of a QR code when that payload is personal or is an
access token. Decorative text around a code is not the code.

### UYAP_ACCESS

A UYAP access address or access token.

Correct: a `uyap.gov.tr` access URL.
Incorrect: an ordinary company URL (`URL`).

### COMPANY_NAME

A company that is a party, an employer, or a named business. Include the
legal suffix.

Correct: `ABC Teknoloji A.Ş.`, `XYZ Ltd. Şti.`.
Incorrect: a bar association (`ORGANISATION`) or a court (`COURT_NAME`).

### ORGANISATION

An organisation that is not a commercial company: a bar, a chamber, a
union, a hospital, a public body named as a party or an addressee.

Correct: `Türkiye Barolar Birliği`.
Incorrect: `ABC Teknoloji A.Ş.` (`COMPANY_NAME`), or a court
(`COURT_NAME`).
Edge: a public body mentioned only as the author of a statute is not
labeled.

### LOCATION

A place that is not a street address: a city on a route, a birth city with
no street, a region.

Correct: `İstanbul` in `Gezi rotası: İstanbul → Ankara`.
Incorrect: `Çankaya/Ankara` inside a street address (`ADDRESS`), or a court
name.

### DATE

A calendar date that is not a date of birth: a signature date, a hearing
date, a log date.

Correct: `Tarih: 12.12.2023` → `12.12.2023`.
Incorrect: `Doğum Tarihi: 15.03.1985` (`DATE_OF_BIRTH`), or a case number.

### DATE_OF_BIRTH

A date the document identifies as a birth date.

Correct: `Doğum Tarihi: 15.03.1985` → `15.03.1985`.
Incorrect: the same digits labeled `DATE`.

### BIRTH_PLACE

The place the document identifies as a birthplace, when it is not only part
of a street address.

Correct: `doğum yeri: Sivas` → `Sivas`.
Incorrect: a city that is only the current residence (`ADDRESS` or
`LOCATION`).

### VEHICLE_PLATE

A vehicle plate as written, including spaces.

Correct: `34 ABC 1234`.
Incorrect: the word `plaka` or a product code.

### PROFESSIONAL_ID

A professional register number: bar number, medical register, similar.

Correct: `baro sicil: B-12345` → `B-12345`.
Incorrect: an employee payroll number (`EMPLOYEE_ID`).

### PORT_NUMBER

A network port tied to a person's system or a log about that person. A
generic service port in a manual (`port 443`) is not labeled.

### MONEY_AMOUNT

Do not use this for pay or for an ordinary price.
The detectors retire this type. Leave ordinary amounts unlabeled.

### SYSTEM_URL

A government or court system URL that is not UYAP.

Correct: a justice-portal URL for a named case.
Incorrect: `https://portal.example.com/login` (`URL`).

### UETS

A national electronic-notification (UETS) address or identifier.

Correct: the UETS address string, without the label `UETS:`.
Incorrect: an ordinary email (`EMAIL`).

### OTHER_IDENTIFIER

A person- or case-linked identifier with no more specific type: a driving
licence number, an order number, a tracking code, a patient protocol number.

Correct: `ehliyet: A1234567890123` → `A1234567890123`. `prot. no:
P-2023-5678` → `P-2023-5678`.
Incorrect: a TCKN, an IBAN, or a 4-digit branch code.

## Schema gaps

Do not invent labels for these. Use `PERSON_NAME` for the person, and leave
the descriptive phrase unlabeled.

- Criminal complainant (`şikayetçi`), victim (`mağdur`), petition author
  (`dilekçe sahibi`), prosecutor (`savcı`), and clerk (`zabıt kâtibi`).
- Diagnosis, medication, and criminal sentences. They are out of scope.
- Initials. `M.K.` is `PERSON_NAME`. `INITIALS` is a redaction strategy, not
  an entity type.
