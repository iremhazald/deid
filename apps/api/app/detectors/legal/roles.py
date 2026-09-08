"""Legal role dictionaries for Turkish court documents."""

from __future__ import annotations

import re

from app.detectors.legal.common import fold_tr
from app.detectors.textutil import fold_tr_identity
from app.domain.models import EntityType
from app.transforms.catalog import ROLE_ALIASES

# Roster lines: ROLE : NAME REGISTRY
ROSTER_ROLES: tuple[tuple[str, str, EntityType], ...] = (
    ("başkan", "JUDGE", EntityType.JUDGE_NAME),
    ("üye", "JUDGE", EntityType.JUDGE_NAME),
    ("hâkim", "JUDGE", EntityType.JUDGE_NAME),
    ("hakim", "JUDGE", EntityType.JUDGE_NAME),
    ("yargıç", "JUDGE", EntityType.JUDGE_NAME),
    ("yargic", "JUDGE", EntityType.JUDGE_NAME),
    ("c. savcısı", "PROSECUTOR", EntityType.PERSON_NAME),
    ("c.savcısı", "PROSECUTOR", EntityType.PERSON_NAME),
    ("cumhuriyet savcısı", "PROSECUTOR", EntityType.PERSON_NAME),
    ("kâtip", "CLERK", EntityType.PERSON_NAME),
    ("katip", "CLERK", EntityType.PERSON_NAME),
    ("zabıt kâtibi", "CLERK", EntityType.PERSON_NAME),
    ("zabıt katibi", "CLERK", EntityType.PERSON_NAME),
    ("mübaşir", "BAILIFF", EntityType.PERSON_NAME),
    ("mubasir", "BAILIFF", EntityType.PERSON_NAME),
)

