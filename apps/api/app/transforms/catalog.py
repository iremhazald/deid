from __future__ import annotations

from app.domain.models import EntityType, TransformationStrategy
from app.transforms.tag_taxonomy import (
    TAG_SPECS,
    placeholder_prefix as taxonomy_placeholder_prefix,
    serialize_taxonomy,
)

PERSON_TYPES = {
    EntityType.PERSON_NAME,
    EntityType.FIRST_NAME,
    EntityType.LAST_NAME,
    EntityType.ALIAS,
    EntityType.JUDGE_NAME,
    EntityType.LAWYER_NAME,
    EntityType.CLAIMANT_NAME,
    EntityType.DEFENDANT_NAME,
    EntityType.WITNESS_NAME,
    EntityType.EXPERT_NAME,
}

ROLE_TYPED = {
    EntityType.CLAIMANT_NAME,
    EntityType.DEFENDANT_NAME,
    EntityType.WITNESS_NAME,
    EntityType.EXPERT_NAME,
    EntityType.LAWYER_NAME,
}

COMMON = {
    TransformationStrategy.REDACT,
    TransformationStrategy.PLACEHOLDER,
    TransformationStrategy.KEEP,
}

PERSON_STRATEGIES = COMMON | {
    TransformationStrategy.INITIALS,
}

IDENTIFIER_STRATEGIES = COMMON | {TransformationStrategy.PARTIAL_MASK}
ADDRESS_STRATEGIES = COMMON | {TransformationStrategy.PARTIAL_MASK}
DATE_STRATEGIES = COMMON
BIRTH_DATE_STRATEGIES = COMMON | {TransformationStrategy.PARTIAL_MASK}
COURT_STRATEGIES = {
    TransformationStrategy.REDACT,
    TransformationStrategy.PARTIAL_MASK,
    TransformationStrategy.PLACEHOLDER,
    TransformationStrategy.KEEP,
}
CONTACT_STRATEGIES = COMMON | {TransformationStrategy.PARTIAL_MASK}

ALLOWED: dict[EntityType, set[TransformationStrategy]] = {
    **{t: PERSON_STRATEGIES for t in PERSON_TYPES},
    EntityType.NATIONAL_ID: IDENTIFIER_STRATEGIES,
    EntityType.PASSPORT_NUMBER: IDENTIFIER_STRATEGIES,
    EntityType.TAX_IDENTIFIER: IDENTIFIER_STRATEGIES,
    EntityType.EMPLOYEE_ID: IDENTIFIER_STRATEGIES,
    EntityType.CUSTOMER_ID: IDENTIFIER_STRATEGIES,
    EntityType.OTHER_IDENTIFIER: IDENTIFIER_STRATEGIES,
    EntityType.PROFESSIONAL_ID: IDENTIFIER_STRATEGIES,
    EntityType.VEHICLE_PLATE: IDENTIFIER_STRATEGIES,
    EntityType.CREDIT_CARD: IDENTIFIER_STRATEGIES,
    EntityType.BANK_ACCOUNT: IDENTIFIER_STRATEGIES,
    EntityType.FINANCIAL_IDENTIFIER: IDENTIFIER_STRATEGIES,
    EntityType.IBAN: CONTACT_STRATEGIES,
    EntityType.EMAIL: CONTACT_STRATEGIES,
    EntityType.PHONE_NUMBER: CONTACT_STRATEGIES,
    EntityType.IP_ADDRESS: CONTACT_STRATEGIES,
    EntityType.PORT_NUMBER: COMMON,
    EntityType.URL: CONTACT_STRATEGIES,
    EntityType.SYSTEM_URL: COMMON,
    EntityType.MONEY_AMOUNT: COMMON,
    EntityType.ADDRESS: ADDRESS_STRATEGIES,
    EntityType.UETS: ADDRESS_STRATEGIES,
    EntityType.POSTAL_CODE: ADDRESS_STRATEGIES,
    EntityType.LOCATION: ADDRESS_STRATEGIES,
    EntityType.DATE: DATE_STRATEGIES,
    EntityType.DATE_OF_BIRTH: BIRTH_DATE_STRATEGIES,
    EntityType.BIRTH_PLACE: ADDRESS_STRATEGIES,
    EntityType.COURT_NAME: COURT_STRATEGIES,
    EntityType.CASE_NUMBER: COMMON,
    EntityType.FILE_NUMBER: COMMON,
    EntityType.DECISION_NUMBER: COMMON,
    EntityType.COMPANY_NAME: COMMON | {TransformationStrategy.INITIALS},
    EntityType.ORGANISATION: COMMON,
    EntityType.SIGNATURE: {TransformationStrategy.REDACT, TransformationStrategy.KEEP},
    EntityType.QR_CODE: {TransformationStrategy.REDACT, TransformationStrategy.KEEP},
    EntityType.UYAP_ACCESS: {TransformationStrategy.REDACT, TransformationStrategy.KEEP},
    EntityType.SALARY_INFORMATION: COMMON,
    EntityType.POLITICAL_INFORMATION: COMMON,
}

