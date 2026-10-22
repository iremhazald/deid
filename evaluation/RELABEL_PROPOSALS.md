# Pending gold-set decisions

Applied in the gold corpus, with two rejections and one text replacement.

Rejected: `tr-mixed-hard-001` Şikayetçi stays `PERSON_NAME`. `tr-mixed-001`
Dilekçe sahibi stays `PERSON_NAME`. `tr-location-001` uses the fictional
name `Mavi Körfez Oteli` with `COMPANY_NAME`.

The table below is the proposal that was reviewed. It is not a second list
of pending edits.

A later decision took salary out of scope. The three amounts in
`tr-salary-001` are unlabeled. The row in "No change recommended" records
the earlier proposal.

## Proposed changes

| Document | Span | Current label | Proposed label | Reason |
|---|---|---|---|---|
| tr-contract-001 | 9:21 -> 10:22 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-contract-001 | 29:40 -> 30:41 | NATIONAL_ID | NATIONAL_ID | text[start:end] does not equal the gold string. |
| tr-contract-001 | 45:55 -> 46:56 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-contract-001 | 63:74 -> 64:75 | NATIONAL_ID | NATIONAL_ID | text[start:end] does not equal the gold string. |
| tr-court-001 | 44:52 -> 45:53 | CASE_NUMBER | CASE_NUMBER | text[start:end] does not equal the gold string. |
| tr-court-001 | 64:72 -> 65:73 | DECISION_NUMBER | DECISION_NUMBER | text[start:end] does not equal the gold string. |
| tr-court-001 | 81:92 -> 82:93 | PERSON_NAME | CLAIMANT_NAME | Davacı names the claimant. The role word stays outside the span. The recorded offsets also miss the string. |
| tr-court-001 | 102:115 | PERSON_NAME | DEFENDANT_NAME | Davalı names the defendant. |
| tr-address-001 | 10:23 | PERSON_NAME | LAWYER_NAME | Av. is a lawyer title and already sits outside the span. |
| tr-mixed-001 | 16:26 | PERSON_NAME | CLAIMANT_NAME | Dilekçe sahibi is the petitioner. |
| tr-mixed-001 | 54:92 -> 54:91 | ADDRESS | ADDRESS | text[start:end] does not equal the gold string. |
| tr-mixed-001 | 99:112 -> 98:111 | PHONE_NUMBER | PHONE_NUMBER | text[start:end] does not equal the gold string. |
| tr-mixed-001 | 123:143 -> 122:142 | EMAIL | EMAIL | text[start:end] does not equal the gold string. |
| tr-court-002 | 48:58 -> 47:57 | FILE_NUMBER | FILE_NUMBER | text[start:end] does not equal the gold string. |
| tr-court-002 | 70:81 -> 69:80 | PERSON_NAME | CLAIMANT_NAME | Alacaklı is the claiming party. There is no creditor type. The recorded offsets also miss the string. |
| tr-court-002 | 91:102 -> 90:101 | PERSON_NAME | DEFENDANT_NAME | Borçlu is the opposing party. There is no debtor type. The recorded offsets also miss the string. |
| tr-company-001 | 31:41 -> 30:40 | TAX_IDENTIFIER | TAX_IDENTIFIER | text[start:end] does not equal the gold string. |
| tr-company-001 | 47:60 -> 46:59 | COMPANY_NAME | COMPANY_NAME | text[start:end] does not equal the gold string. |
| tr-sensitive-001 | 28:39 | PATIENT_ID | OTHER_IDENTIFIER | PATIENT_ID is not an EntityType. A protocol number is an other identifier. |
| tr-sensitive-001 | 48:71 | HEALTH_INFORMATION | REMOVE | HEALTH_INFORMATION is not an EntityType. Diagnosis stays unlabeled. |
| tr-sensitive-001 | 79:94 | HEALTH_INFORMATION | REMOVE | HEALTH_INFORMATION is not an EntityType. Medication stays unlabeled. |
| tr-names-only-001 | 43:53 | PERSON_NAME | LAWYER_NAME | Av. is a lawyer title and already sits outside the span. |
| tr-names-only-001 | 86:98 -> 85:97 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-court-complex-001 | 74:83 | PERSON_NAME | DEFENDANT_NAME | Sanık names the defendant. |
| tr-court-complex-001 | 116:127 -> 115:126 | LAWYER_NAME | LAWYER_NAME | text[start:end] does not equal the gold string. |
| tr-court-complex-001 | 137:149 -> 136:148 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-address-complex-001 | 17:86 -> 17:85 | ADDRESS | ADDRESS | text[start:end] does not equal the gold string. |
| tr-address-complex-001 | 95:107 -> 94:106 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-address-complex-001 | 114:127 -> 113:126 | PHONE_NUMBER | PHONE_NUMBER | text[start:end] does not equal the gold string. |
| tr-financial-complex-001 | 68:100 -> 67:99 | IBAN | IBAN | text[start:end] does not equal the gold string. |
| tr-court-roles-001 | 55:69 -> 54:68 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-court-roles-001 | 78:88 -> 77:87 | WITNESS_NAME | WITNESS_NAME | text[start:end] does not equal the gold string. |
| tr-court-roles-001 | 105:113 -> 104:112 | EXPERT_NAME | EXPERT_NAME | text[start:end] does not equal the gold string. |
| tr-mixed-hard-001 | 11:19 | PERSON_NAME | CLAIMANT_NAME | Şikayetçi names the complainant. |
| tr-structural-labels-001 | 40:50 -> 39:49 | DATE | DATE_OF_BIRTH | The label is Doğum Tarihi. The recorded offsets also miss the string. |
| tr-structural-labels-001 | 60:73 -> 59:72 | PHONE_NUMBER | PHONE_NUMBER | text[start:end] does not equal the gold string. |
| tr-structural-labels-001 | 83:97 -> 82:96 | EMAIL | EMAIL | text[start:end] does not equal the gold string. |
| tr-url-ip-001 | 54:67 -> 53:66 | IP_ADDRESS | IP_ADDRESS | text[start:end] does not equal the gold string. |
| tr-url-ip-001 | 77:87 -> 75:85 | DATE | DATE | text[start:end] does not equal the gold string. |
| tr-vehicle-001 | 47:59 -> 46:58 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-vehicle-001 | 65:76 -> 64:75 | NATIONAL_ID | NATIONAL_ID | text[start:end] does not equal the gold string. |
| tr-signature-001 | 36:46 -> 35:45 | DATE | DATE | text[start:end] does not equal the gold string. |
| tr-signature-001 | 55:69 -> 54:68 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-customer-ids-001 | 39:46 -> 38:45 | OTHER_IDENTIFIER | OTHER_IDENTIFIER | text[start:end] does not equal the gold string. |
| tr-customer-ids-001 | 60:74 -> 59:73 | OTHER_IDENTIFIER | OTHER_IDENTIFIER | text[start:end] does not equal the gold string. |
| tr-bank-account-001 | 28:32 | BANK_ACCOUNT | REMOVE | A branch code is not a bank account. |
| tr-bank-account-001 | 45:54 -> 44:53 | BANK_ACCOUNT | BANK_ACCOUNT | text[start:end] does not equal the gold string. |
| tr-bank-account-001 | 71:90 -> 70:89 | CREDIT_CARD | CREDIT_CARD | text[start:end] does not equal the gold string. |
| tr-initials-001 | 19:23 | INITIALS | PERSON_NAME | INITIALS is a redaction strategy, not an entity type. |
| tr-initials-001 | 57:61 -> 56:60 | INITIALS | PERSON_NAME | INITIALS is a redaction strategy, not an entity type. The recorded offsets also miss the string. |
| tr-initials-001 | 63:74 -> 62:73 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-postal-code-001 | 27:58 -> 26:57 | ADDRESS | ADDRESS | text[start:end] does not equal the gold string. |
| tr-criminal-record-001 | 6:17 | PERSON_NAME | DEFENDANT_NAME | Sanık names the defendant. |
| tr-criminal-record-001 | 46:88 -> 45:87 | CRIMINAL_INFORMATION | REMOVE | CRIMINAL_INFORMATION is not an EntityType. The sentence stays unlabeled. The recorded offsets also miss the string. |
| tr-alias-001 | 57:67 -> 56:66 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-alias-001 | 73:84 -> 72:83 | NATIONAL_ID | NATIONAL_ID | text[start:end] does not equal the gold string. |
| tr-mixed-ultra-001 | 115:157 -> 115:156 | ADDRESS | ADDRESS | text[start:end] does not equal the gold string. |
| tr-mixed-ultra-001 | 164:177 -> 163:176 | PHONE_NUMBER | PHONE_NUMBER | text[start:end] does not equal the gold string. |
| tr-mixed-ultra-001 | 188:206 -> 187:205 | EMAIL | EMAIL | text[start:end] does not equal the gold string. |
| tr-mixed-ultra-001 | 221:233 -> 220:232 | LAWYER_NAME | LAWYER_NAME | text[start:end] does not equal the gold string. |
| tr-mixed-ultra-001 | 247:254 -> 246:253 | OTHER_IDENTIFIER | PROFESSIONAL_ID | Baro sicil is a professional register number. The recorded offsets also miss the string. |
| tr-mixed-ultra-001 | 265:274 -> 264:273 | PERSON_NAME | PERSON_NAME | text[start:end] does not equal the gold string. |
| tr-mixed-ultra-001 | 282:293 -> 281:292 | NATIONAL_ID | NATIONAL_ID | text[start:end] does not equal the gold string. |
| tr-mixed-ultra-001 | 303:312 -> 302:311 | WITNESS_NAME | WITNESS_NAME | text[start:end] does not equal the gold string. |
| tr-mixed-ultra-001 | 321:332 -> 320:331 | CRIMINAL_INFORMATION | REMOVE | CRIMINAL_INFORMATION is not an EntityType. The sentence stays unlabeled. The recorded offsets also miss the string. |
| tr-court-001 | (none) -> 0:34 | (unlabeled) | COURT_NAME | Specific court caption. It is unlabeled, so a court detection is a false positive. |
| tr-court-002 | (none) -> 0:35 | (unlabeled) | COURT_NAME | Specific court caption. It is unlabeled, so a court detection is a false positive. |
| tr-court-complex-001 | (none) -> 0:28 | (unlabeled) | COURT_NAME | Specific court caption. It is unlabeled, so a court detection is a false positive. |
| tr-mixed-ultra-001 | (none) -> 14:46 | (unlabeled) | COURT_NAME | Specific court caption. It is unlabeled, so a court detection is a false positive. |
| tr-address-complex-001 | (none) -> 80:85 | (unlabeled) | POSTAL_CODE | Postal code inside a street address is its own span and stays inside ADDRESS. |
| tr-location-001 | (none) -> 56:81 | (unlabeled) | COMPANY_NAME | Named business. Cities on the route stay LOCATION. |

## No change recommended

| Document | Span text | Current label | Reason |
|---|---|---|---|
| tr-court-roles-001 | Leyla Tunç | PERSON_NAME | Savcı has no entity type. Keep PERSON_NAME. |
| tr-court-roles-001 | Ayhan Eryılmaz | PERSON_NAME | Zabıt kâtibi has no entity type. Keep PERSON_NAME. |
| tr-court-complex-001 | Sibel Arslan | PERSON_NAME | Mağdur has no entity type. Keep PERSON_NAME. |
| tr-mixed-ultra-001 | Zehra Koç | PERSON_NAME | Mağdur has no entity type. Keep PERSON_NAME. |
| tr-names-only-001 | Emre Çelik | PERSON_NAME | Dr. is not a legal role. The title stays outside the span. |
| tr-salary-001 | 25.000 TL, 18.750 TL, 22.000 TL | SALARY_INFORMATION | Type is in the schema. Detectors currently drop it, so these three amounts stay false negatives. |
| tr-religious-political-001 | sosyalist | (unlabeled) | POLITICAL_INFORMATION is retired. Leave religion, union membership, and political opinion unlabeled. |
