"""PLACEHOLDER tag families. Independent of detection types and panel grouping.

Detection ``EntityType`` values, NER labels, scoring, and review-panel grouping
stay unchanged. This module only decides how a PLACEHOLDER token is spelled.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import EntityType


@dataclass(frozen=True)
class TagSpec:
    """How PLACEHOLDER renders one detection type.

    ``ui_group`` is the review-panel heading key (listDisplayType). It is not
    a detection family and must not be used as a tag prefix.
    """

    family: str
    ui_group: str
    numbered: bool
    reuse: bool
    role_propagation: str
    placeholder_recommended: bool
    placeholder_allowed: bool
    labels_tr: str
    labels_en: str
    example_tr: str
    example_en: str
    notes: str = ""


# Role-specific person types. PERSON_NAME is generic and never invents a role.
ROLE_SPECIFIC_TYPES: frozenset[EntityType] = frozenset(
    {
        EntityType.CLAIMANT_NAME,
        EntityType.DEFENDANT_NAME,
        EntityType.LAWYER_NAME,
        EntityType.JUDGE_NAME,
        EntityType.WITNESS_NAME,
        EntityType.EXPERT_NAME,
    }
)

GENERIC_PERSON_TYPES: frozenset[EntityType] = frozenset(
    {
        EntityType.PERSON_NAME,
        EntityType.FIRST_NAME,
        EntityType.LAST_NAME,
        EntityType.ALIAS,
    }
)

PERSON_MATCH_TYPES: frozenset[EntityType] = ROLE_SPECIFIC_TYPES | GENERIC_PERSON_TYPES

# One role-specific type outranks generic PERSON. Two distinct role-specific
# types on the same exact name are a conflict → fall back to PERSON.
TYPE_TO_FAMILY: dict[EntityType, str] = {
    EntityType.CLAIMANT_NAME: "CLAIMANT",
    EntityType.DEFENDANT_NAME: "DEFENDANT",
    EntityType.LAWYER_NAME: "LAWYER",
    EntityType.JUDGE_NAME: "JUDGE",
    EntityType.WITNESS_NAME: "WITNESS",
    EntityType.EXPERT_NAME: "EXPERT",
    EntityType.PERSON_NAME: "PERSON",
    EntityType.FIRST_NAME: "PERSON",
    EntityType.LAST_NAME: "PERSON",
    EntityType.ALIAS: "PERSON",
}

GENERIC_PERSON_FAMILY = "PERSON"

# Visual overlays: PLACEHOLDER is not in the strategy catalog.
PLACEHOLDER_DISALLOWED: frozenset[EntityType] = frozenset(
    {
        EntityType.SIGNATURE,
        EntityType.QR_CODE,
        EntityType.UYAP_ACCESS,
    }
)

# Allowed, but not a useful default. Policy/recommended_strategy is unchanged.
PLACEHOLDER_DISCOURAGED: frozenset[EntityType] = frozenset(
    {
        EntityType.DATE,
        EntityType.MONEY_AMOUNT,
        EntityType.PORT_NUMBER,
        EntityType.SYSTEM_URL,
        EntityType.COMPANY_NAME,
        EntityType.ORGANISATION,
        EntityType.SALARY_INFORMATION,
        EntityType.POLITICAL_INFORMATION,
        EntityType.COURT_NAME,
    }
)


def _spec(
    family: str,
    ui_group: str,
    *,
    numbered: bool,
    reuse: bool,
    role_propagation: str,
    recommended: bool,
    allowed: bool,
    tr: str,
    en: str,
    notes: str = "",
) -> TagSpec:
    example_tr = f"[{tr}_1]" if numbered else f"[{tr}]"
    example_en = f"[{en}_1]" if numbered else f"[{en}]"
    return TagSpec(
        family=family,
        ui_group=ui_group,
        numbered=numbered,
        reuse=reuse,
        role_propagation=role_propagation,
        placeholder_recommended=recommended,
        placeholder_allowed=allowed,
        labels_tr=tr,
        labels_en=en,
        example_tr=example_tr,
        example_en=example_en,
        notes=notes,
    )


TAG_SPECS: dict[EntityType, TagSpec] = {
    EntityType.CLAIMANT_NAME: _spec(
        "CLAIMANT",
        "COURT_NAME",
        numbered=True,
        reuse=True,
        role_propagation="conservative",
        recommended=True,
        allowed=True,
        tr="DAVACI",
        en="CLAIMANT",
        notes="Panel groups under Mahkeme Bilgileri; tag family stays DAVACI.",
    ),
    EntityType.DEFENDANT_NAME: _spec(
        "DEFENDANT",
        "COURT_NAME",
        numbered=True,
        reuse=True,
        role_propagation="conservative",
        recommended=True,
        allowed=True,
        tr="DAVALI",
        en="DEFENDANT",
    ),
    EntityType.LAWYER_NAME: _spec(
        "LAWYER",
        "COURT_NAME",
        numbered=True,
        reuse=True,
        role_propagation="conservative",
        recommended=True,
        allowed=True,
        tr="AVUKAT",
        en="LAWYER",
    ),
    EntityType.JUDGE_NAME: _spec(
        "JUDGE",
        "COURT_NAME",
        numbered=True,
        reuse=True,
        role_propagation="conservative",
        recommended=True,
        allowed=True,
        tr="HÂKİM",
        en="JUDGE",
    ),
    EntityType.WITNESS_NAME: _spec(
        "WITNESS",
        "COURT_NAME",
        numbered=True,
        reuse=True,
        role_propagation="conservative",
        recommended=True,
        allowed=True,
        tr="TANIK",
        en="WITNESS",
    ),
    EntityType.EXPERT_NAME: _spec(
        "EXPERT",
        "COURT_NAME",
        numbered=True,
        reuse=True,
        role_propagation="conservative",
        recommended=True,
        allowed=True,
        tr="BİLİRKİŞİ",
        en="EXPERT",
    ),
    EntityType.PERSON_NAME: _spec(
        "PERSON",
        "PERSON_NAME",
        numbered=True,
        reuse=True,
        role_propagation="conservative",
        recommended=True,
        allowed=True,
        tr="KİŞİ",
        en="PERSON",
        notes="May inherit a role family only via exact full-name match to a role-typed span.",
    ),
    EntityType.FIRST_NAME: _spec(
        "PERSON",
        "PERSON_NAME",
        numbered=True,
        reuse=True,
        role_propagation="none",
        recommended=True,
        allowed=True,
        tr="KİŞİ",
        en="PERSON",
        notes="Single given names never merge into a full name.",
    ),
    EntityType.LAST_NAME: _spec(
        "PERSON",
        "PERSON_NAME",
        numbered=True,
        reuse=True,
        role_propagation="none",
        recommended=True,
        allowed=True,
        tr="KİŞİ",
        en="PERSON",
        notes="Surname-only spans never merge into a full name.",
    ),
    EntityType.ALIAS: _spec(
        "PERSON",
        "PERSON_NAME",
        numbered=True,
        reuse=True,
        role_propagation="none",
        recommended=True,
        allowed=True,
        tr="KİŞİ",
        en="PERSON",
    ),
    EntityType.COMPANY_NAME: _spec(
        "COMPANY",
        "INSTITUTION",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="ŞİRKET",
        en="COMPANY",
        notes="Default PLACEHOLDER so company names are tagged, not left in KEEP.",
    ),
    EntityType.ORGANISATION: _spec(
        "ORGANISATION",
        "INSTITUTION",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="KURUM",
        en="ORGANISATION",
        notes="Default PLACEHOLDER so institution names are tagged, not left in KEEP.",
    ),
    EntityType.ADDRESS: _spec(
        "ADDRESS",
        "ADDRESS",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="ADRES",
        en="ADDRESS",
    ),
    EntityType.UETS: _spec(
        "UETS",
        "ADDRESS",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="UETS",
        en="UETS",
        notes="National electronic notification address. Default REDACT.",
    ),
    EntityType.POSTAL_CODE: _spec(
        "POSTAL_CODE",
        "ADDRESS",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="POSTA_KODU",
        en="POSTAL_CODE",
        notes="Descriptive attribute. Panel stays under Adresler; no document identity number.",
    ),
    EntityType.LOCATION: _spec(
        "LOCATION",
        "ADDRESS",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="KONUM",
        en="LOCATION",
    ),
    EntityType.BIRTH_PLACE: _spec(
        "BIRTH_PLACE",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="DOĞUM_YERİ",
        en="PLACE_OF_BIRTH",
    ),
    EntityType.PHONE_NUMBER: _spec(
        "PHONE",
        "PHONE_NUMBER",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="TELEFON",
        en="PHONE",
    ),
    EntityType.EMAIL: _spec(
        "EMAIL",
        "EMAIL",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="EPOSTA",
        en="EMAIL",
    ),
    EntityType.IBAN: _spec(
        "IBAN",
        "BANKING",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="IBAN",
        en="IBAN",
    ),
    EntityType.BANK_ACCOUNT: _spec(
        "ACCOUNT",
        "BANKING",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="HESAP",
        en="ACCOUNT",
    ),
    EntityType.CREDIT_CARD: _spec(
        "CARD",
        "BANKING",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="KART",
        en="CARD",
    ),
    EntityType.FINANCIAL_IDENTIFIER: _spec(
        "FINANCIAL_ID",
        "BANKING",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="FİNANSAL_ID",
        en="FINANCIAL_ID",
    ),
    EntityType.NATIONAL_ID: _spec(
        "NATIONAL_ID",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="TCKN",
        en="NATIONAL_ID",
    ),
    EntityType.PASSPORT_NUMBER: _spec(
        "PASSPORT",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="PASAPORT",
        en="PASSPORT",
    ),
    EntityType.TAX_IDENTIFIER: _spec(
        "TAX_ID",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="VKN",
        en="TAX_ID",
    ),
    EntityType.EMPLOYEE_ID: _spec(
        "EMPLOYEE_ID",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="PERSONEL_NO",
        en="EMPLOYEE_ID",
    ),
    EntityType.CUSTOMER_ID: _spec(
        "CUSTOMER_ID",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="MÜŞTERİ_NO",
        en="CUSTOMER_ID",
    ),
    EntityType.OTHER_IDENTIFIER: _spec(
        "OTHER_ID",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="TANIMLAYICI",
        en="IDENTIFIER",
    ),
    EntityType.PROFESSIONAL_ID: _spec(
        "PROFESSIONAL_ID",
        "COURT_NAME",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="SİCİL",
        en="REGISTRY_NO",
        notes="Panel groups under Mahkeme Bilgileri; tag family stays SİCİL.",
    ),
    EntityType.VEHICLE_PLATE: _spec(
        "PLATE",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="PLAKA",
        en="VEHICLE_PLATE",
    ),
    EntityType.CASE_NUMBER: _spec(
        "CASE_NUMBER",
        "FILE_NUMBER",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="ESAS",
        en="CASE_NO",
    ),
    EntityType.FILE_NUMBER: _spec(
        "FILE_NUMBER",
        "FILE_NUMBER",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="DOSYA",
        en="FILE_NO",
    ),
    EntityType.DECISION_NUMBER: _spec(
        "DECISION_NUMBER",
        "FILE_NUMBER",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="KARAR",
        en="DECISION_NO",
    ),
    EntityType.COURT_NAME: _spec(
        "COURT",
        "COURT_NAME",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=False,
        allowed=True,
        tr="MAHKEME",
        en="COURT",
        notes="Default PLACEHOLDER replaces chamber ordinals with X, not [MAHKEME].",
    ),
    EntityType.DATE: _spec(
        "DATE",
        "DATE",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=False,
        allowed=True,
        tr="TARİH",
        en="DATE",
        notes="Descriptive attribute. Explicit PLACEHOLDER yields generic [TARİH]; default policy unchanged.",
    ),
    EntityType.DATE_OF_BIRTH: _spec(
        "DATE_OF_BIRTH",
        "NATIONAL_ID",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="DOĞUM_TARİHİ",
        en="DATE_OF_BIRTH",
    ),
    EntityType.IP_ADDRESS: _spec(
        "IP",
        "CYBER",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="IP",
        en="IP",
    ),
    EntityType.URL: _spec(
        "URL",
        "CYBER",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="URL",
        en="URL",
    ),
    EntityType.SYSTEM_URL: _spec(
        "SYSTEM_URL",
        "CYBER",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=False,
        allowed=True,
        tr="SİSTEM_URL",
        en="SYSTEM_URL",
    ),
    EntityType.PORT_NUMBER: _spec(
        "PORT",
        "CYBER",
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=False,
        allowed=True,
        tr="PORT",
        en="PORT",
    ),
    EntityType.MONEY_AMOUNT: _spec(
        "AMOUNT",
        "MONEY_AMOUNT",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=False,
        allowed=True,
        tr="TUTAR",
        en="AMOUNT",
        notes="Descriptive attribute. Default remains KEEP. Explicit PLACEHOLDER yields generic [TUTAR].",
    ),
    EntityType.SALARY_INFORMATION: _spec(
        "SALARY",
        "SALARY_INFORMATION",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=False,
        allowed=True,
        tr="MAAŞ",
        en="SALARY",
        notes="Free-text span: generic unnumbered tag. Default remains REDACT.",
    ),
    EntityType.POLITICAL_INFORMATION: _spec(
        "POLITICAL",
        "POLITICAL_INFORMATION",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=False,
        allowed=True,
        tr="SİYASİ",
        en="POLITICAL",
        notes="Special-category political opinion/affiliation. Default REDACT.",
    ),
    EntityType.SIGNATURE: _spec(
        "SIGNATURE",
        "NATIONAL_ID",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=False,
        allowed=False,
        tr="İMZA",
        en="SIGNATURE",
        notes="Visual overlay only; PLACEHOLDER is not offered.",
    ),
    EntityType.QR_CODE: _spec(
        "QR",
        "QR_CODE",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=False,
        allowed=False,
        tr="KAREKOD",
        en="QR",
        notes="Visual overlay only; PLACEHOLDER is not offered.",
    ),
    EntityType.UYAP_ACCESS: _spec(
        "UYAP",
        "FILE_NUMBER",
        numbered=False,
        reuse=False,
        role_propagation="n/a",
        recommended=False,
        allowed=False,
        tr="UYAP",
        en="UYAP",
        notes="Visual overlay only; PLACEHOLDER is not offered.",
    ),
}

FAMILY_LABELS_TR: dict[str, str] = {
    spec.family: spec.labels_tr for spec in TAG_SPECS.values()
}
FAMILY_LABELS_EN: dict[str, str] = {
    spec.family: spec.labels_en for spec in TAG_SPECS.values()
}


def spec_for(entity_type: EntityType | str) -> TagSpec:
    if isinstance(entity_type, str):
        entity_type = EntityType(entity_type)
    spec = TAG_SPECS.get(entity_type)
    if spec is not None:
        return spec
    return _spec(
        "LABEL",
        entity_type.value if isinstance(entity_type, EntityType) else str(entity_type),
        numbered=True,
        reuse=True,
        role_propagation="n/a",
        recommended=True,
        allowed=True,
        tr="ETİKET",
        en="LABEL",
    )


def family_for_type(entity_type: EntityType | str) -> str:
    return spec_for(entity_type).family


def normalize_tag_locale(locale: str | None) -> str:
    """Map a document-language value to the tag-label locale ``tr`` or ``en``."""
    if not locale:
        return "tr"
    value = locale.strip().lower()
    if value.startswith("en"):
        return "en"
    return "tr"


def family_label(family: str, locale: str) -> str:
    turkish = normalize_tag_locale(locale) == "tr"
    table = FAMILY_LABELS_TR if turkish else FAMILY_LABELS_EN
    if family in table:
        return table[family]
    return "ETİKET" if turkish else "LABEL"


def placeholder_prefix(category: str, locale: str) -> str:
    """Type-level prefix without document identity or role propagation."""
    spec = spec_for(category)
    return spec.labels_tr if normalize_tag_locale(locale) == "tr" else spec.labels_en


def numbered_families() -> frozenset[str]:
    return frozenset(
        spec.family
        for spec in TAG_SPECS.values()
        if spec.numbered and spec.placeholder_allowed
    )


def generic_placeholder_families() -> frozenset[str]:
    return frozenset(
        spec.family
        for spec in TAG_SPECS.values()
        if not spec.numbered and spec.placeholder_allowed
    )


def resolve_person_family(types: set[EntityType]) -> str:
    """Pick a person tag family from detector types already present.

    Does not infer roles. Conflicting role-specific types fall back to PERSON.
    """
    roles = {TYPE_TO_FAMILY[item] for item in types if item in ROLE_SPECIFIC_TYPES}
    if len(roles) > 1:
        return GENERIC_PERSON_FAMILY
    if len(roles) == 1:
        return next(iter(roles))
    return GENERIC_PERSON_FAMILY


def serialize_taxonomy() -> list[dict[str, object]]:
    rows = []
    for entity_type, spec in TAG_SPECS.items():
        rows.append(
            {
                "entity_type": entity_type.value,
                "ui_group": spec.ui_group,
                "family": spec.family,
                "numbered": spec.numbered,
                "reuse": spec.reuse,
                "role_propagation": spec.role_propagation,
                "placeholder_allowed": spec.placeholder_allowed,
                "placeholder_recommended": spec.placeholder_recommended,
                "labels": {"tr": spec.labels_tr, "en": spec.labels_en},
                "example": {"tr": spec.example_tr, "en": spec.example_en},
            }
        )
    return rows