# Category default transformation policy. Independent of tag taxonomy:
# PLACEHOLDER spelling is assigned later by the document tag registry.
RECOMMENDED: dict[EntityType, TransformationStrategy] = {
    EntityType.PERSON_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.FIRST_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.LAST_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.ALIAS: TransformationStrategy.PLACEHOLDER,
    EntityType.CLAIMANT_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.DEFENDANT_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.LAWYER_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.JUDGE_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.WITNESS_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.EXPERT_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.EMPLOYEE_ID: TransformationStrategy.PLACEHOLDER,
    EntityType.CUSTOMER_ID: TransformationStrategy.PLACEHOLDER,
    EntityType.OTHER_IDENTIFIER: TransformationStrategy.PLACEHOLDER,
    EntityType.BIRTH_PLACE: TransformationStrategy.PLACEHOLDER,
    EntityType.VEHICLE_PLATE: TransformationStrategy.PLACEHOLDER,
    EntityType.ADDRESS: TransformationStrategy.REDACT,
    EntityType.CASE_NUMBER: TransformationStrategy.PLACEHOLDER,
    EntityType.FILE_NUMBER: TransformationStrategy.PLACEHOLDER,
    EntityType.DECISION_NUMBER: TransformationStrategy.PLACEHOLDER,
    EntityType.PROFESSIONAL_ID: TransformationStrategy.REDACT,
    EntityType.NATIONAL_ID: TransformationStrategy.REDACT,
    EntityType.PASSPORT_NUMBER: TransformationStrategy.REDACT,
    EntityType.TAX_IDENTIFIER: TransformationStrategy.REDACT,
    EntityType.DATE_OF_BIRTH: TransformationStrategy.PARTIAL_MASK,
    EntityType.SIGNATURE: TransformationStrategy.REDACT,
    EntityType.POSTAL_CODE: TransformationStrategy.REDACT,
    EntityType.FINANCIAL_IDENTIFIER: TransformationStrategy.REDACT,
    EntityType.UYAP_ACCESS: TransformationStrategy.REDACT,
    EntityType.QR_CODE: TransformationStrategy.REDACT,
    EntityType.SALARY_INFORMATION: TransformationStrategy.REDACT,
    EntityType.POLITICAL_INFORMATION: TransformationStrategy.REDACT,
    EntityType.PHONE_NUMBER: TransformationStrategy.PLACEHOLDER,
    EntityType.EMAIL: TransformationStrategy.PARTIAL_MASK,
    EntityType.IP_ADDRESS: TransformationStrategy.PARTIAL_MASK,
    EntityType.URL: TransformationStrategy.PARTIAL_MASK,
    EntityType.IBAN: TransformationStrategy.REDACT,
    EntityType.BANK_ACCOUNT: TransformationStrategy.PARTIAL_MASK,
    EntityType.CREDIT_CARD: TransformationStrategy.PARTIAL_MASK,
    EntityType.COURT_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.LOCATION: TransformationStrategy.KEEP,
    EntityType.SYSTEM_URL: TransformationStrategy.KEEP,
    EntityType.PORT_NUMBER: TransformationStrategy.KEEP,
    EntityType.COMPANY_NAME: TransformationStrategy.PLACEHOLDER,
    EntityType.ORGANISATION: TransformationStrategy.PLACEHOLDER,
    EntityType.DATE: TransformationStrategy.KEEP,
    EntityType.MONEY_AMOUNT: TransformationStrategy.KEEP,
    EntityType.UETS: TransformationStrategy.REDACT,
}

