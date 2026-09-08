"""Turkish jurisdiction locale pack."""
from app.detectors.locale_pack import LocalePack
from app.detectors.registry import detect_legal_structure, detect_tr
from app.detectors.turkish_advanced import detect_turkish_advanced

TURKISH_PACK = LocalePack(
    locale_id="tr",
    name="Turkish Legal Documents",
    detectors=[
        ("TR_DOCUMENTED", detect_tr),
        ("TR_ADVANCED_GRAMMAR", detect_turkish_advanced),
        ("TR_LEGAL_STRUCTURE", detect_legal_structure),
    ],
    placeholder_prefixes={
        "PERSON_NAME": "KİŞİ",
        "ADDRESS": "ADRES",
        "PHONE_NUMBER": "TELEFON",
        "EMAIL": "E-POSTA",
        "IBAN": "IBAN",
        "NATIONAL_ID": "TCKN",
    },
    role_labels={
        "claimant": "Davacı",
        "defendant": "Davalı",
        "witness": "Tanık",
        "expert": "Bilirkişi",
        "lawyer": "Avukat",
        "judge": "Hakim",
    },
)
