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
    ("duruşma savcısı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("durusma savcisi", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("cumhuriyet savcısı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("cumhuriyet savcisi", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("c. savcısı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("c.savcısı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("c. savcisi", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("savcı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("savci", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("zabıt kâtibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("zabıt katibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("zabit katibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("mahkeme kâtibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("mahkeme katibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("kâtip", "CLERK", EntityType.COURT_CLERK_NAME),
    ("katip", "CLERK", EntityType.COURT_CLERK_NAME),
    ("mübaşir", "BAILIFF", EntityType.PERSON_NAME),
    ("mubasir", "BAILIFF", EntityType.PERSON_NAME),
)

# Party-block openers, including numbered variants SANIK-(1)-
PARTY_ROLES: tuple[tuple[str, str, EntityType], ...] = (
    ("müşteki / sanık", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("musteki / sanik", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("müşteki/sanık", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("musteki/sanik", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("müşteki-sanık", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("musteki-sanik", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("müşteki sanık", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("musteki sanik", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("müşteki-şüpheli", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("musteki-supheli", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("katılan müşteki", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katilan musteki", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katılan-müşteki", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katilan-musteki", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("müşteki katılan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("musteki katilan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("müşteki-katılan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("musteki-katilan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("mağdur-katılan", "VICTIM", EntityType.VICTIM_NAME),
    ("magdur-katilan", "VICTIM", EntityType.VICTIM_NAME),
    ("mağdur katılan", "VICTIM", EntityType.VICTIM_NAME),
    ("magdur katilan", "VICTIM", EntityType.VICTIM_NAME),
    ("katılan-mağdur", "VICTIM", EntityType.VICTIM_NAME),
    ("katilan-magdur", "VICTIM", EntityType.VICTIM_NAME),
    ("katılan mağdur", "VICTIM", EntityType.VICTIM_NAME),
    ("katilan magdur", "VICTIM", EntityType.VICTIM_NAME),
    ("suç mağduru", "VICTIM", EntityType.VICTIM_NAME),
    ("suc magduru", "VICTIM", EntityType.VICTIM_NAME),
    ("mağdur çocuk", "VICTIM", EntityType.VICTIM_NAME),
    ("magdur cocuk", "VICTIM", EntityType.VICTIM_NAME),
    ("şüphelinin adı soyadı", "SUSPECT", EntityType.SUSPECT_NAME),
    ("suphelinin adi soyadi", "SUSPECT", EntityType.SUSPECT_NAME),
    ("şüpheliler", "SUSPECT", EntityType.SUSPECT_NAME),
    ("supheliler", "SUSPECT", EntityType.SUSPECT_NAME),
    ("şüpheli", "SUSPECT", EntityType.SUSPECT_NAME),
    ("supheli", "SUSPECT", EntityType.SUSPECT_NAME),
    ("sanığın adı soyadı", "ACCUSED", EntityType.ACCUSED_NAME),
    ("sanigin adi soyadi", "ACCUSED", EntityType.ACCUSED_NAME),
    ("suça sürüklenen çocuk", "ACCUSED", EntityType.ACCUSED_NAME),
    ("suca suruklenen cocuk", "ACCUSED", EntityType.ACCUSED_NAME),
    ("ssç", "ACCUSED", EntityType.ACCUSED_NAME),
    ("ssc", "ACCUSED", EntityType.ACCUSED_NAME),
    ("sanıklar", "ACCUSED", EntityType.ACCUSED_NAME),
    ("saniklar", "ACCUSED", EntityType.ACCUSED_NAME),
    ("sanık", "ACCUSED", EntityType.ACCUSED_NAME),
    ("sanik", "ACCUSED", EntityType.ACCUSED_NAME),
    ("katılanlar", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katilanlar", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katılan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katilan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("davacılar", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("davacı", "CLAIMANT", EntityType.CLAIMANT_NAME),
    ("davalılar", "RESPONDENT", EntityType.DEFENDANT_NAME),
    ("davalı", "RESPONDENT", EntityType.DEFENDANT_NAME),
    ("müştekiler", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("mustekiler", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("müşteki", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("musteki", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("şikayetçiler", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("şikayetçi", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("şikâyetçi", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("sikayetci", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("mağdurlar", "VICTIM", EntityType.VICTIM_NAME),
    ("magdurlar", "VICTIM", EntityType.VICTIM_NAME),
    ("mağdur", "VICTIM", EntityType.VICTIM_NAME),
    ("magdur", "VICTIM", EntityType.VICTIM_NAME),
    ("borçlu", "DEBTOR", EntityType.PERSON_NAME),
    ("alacaklı", "CREDITOR", EntityType.PERSON_NAME),
    ("başvurucu", "APPLICANT", EntityType.PERSON_NAME),
    ("müdahil", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("mudahil", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("kanuni temsilci", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("yasal temsilci", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("vasi", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("veli", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("kayyım", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("kayyim", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("arabulucunun adı soyadı", "MEDIATOR", EntityType.MEDIATOR_NAME),
    ("arabulucunun adi soyadi", "MEDIATOR", EntityType.MEDIATOR_NAME),
    ("arabulucu avukat", "MEDIATOR", EntityType.MEDIATOR_NAME),
    ("arabulucu", "MEDIATOR", EntityType.MEDIATOR_NAME),
    ("yeminli tercüman", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("yeminli tercuman", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("yeminli çevirmen", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("yeminli cevirmen", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("mahkeme çevirmeni", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("mahkeme cevirmeni", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("tercüman", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("tercuman", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("çevirmen", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("cevirmen", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("icra müdür yardımcısı", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra mudur yardimcisi", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra müdürü", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra muduru", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra görevlisi", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra gorevlisi", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra memuru", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("noterin adı soyadı", "NOTARY", EntityType.NOTARY_NAME),
    ("noterin adi soyadi", "NOTARY", EntityType.NOTARY_NAME),
    ("noterlik görevini yürüten", "NOTARY", EntityType.NOTARY_NAME),
    ("noterlik gorevini yuruten", "NOTARY", EntityType.NOTARY_NAME),
    ("noter", "NOTARY", EntityType.NOTARY_NAME),
    ("hakem heyeti başkanı", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("hakem heyeti baskani", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("hakem kurulu üyesi", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("hakem kurulu uyesi", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("tek hakem", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("hakem", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
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
    ("müşteki / sanık", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("musteki / sanik", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("müşteki/sanık", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("musteki/sanik", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("müşteki-sanık", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("musteki-sanik", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("müşteki sanık", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("musteki sanik", "COMPLAINANT_ACCUSED", EntityType.COMPLAINANT_ACCUSED_NAME),
    ("müşteki-şüpheli", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("musteki-supheli", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("katılan müşteki", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katilan musteki", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katılan-müşteki", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katilan-musteki", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("müşteki katılan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("musteki katilan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("müşteki-katılan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("musteki-katilan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("mağdur-katılan", "VICTIM", EntityType.VICTIM_NAME),
    ("magdur-katilan", "VICTIM", EntityType.VICTIM_NAME),
    ("mağdur katılan", "VICTIM", EntityType.VICTIM_NAME),
    ("magdur katilan", "VICTIM", EntityType.VICTIM_NAME),
    ("katılan-mağdur", "VICTIM", EntityType.VICTIM_NAME),
    ("katilan-magdur", "VICTIM", EntityType.VICTIM_NAME),
    ("katılan mağdur", "VICTIM", EntityType.VICTIM_NAME),
    ("katilan magdur", "VICTIM", EntityType.VICTIM_NAME),
    ("suç mağduru", "VICTIM", EntityType.VICTIM_NAME),
    ("suc magduru", "VICTIM", EntityType.VICTIM_NAME),
    ("mağdur çocuk", "VICTIM", EntityType.VICTIM_NAME),
    ("magdur cocuk", "VICTIM", EntityType.VICTIM_NAME),
    ("şüphelinin adı soyadı", "SUSPECT", EntityType.SUSPECT_NAME),
    ("suphelinin adi soyadi", "SUSPECT", EntityType.SUSPECT_NAME),
    ("şüpheliler", "SUSPECT", EntityType.SUSPECT_NAME),
    ("supheliler", "SUSPECT", EntityType.SUSPECT_NAME),
    ("şüpheli", "SUSPECT", EntityType.SUSPECT_NAME),
    ("supheli", "SUSPECT", EntityType.SUSPECT_NAME),
    ("sanığın adı soyadı", "ACCUSED", EntityType.ACCUSED_NAME),
    ("sanigin adi soyadi", "ACCUSED", EntityType.ACCUSED_NAME),
    ("suça sürüklenen çocuk", "ACCUSED", EntityType.ACCUSED_NAME),
    ("suca suruklenen cocuk", "ACCUSED", EntityType.ACCUSED_NAME),
    ("ssç", "ACCUSED", EntityType.ACCUSED_NAME),
    ("ssc", "ACCUSED", EntityType.ACCUSED_NAME),
    ("sanıklar", "ACCUSED", EntityType.ACCUSED_NAME),
    ("saniklar", "ACCUSED", EntityType.ACCUSED_NAME),
    ("sanık", "ACCUSED", EntityType.ACCUSED_NAME),
    ("sanik", "ACCUSED", EntityType.ACCUSED_NAME),
    ("katılanlar", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katilanlar", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katılan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("katilan", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("müştekiler", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("mustekiler", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("müşteki", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("musteki", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("şikayetçiler", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("şikayetçi", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("şikâyetçi", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("sikayetci", "COMPLAINANT", EntityType.COMPLAINANT_NAME),
    ("mağdurlar", "VICTIM", EntityType.VICTIM_NAME),
    ("magdurlar", "VICTIM", EntityType.VICTIM_NAME),
    ("mağdur", "VICTIM", EntityType.VICTIM_NAME),
    ("magdur", "VICTIM", EntityType.VICTIM_NAME),
    ("müdahil", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("mudahil", "INTERVENOR", EntityType.INTERVENOR_NAME),
    ("kanuni temsilci", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("yasal temsilci", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("vasi", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("veli", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("kayyım", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("kayyim", "LEGAL_REPRESENTATIVE", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("arabulucunun adı soyadı", "MEDIATOR", EntityType.MEDIATOR_NAME),
    ("arabulucunun adi soyadi", "MEDIATOR", EntityType.MEDIATOR_NAME),
    ("arabulucu avukat", "MEDIATOR", EntityType.MEDIATOR_NAME),
    ("arabulucu", "MEDIATOR", EntityType.MEDIATOR_NAME),
    ("yeminli tercüman", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("yeminli tercuman", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("yeminli çevirmen", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("yeminli cevirmen", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("mahkeme çevirmeni", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("mahkeme cevirmeni", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("tercüman", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("tercuman", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("çevirmen", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("cevirmen", "INTERPRETER", EntityType.INTERPRETER_NAME),
    ("icra müdür yardımcısı", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra mudur yardimcisi", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra müdürü", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra muduru", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra görevlisi", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra gorevlisi", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("icra memuru", "ENFORCEMENT_OFFICER", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("noterin adı soyadı", "NOTARY", EntityType.NOTARY_NAME),
    ("noterin adi soyadi", "NOTARY", EntityType.NOTARY_NAME),
    ("noterlik görevini yürüten", "NOTARY", EntityType.NOTARY_NAME),
    ("noterlik gorevini yuruten", "NOTARY", EntityType.NOTARY_NAME),
    ("noter", "NOTARY", EntityType.NOTARY_NAME),
    ("hakem heyeti başkanı", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("hakem heyeti baskani", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("hakem kurulu üyesi", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("hakem kurulu uyesi", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("tek hakem", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
    ("hakem", "ARBITRATOR", EntityType.ARBITRATOR_NAME),
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
    ("duruşma savcısı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("durusma savcisi", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("cumhuriyet savcısı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("cumhuriyet savcisi", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("c. savcısı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("c.savcısı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("c. savcisi", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("savcı", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("savci", "PROSECUTOR", EntityType.PROSECUTOR_NAME),
    ("zabıt kâtibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("zabıt katibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("zabit katibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("mahkeme kâtibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("mahkeme katibi", "CLERK", EntityType.COURT_CLERK_NAME),
    ("kâtip", "CLERK", EntityType.COURT_CLERK_NAME),
    ("katip", "CLERK", EntityType.COURT_CLERK_NAME),
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


def _party_label_body() -> str:
    raw = sorted((item[0] for item in PARTY_ROLES), key=len, reverse=True)
    return "|".join(_pattern_for(label) for label in raw)


def party_label_pattern() -> re.Pattern[str]:
    return re.compile(
        rf"(?m)^\s*({_party_label_body()})(?:\s*-\s*\(\s*\d+\s*\)\s*-)?\s*:",
        re.IGNORECASE,
    )


def party_label_sentence_pattern() -> re.Pattern[str]:
    """A later party label, including one that starts after a period on the same line."""
    return re.compile(
        rf"(?:^|(?<=[.!?;\n]))\s*({_party_label_body()})"
        rf"(?:\s*-\s*\(\s*\d+\s*\)\s*-)?\s*:",
        re.IGNORECASE | re.MULTILINE,
    )


def counsel_label_pattern() -> re.Pattern[str]:
    raw = sorted((item[0] for item in COUNSEL_ROLES), key=len, reverse=True)
    body = "|".join(_pattern_for(label) for label in raw)
    return re.compile(rf"(?m)^\s*({body})\s*:", re.IGNORECASE)


_FOLDED_ROLE_TYPES = {
    EntityType.PROSECUTOR_NAME,
    EntityType.COURT_CLERK_NAME,
    EntityType.VICTIM_NAME,
    EntityType.COMPLAINANT_NAME,
    EntityType.SUSPECT_NAME,
    EntityType.ACCUSED_NAME,
    EntityType.COMPLAINANT_ACCUSED_NAME,
    EntityType.INTERVENOR_NAME,
    EntityType.LEGAL_REPRESENTATIVE_NAME,
    EntityType.MEDIATOR_NAME,
    EntityType.INTERPRETER_NAME,
    EntityType.ENFORCEMENT_OFFICER_NAME,
    EntityType.NOTARY_NAME,
    EntityType.ARBITRATOR_NAME,
}


def officer_role_body() -> str:
    """Case-folded role labels for adjacent-name grammar.

    ``re.IGNORECASE`` does not fold dotted İ. This body covers prosecutor,
    clerk, and the other role-specific labels so all-caps court lines match.
    """
    labels = sorted(
        (
            name
            for name, _role, entity_type in PERSON_TRIGGERS
            if entity_type in _FOLDED_ROLE_TYPES
        ),
        key=len,
        reverse=True,
    )
    return "|".join(_pattern_for(label) for label in labels)


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