PLACEHOLDER_PREFIX_TR: dict[str, str] = {
    entity_type.value: spec.labels_tr for entity_type, spec in TAG_SPECS.items()
}
PLACEHOLDER_PREFIX_EN: dict[str, str] = {
    entity_type.value: spec.labels_en for entity_type, spec in TAG_SPECS.items()
}

ROLE_LABELS_TR: dict[str, str] = {
    "DEFENDANT": "Sanık",
    "SUSPECT": "Şüpheli",
    "CLAIMANT": "Davacı",
    "RESPONDENT": "Davalı",
    "INTERVENOR": "Katılan",
    "COMPLAINANT": "Müşteki",
    "ACCUSER": "Şikâyetçi",
    "WITNESS": "Tanık",
    "COUNSEL": "Vekil",
    "DEFENSE_COUNSEL": "Avukat",
    "APPLICANT": "Başvurucu",
    "DEBTOR": "Borçlu",
    "CREDITOR": "Alacaklı",
    "EXPERT": "Bilirkişi",
    "JUDGE": "Hâkim",
    "LAWYER": "Vekil",
    "PROSECUTOR": "Savcı",
    "CLERK": "Kâtip",
    "BAILIFF": "Mübaşir",
    "VICTIM": "Mağdur",
    "ACCOUNT_HOLDER": "Hesap sahibi",
    "PHONE_HOLDER": "Hat sahibi",
    "CARD_HOLDER": "Kart sahibi",
}

ROLE_LABELS_EN: dict[str, str] = {
    "DEFENDANT": "Defendant",
    "SUSPECT": "Suspect",
    "CLAIMANT": "Claimant",
    "RESPONDENT": "Respondent",
    "INTERVENOR": "Intervenor",
    "COMPLAINANT": "Complainant",
    "ACCUSER": "Complainant",
    "WITNESS": "Witness",
    "COUNSEL": "Counsel",
    "DEFENSE_COUNSEL": "Defense counsel",
    "APPLICANT": "Applicant",
    "DEBTOR": "Debtor",
    "CREDITOR": "Creditor",
    "EXPERT": "Expert",
    "JUDGE": "Judge",
    "LAWYER": "Counsel",
    "PROSECUTOR": "Prosecutor",
    "CLERK": "Clerk",
    "BAILIFF": "Bailiff",
    "VICTIM": "Victim",
    "ACCOUNT_HOLDER": "Account holder",
    "PHONE_HOLDER": "Phone holder",
    "CARD_HOLDER": "Card holder",
}

TYPE_TO_ROLE: dict[EntityType, str] = {
    EntityType.DEFENDANT_NAME: "DEFENDANT",
    EntityType.CLAIMANT_NAME: "CLAIMANT",
    EntityType.WITNESS_NAME: "WITNESS",
    EntityType.EXPERT_NAME: "EXPERT",
    EntityType.LAWYER_NAME: "COUNSEL",
    EntityType.JUDGE_NAME: "JUDGE",
}