# Party-block openers, including numbered variants SANIK-(1)-
PARTY_ROLES: tuple[tuple[str, str, EntityType], ...] = (
    ("sanıklar", "DEFENDANT", EntityType.DEFENDANT_NAME),
    ("sanık", "DEFENDANT", EntityType.DEFENDANT_NAME),
    ("katılanlar", "INTERVENOR", EntityType.PERSON_NAME),
    ("katılan", "INTERVENOR", EntityType.PERSON_NAME),
    ("davacılar", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("davacı", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("davalılar", "RESPONDENT", EntityType.DEFENDANT_NAME),
    ("davalı", "RESPONDENT", EntityType.DEFENDANT_NAME),
    ("müştekiler", "COMPLAINANT", EntityType.PERSON_NAME),
    ("müşteki", "COMPLAINANT", EntityType.PERSON_NAME),
    ("şikayetçiler", "ACCUSER", EntityType.PERSON_NAME),
    ("şikayetçi", "ACCUSER", EntityType.PERSON_NAME),
    ("şikâyetçi", "ACCUSER", EntityType.PERSON_NAME),
    ("mağdurlar", "VICTIM", EntityType.PERSON_NAME),
    ("mağdur", "VICTIM", EntityType.PERSON_NAME),
    ("borçlu", "DEBTOR", EntityType.PERSON_NAME),
    ("alacaklı", "CREDITOR", EntityType.PERSON_NAME),
    ("başvurucu", "APPLICANT", EntityType.PERSON_NAME),
    ("müdahil", "INTERVENOR", EntityType.PERSON_NAME),
    ("ihtar eden", "NOTICE_SENDER", EntityType.PERSON_NAME),
    ("ihtar olunan", "NOTICE_RECIPIENT", EntityType.PERSON_NAME),
    ("ihtar edilen", "NOTICE_RECIPIENT", EntityType.PERSON_NAME),
    ("keşideci", "DRAWER", EntityType.PERSON_NAME),
    ("kesideci", "DRAWER", EntityType.PERSON_NAME),
    ("muhatap", "ADDRESSEE", EntityType.PERSON_NAME),
    ("ihtiyati haciz isteyen", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("haciz isteyen", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("isteyen", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("karşı taraf", "RESPONDENT", EntityType.DEFENDANT_NAME),
)

COUNSEL_ROLES: tuple[tuple[str, str], ...] = (
    ("müdafi", "DEFENSE_COUNSEL"),
    ("vekil", "COUNSEL"),
    ("davacı vekili", "COUNSEL"),
    ("davalı vekili", "COUNSEL"),
    ("katılan vekili", "COUNSEL"),
    ("sanık vekili", "COUNSEL"),
    ("müşteki vekili", "COUNSEL"),
    ("mağdur vekili", "COUNSEL"),
    ("borçlu vekili", "COUNSEL"),
    ("alacaklı vekili", "COUNSEL"),
    ("başvurucu vekili", "COUNSEL"),
)

# Role words that may precede or follow a person name in running text.
PERSON_TRIGGERS: tuple[tuple[str, str, EntityType], ...] = (
    ("sanıklar", "DEFENDANT", EntityType.DEFENDANT_NAME),
    ("sanık", "DEFENDANT", EntityType.DEFENDANT_NAME),
    ("katılanlar", "INTERVENOR", EntityType.PERSON_NAME),
    ("katılan", "INTERVENOR", EntityType.PERSON_NAME),
    ("müştekiler", "COMPLAINANT", EntityType.PERSON_NAME),
    ("müşteki", "COMPLAINANT", EntityType.PERSON_NAME),
    ("şikayetçiler", "ACCUSER", EntityType.PERSON_NAME),
    ("şikayetçi", "ACCUSER", EntityType.PERSON_NAME),
    ("şikâyetçi", "ACCUSER", EntityType.PERSON_NAME),
    ("mağdurlar", "VICTIM", EntityType.PERSON_NAME),
    ("mağdur", "VICTIM", EntityType.PERSON_NAME),
    ("tanıklar", "WITNESS", EntityType.WITNESS_NAME),
    ("tanık", "WITNESS", EntityType.WITNESS_NAME),
    ("davacılar", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("davacı", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("davalılar", "RESPONDENT", EntityType.DEFENDANT_NAME),
    ("davalı", "RESPONDENT", EntityType.DEFENDANT_NAME),
    ("borçlu", "DEBTOR", EntityType.PERSON_NAME),
    ("alacaklı", "CREDITOR", EntityType.PERSON_NAME),
    ("başvurucu", "APPLICANT", EntityType.PERSON_NAME),
    ("ihtar eden", "NOTICE_SENDER", EntityType.PERSON_NAME),
    ("ihtar olunan", "NOTICE_RECIPIENT", EntityType.PERSON_NAME),
    ("ihtar edilen", "NOTICE_RECIPIENT", EntityType.PERSON_NAME),
    ("keşideci", "DRAWER", EntityType.PERSON_NAME),
    ("kesideci", "DRAWER", EntityType.PERSON_NAME),
    ("muhatap", "ADDRESSEE", EntityType.PERSON_NAME),
    ("avukat", "COUNSEL", EntityType.LAWYER_NAME),
    ("av.", "COUNSEL", EntityType.LAWYER_NAME),
    ("av", "COUNSEL", EntityType.LAWYER_NAME),
    ("katılan vekili", "COUNSEL", EntityType.LAWYER_NAME),
    ("davacı vekili", "COUNSEL", EntityType.LAWYER_NAME),
    ("davalı vekili", "COUNSEL", EntityType.LAWYER_NAME),
    ("sanık vekili", "COUNSEL", EntityType.LAWYER_NAME),
    ("müşteki vekili", "COUNSEL", EntityType.LAWYER_NAME),
    ("mağdur vekili", "COUNSEL", EntityType.LAWYER_NAME),
    ("vekili", "COUNSEL", EntityType.LAWYER_NAME),
    ("vekil", "COUNSEL", EntityType.LAWYER_NAME),
    ("müdafii", "DEFENSE_COUNSEL", EntityType.LAWYER_NAME),
    ("müdafi", "DEFENSE_COUNSEL", EntityType.LAWYER_NAME),
    ("başkan", "JUDGE", EntityType.JUDGE_NAME),
    ("üye", "JUDGE", EntityType.JUDGE_NAME),
    ("hâkim", "JUDGE", EntityType.JUDGE_NAME),
    ("hakim", "JUDGE", EntityType.JUDGE_NAME),
    ("yargıç", "JUDGE", EntityType.JUDGE_NAME),
    ("savcı", "PROSECUTOR", EntityType.PERSON_NAME),
    ("kâtip", "CLERK", EntityType.PERSON_NAME),
    ("katip", "CLERK", EntityType.PERSON_NAME),
    ("hesap sahibi", "ACCOUNT_HOLDER", EntityType.PERSON_NAME),
    ("hat sahibi", "PHONE_HOLDER", EntityType.PERSON_NAME),
    ("kart sahibi", "CARD_HOLDER", EntityType.PERSON_NAME),
    ("şahıs", "", EntityType.PERSON_NAME),
    ("kişi", "", EntityType.PERSON_NAME),
    ("ihtiyati haciz isteyen", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("haciz isteyen", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("karşı taraf", "RESPONDENT", EntityType.DEFENDANT_NAME),
)

MENTION_TRIGGERS = (
    "ismi geçen",
    "adı geçen",
    "ismi gecen",
    "adi gecen",
    "isimli",
    "adlı",
    "şahıs",
    "sahis",
    "kişi",
    "kisi",
)


def _pattern_for(label: str) -> str:
    """Build a label regex that treats Turkish I/İ/ı/i as the same letter.

    ``re.IGNORECASE`` does not fold dotted İ onto i, so all-caps court
    lines like ``CUMHURİYET SAVCISI`` would otherwise miss ``cumhuriyet savcısı``.
    """
    parts = [re.escape(part) for part in label.split()]
    body = r"\s*\.?\s*".join(parts)
    return re.sub(r"[iıIİ]", "[iıIİ]", body)


def roster_label_pattern() -> re.Pattern[str]:
    # Longest first so "cumhuriyet savcısı" wins over "c. savcısı".
    raw = sorted((item[0] for item in ROSTER_ROLES), key=len, reverse=True)
    body = "|".join(_pattern_for(label) for label in raw)
    return re.compile(rf"(?<!\w)({body})\s*:", re.IGNORECASE)


def party_label_pattern() -> re.Pattern[str]:
    raw = sorted((item[0] for item in PARTY_ROLES), key=len, reverse=True)
    body = "|".join(_pattern_for(label) for label in raw)
    return re.compile(
        rf"(?m)^\s*({body})(?:\s*-\s*\(\s*\d+\s*\)\s*-)?\s*:",
        re.IGNORECASE,
    )


def counsel_label_pattern() -> re.Pattern[str]:
    raw = sorted((item[0] for item in COUNSEL_ROLES), key=len, reverse=True)
    body = "|".join(_pattern_for(label) for label in raw)
    return re.compile(rf"(?m)^\s*({body})\s*:", re.IGNORECASE)


def resolve_roster(label: str) -> tuple[str, EntityType]:
    key = fold_tr_identity(re.sub(r"\s+", " ", label).replace(".", "").strip())
    key = re.sub(r"\s+", " ", key)
    for name, role, entity_type in ROSTER_ROLES:
        if fold_tr_identity(name).replace(".", "") == key.replace(".", ""):
            return role, entity_type
    return ROLE_ALIASES.get(key, ""), EntityType.PERSON_NAME


def resolve_party(label: str) -> tuple[str, EntityType]:
    compact = re.sub(r"\s+", " ", label).strip()
    key = fold_tr(compact)
    key_id = fold_tr_identity(compact)
    for name, role, entity_type in PARTY_ROLES:
        if fold_tr(name) == key or fold_tr_identity(name) == key_id:
            return role, entity_type
    return ROLE_ALIASES.get(key, "") or ROLE_ALIASES.get(key_id, ""), EntityType.PERSON_NAME


def resolve_counsel(label: str) -> str:
    key = fold_tr(re.sub(r"\s+", " ", label).strip())
    for name, role in COUNSEL_ROLES:
        if fold_tr(name) == key:
            return role
    return "COUNSEL"


def resolve_trigger(label: str) -> tuple[str, EntityType]:
    compact = re.sub(r"\s+", " ", label).strip()
    key = fold_tr(compact)
    key_id = fold_tr_identity(compact)
    for name, role, entity_type in PERSON_TRIGGERS:
        if fold_tr(name) == key or fold_tr_identity(name) == key_id:
            return role, entity_type
    return ROLE_ALIASES.get(key, "") or ROLE_ALIASES.get(key_id, ""), EntityType.PERSON_NAME
