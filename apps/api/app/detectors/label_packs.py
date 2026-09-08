from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import EntityType


@dataclass(frozen=True)
class SemanticLabelGroup:
    """Maps document label concepts to entity types and language-specific aliases."""

    concept: str
    entity_types: tuple[EntityType, ...]
    aliases: dict[str, tuple[str, ...]]


# Configuration-driven semantic labels. Add languages/jurisdictions without
# changing the structural detector algorithm.
SEMANTIC_LABEL_GROUPS: tuple[SemanticLabelGroup, ...] = (
    SemanticLabelGroup(
        concept="person_name",
        entity_types=(EntityType.PERSON_NAME,),
        aliases={
            "en": (
                "name",
                "full name",
                "name of signatory",
                "signed by",
                "claimant",
                "defendant",
                "applicant",
                "respondent",
                "plaintiff",
                "petitioner",
                "appellant",
                "appellee",
                "complainant",
                "accused",
                "deponent",
                "affiant",
                "witness",
                "counsel",
                "attorney",
                "solicitor",
                "barrister",
                "subject",
                "employee",
                "client",
                "contact person",
            ),
            "tr": (
                "ad soyad",
                "isim",
                "adı",
                "soyadı",
                "davacı",
                "davalı",
                "şikayetçi",
                "müşteri",
                "başvurucu",
                "muhatap",
                "ihtar eden",
                "ihtar olunan",
                "ihtar edilen",
                "keşideci",
                "kesideci",
            ),
            "de": (
                "name",
                "vorname",
                "nachname",
                "kläger",
                "beklagter",
                "antragsteller",
            ),
        },
    ),
    SemanticLabelGroup(
        concept="identity",
        entity_types=(EntityType.NATIONAL_ID, EntityType.PASSPORT_NUMBER, EntityType.TAX_IDENTIFIER),
        aliases={
            "en": (
                "national id",
                "national id no",
                "national identification number",
                "identity number",
                "id number",
                "passport",
                "passport no",
                "passport number",
                "passport #",
                "tax id",
                "tax identifier",
                "social security",
            ),
            "tr": (
                "kimlik",
                "tc kimlik",
                "t.c. kimlik",
                "tc kimlik no",
                "pasaport",
                "vergi no",
                "vergi numarası",
                "vergi kimlik",
                "vergi kimlik no",
                "vergi kimlik numarası",
                "v.k.n.",
                "vkn",
            ),
            "de": ("personalausweis", "steuer-id", "steuernummer", "passnummer"),
        },
    ),
    SemanticLabelGroup(
        concept="address",
        entity_types=(EntityType.ADDRESS, EntityType.LOCATION, EntityType.POSTAL_CODE),
        aliases={
            "en": (
                "address",
                "home address",
                "residential address",
                "registered address",
                "service address",
                "address for service",
                "correspondence address",
                "postal address",
                "mailing address",
                "residence",
                "location",
                "postal code",
                "postcode",
                "zip",
                "zip code",
            ),
            "tr": ("adres", "ikametgah", "açık adres", "posta adresi"),
            "de": ("adresse", "wohnort", "anschrift"),
        },
    ),
    SemanticLabelGroup(
        concept="contact",
        entity_types=(EntityType.EMAIL, EntityType.PHONE_NUMBER),
        aliases={
            "en": (
                "email",
                "e-mail",
                "email address",
                "phone",
                "telephone",
                "tel",
                "mobile",
                "cell",
                "contact number",
                "phone number",
                "telephone number",
                "fax",
                "website",
                "web",
                "url",
            ),
            "tr": ("e-posta", "eposta", "telefon", "gsm", "cep telefonu", "faks"),
            "de": ("e-mail", "telefon", "mobiltelefon", "fax"),
        },
    ),
    SemanticLabelGroup(
        concept="account_identifier",
        entity_types=(EntityType.CUSTOMER_ID, EntityType.EMPLOYEE_ID, EntityType.OTHER_IDENTIFIER),
        aliases={
            "en": (
                "account number",
                "account id",
                "customer number",
                "customer id",
                "subscriber number",
                "subscriber id",
                "client number",
                "employee id",
                "member number",
                "reference number",
                "client reference",
            ),
            "tr": (
                "abone no",
                "abone numarası",
                "müşteri no",
                "müşteri numarası",
                "hesap no",
                "sicil no",
                "referans no",
            ),
            "de": (
                "kundennummer",
                "kunden-id",
                "vertragsnummer",
                "kontonummer",
                "personalnummer",
            ),
        },
    ),
    SemanticLabelGroup(
        concept="financial",
        entity_types=(EntityType.IBAN, EntityType.BANK_ACCOUNT, EntityType.FINANCIAL_IDENTIFIER),
        aliases={
            "en": (
                "iban",
                "bank account",
                "account number",
                "account no",
                "account",
                "sort code",
                "routing number",
                "swift",
                "bic",
            ),
            "tr": ("iban", "banka hesabı", "hesap numarası"),
            "de": ("iban", "bankkonto", "kontonummer"),
        },
    ),
    SemanticLabelGroup(
        concept="case_identifier",
        entity_types=(EntityType.CASE_NUMBER, EntityType.FILE_NUMBER, EntityType.DECISION_NUMBER),
        aliases={
            "en": (
                "case number",
                "case no",
                "claim number",
                "claim no",
                "file number",
                "file no",
                "docket number",
                "docket no",
                "decision number",
                "reference",
                "reference number",
                "reference no",
                "matter number",
                "matter no",
                "proceeding number",
                "proceeding no",
                "application no",
                "appeal no",
            ),
            "tr": (
                "dosya no",
                "dosya numarası",
                "dava no",
                "karar no",
                "karar numarası",
                "esas no",
                "esas numarası",
                "evrak no",
                "c.savcılığı esas no",
                "c. savcılığı esas no",
                "c.savciligi esas no",
                "c. savciligi esas no",
                "cumhuriyet savcılığı esas no",
                "savcılığı esas no",
            ),
            "de": ("aktenzeichen", "geschäftszeichen", "az", "file number"),
        },
    ),
    SemanticLabelGroup(
        concept="organization",
        entity_types=(EntityType.ORGANISATION, EntityType.COMPANY_NAME, EntityType.COURT_NAME),
        aliases={
            "en": ("company", "organization", "organisation", "court", "authority", "institution"),
            "tr": ("kurum", "şirket", "mahkeme", "kuruluş", "idare"),
            "de": ("unternehmen", "behörde", "gericht", "institution"),
        },
    ),
    SemanticLabelGroup(
        concept="date_of_birth",
        entity_types=(EntityType.DATE_OF_BIRTH, EntityType.DATE),
        aliases={
            "en": (
                "date of birth",
                "birth date",
                "dob",
                "d.o.b.",
                "born",
                "place of birth",
                "birthplace",
            ),
            "tr": ("doğum tarihi", "doğum tarih"),
            "de": ("geburtsdatum", "geboren am"),
        },
    ),
)


def label_lookup() -> dict[str, SemanticLabelGroup]:
    """Normalized alias -> semantic group (longest aliases registered first)."""
    pairs: list[tuple[str, SemanticLabelGroup]] = []
    for group in SEMANTIC_LABEL_GROUPS:
        for aliases in group.aliases.values():
            for alias in aliases:
                pairs.append((alias.casefold().strip(), group))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return dict(pairs)