ROLE_ALIASES: dict[str, str] = {
    "sanık": "DEFENDANT",
    "sanik": "DEFENDANT",
    "şüpheli": "SUSPECT",
    "supheli": "SUSPECT",
    "defendant": "DEFENDANT",
    "davacı": "CLAIMANT",
    "davaci": "CLAIMANT",
    "claimant": "CLAIMANT",
    "plaintiff": "CLAIMANT",
    "isteyen": "CLAIMANT",
    "haciz isteyen": "CLAIMANT",
    "ihtiyati haciz isteyen": "CLAIMANT",
    "karşı taraf": "RESPONDENT",
    "karsi taraf": "RESPONDENT",
    "davalı": "RESPONDENT",
    "davali": "RESPONDENT",
    "respondent": "RESPONDENT",
    "katılan": "INTERVENOR",
    "katilan": "INTERVENOR",
    "müşteki": "COMPLAINANT",
    "musteki": "COMPLAINANT",
    "şikâyetçi": "ACCUSER",
    "şikayetçi": "ACCUSER",
    "sikayetci": "ACCUSER",
    "tanık": "WITNESS",
    "tanik": "WITNESS",
    "witness": "WITNESS",
    "vekil": "COUNSEL",
    "müdafi": "DEFENSE_COUNSEL",
    "mudafi": "DEFENSE_COUNSEL",
    "avukat": "COUNSEL",
    "lawyer": "COUNSEL",
    "counsel": "COUNSEL",
    "başvurucu": "APPLICANT",
    "basvurucu": "APPLICANT",
    "applicant": "APPLICANT",
    "muhatap": "ADDRESSEE",
    "ihtar eden": "NOTICE_SENDER",
    "ihtar olunan": "NOTICE_RECIPIENT",
    "ihtar edilen": "NOTICE_RECIPIENT",
    "keşideci": "DRAWER",
    "kesideci": "DRAWER",
    "borçlu": "DEBTOR",
    "borclu": "DEBTOR",
    "alacaklı": "CREDITOR",
    "alacakli": "CREDITOR",
    "bilirkişi": "EXPERT",
    "bilirkisi": "EXPERT",
    "expert": "EXPERT",
    "hâkim": "JUDGE",
    "hakim": "JUDGE",
    "yargıç": "JUDGE",
    "yargic": "JUDGE",
    "judge": "JUDGE",
    "başkan": "JUDGE",
    "baskan": "JUDGE",
    "üye": "JUDGE",
    "uye": "JUDGE",
    "savcı": "PROSECUTOR",
    "savci": "PROSECUTOR",
    "c. savcısı": "PROSECUTOR",
    "c.savcısı": "PROSECUTOR",
    "cumhuriyet savcısı": "PROSECUTOR",
    "kâtip": "CLERK",
    "katip": "CLERK",
    "zabıt kâtibi": "CLERK",
    "zabıt katibi": "CLERK",
    "mübaşir": "BAILIFF",
    "mubasir": "BAILIFF",
    "mağdur": "VICTIM",
    "magdur": "VICTIM",
    "müşteki": "COMPLAINANT",
    "musteki": "COMPLAINANT",
    "hesap sahibi": "ACCOUNT_HOLDER",
    "hat sahibi": "PHONE_HOLDER",
    "kart sahibi": "CARD_HOLDER",
}

SECURE_PDF_STRATEGIES = {
    TransformationStrategy.REDACT,
    TransformationStrategy.INITIALS,
    TransformationStrategy.PLACEHOLDER,
    TransformationStrategy.PARTIAL_MASK,
}

SCAN_SCOPE_GROUPS: list[dict[str, object]] = [
    {
        "id": "identity",
        "types": ["NATIONAL_ID", "PASSPORT_NUMBER", "TAX_IDENTIFIER"],
    },
    {
        "id": "contact",
        "types": ["PHONE_NUMBER", "EMAIL", "ADDRESS", "UETS"],
    },
    {
        "id": "finance",
        "types": ["IBAN", "CREDIT_CARD", "BANK_ACCOUNT"],
    },
    {
        "id": "legal",
        "types": [
            "PERSON_NAME",
            "LAWYER_NAME",
            "JUDGE_NAME",
            "CLAIMANT_NAME",
            "DEFENDANT_NAME",
            "COURT_NAME",
            "CASE_NUMBER",
            "DECISION_NUMBER",
            "FILE_NUMBER",
            "UYAP_ACCESS",
        ],
    },
    {
        "id": "other",
        "types": [
            "VEHICLE_PLATE",
            "COMPANY_NAME",
            "ORGANISATION",
            "DATE",
            "DATE_OF_BIRTH",
        ],
    },
]

SCAN_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "PERSON_NAME": (
        "FIRST_NAME",
        "LAST_NAME",
        "ALIAS",
        "WITNESS_NAME",
        "EXPERT_NAME",
    ),
    "PHONE_NUMBER": ("PHONE_NUMBER",),
    "COMPANY_NAME": ("COMPANY_NAME", "ORGANISATION"),
}

GENERALIZATION_OPTIONS: dict[str, list[dict[str, str]]] = {
    "DATE": [
        {"id": "year_only", "label_key": "generalize.yearOnly"},
        {"id": "year_range", "label_key": "generalize.yearRange"},
    ],
    "DATE_OF_BIRTH": [
        {"id": "year_only", "label_key": "generalize.yearOnly"},
        {"id": "year_range", "label_key": "generalize.yearRange"},
    ],
    "ADDRESS": [
        {"id": "city_only", "label_key": "generalize.cityOnly"},
        {"id": "district_city", "label_key": "generalize.districtCity"},
    ],
    "LOCATION": [
        {"id": "city_only", "label_key": "generalize.cityOnly"},
    ],
    "COURT_NAME": [
        {"id": "court_type", "label_key": "generalize.courtType"},
    ],
}


def allowed_strategies(entity_type: EntityType) -> list[TransformationStrategy]:
    strategies = ALLOWED.get(entity_type, COMMON)
    ordered = [
        TransformationStrategy.REDACT,
        TransformationStrategy.INITIALS,
        TransformationStrategy.PARTIAL_MASK,
        TransformationStrategy.PLACEHOLDER,
        TransformationStrategy.KEEP,
    ]
    return [item for item in ordered if item in strategies]


def recommended_strategy(
    entity_type: EntityType, *, role_confident: bool = False
) -> TransformationStrategy:
    """Category default for user output. Role confidence never changes this.

    ``role_confident`` is accepted for caller compatibility. PLACEHOLDER
    spelling is assigned later by the document tag registry from existing
    detector types, not inferred roles.
    """
    del role_confident
    return RECOMMENDED.get(entity_type, TransformationStrategy.REDACT)


def placeholder_prefix(category: str, locale: str) -> str:
    return taxonomy_placeholder_prefix(category, locale)


def role_label(role_key: str, locale: str) -> str:
    table = ROLE_LABELS_TR if locale.startswith("tr") else ROLE_LABELS_EN
    return table.get(role_key, role_key)


def normalize_role_key(raw: str | None, entity_type: EntityType | None = None) -> str | None:
    if entity_type and entity_type in TYPE_TO_ROLE:
        return TYPE_TO_ROLE[entity_type]
    if not raw:
        return None
    cleaned = raw.strip().lower()
    if cleaned in ROLE_ALIASES:
        return ROLE_ALIASES[cleaned]
    upper = raw.strip().upper().replace(" ", "_")
    if upper in ROLE_LABELS_TR or upper in ROLE_LABELS_EN:
        return upper
    return None


def expand_scan_types(selected: list[str] | None) -> set[str] | None:
    if selected is None:
        return None
    allowed: set[str] = set()
    for item in selected:
        allowed.add(item)
        allowed.update(SCAN_TYPE_ALIASES.get(item, ()))
    return allowed


def filter_by_scan_types(
    candidates: list,
    selected: list[str] | None,
) -> list:
    allowed = expand_scan_types(selected)
    if allowed is None:
        return candidates
    kept = []
    for candidate in candidates:
        if candidate.detector == "USER_DEFINED_TERM":
            kept.append(candidate)
            continue
        if candidate.type.value in allowed:
            kept.append(candidate)
    return kept


def build_catalog() -> dict:
    categories = []
    for entity_type in EntityType:
        allowed = allowed_strategies(entity_type)
        categories.append(
            {
                "category": entity_type.value,
                "allowed_strategies": [item.value for item in allowed],
                "recommended_strategy": recommended_strategy(entity_type).value,
            "generalization_options": GENERALIZATION_OPTIONS.get(
                entity_type.value, []
            ),
        }
        )
    return {
        "strategies": [item.value for item in TransformationStrategy],
        "categories": categories,
        "role_labels": {"tr": ROLE_LABELS_TR, "en": ROLE_LABELS_EN},
        "secure_pdf_strategies": [item.value for item in SECURE_PDF_STRATEGIES],
        "scan_scope_groups": SCAN_SCOPE_GROUPS,
        "purpose_presets": ["ANONYMIZED", "STRICT_PRODUCTION", "DETECT_ONLY"],
        "placeholder_taxonomy": serialize_taxonomy(),
    }
