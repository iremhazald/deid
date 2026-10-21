"""Organisation / authority / prosecutor-office emission."""

from __future__ import annotations

import re

from app.detectors.gazetteers import (
    AUTHORITY_PHRASES,
    TURKISH_BANKS,
    TURKISH_CITIES,
    TURKISH_COURTS,
    TURKISH_DISTRICTS,
    TURKISH_INSTITUTIONS,
    TURKISH_TELECOM,
)
from app.detectors.legal.common import fold_tr, make_candidate
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_CITY = "|".join(re.escape(name) for name in sorted(TURKISH_CITIES, key=len, reverse=True))
_PLACE_TOKEN = r"[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû'’.\-]{2,40}"
# PDF text layers often drop diacritics: Başsavcılığı / Bassavciligi.
_PROSECUTOR_OFFICE = r"Cumhuriyet\s+Ba[sş]\s*savc[iı]l[iı][gğ][iı]"
_PROSECUTOR = re.compile(
    rf"(?<!\w)(?:T\.?\s*C\.?\s+)?"
    rf"(?:(?P<place>{_PLACE_TOKEN}(?:\s+{_PLACE_TOKEN}){{0,2}})\s+)?"
    rf"{_PROSECUTOR_OFFICE}",
    re.IGNORECASE,
)
_PLACE_STOP = {
    "turkiye",
    "t.c",
    "tc",
    "adalet",
    "cumhuriyet",
    "ilgili",
    "soz",
    "konusu",
    "anilan",
    "bahse",
    "konu",
    "mahkeme",
    "savcilik",
    "adliye",
    "bakanlik",
    "yazisi",
    "karari",
}
# Leading tokens the 1–3 word place group may swallow before the city.
_PLACE_ROLE_STEMS = (
    "magdur",
    "sanik",
    "tanik",
    "musteki",
    "katilan",
    "davaci",
    "davali",
    "sahis",
    "kisi",
    "vekil",
    "mudafi",
)
_ASCII_PLACE = str.maketrans({
    "ğ": "g",
    "ü": "u",
    "ş": "s",
    "ö": "o",
    "ç": "c",
    "â": "a",
})
_PLACE_WORD = re.compile(r"\S+")
_PLACE_GAZETTEER = {
    fold_tr(name).replace("\u0307", "").replace("ı", "i")
    for name in TURKISH_CITIES | TURKISH_DISTRICTS
}

_ORG_BOUND = r"(?<![\wÇĞİÖŞÜçğıöşü])"
_ORG_END = r"(?![\wÇĞİÖŞÜçğıöşü])"
# "İNG Bankasından" / "Ziraat Bankası'nın" keep the inflected tail in the span.
_ORG_SUFFIX = r"(?:['’][A-Za-zÇĞİÖŞÜçğıöşü]{1,10}|[a-zçğıöşü]{1,10})?"
_BANK_RE = re.compile(
    _ORG_BOUND
    + r"(?P<bank>"
    + "|".join(re.escape(name) for name in sorted(TURKISH_BANKS, key=len, reverse=True))
    + r")"
    + r"(?P<suf>"
    + _ORG_SUFFIX
    + r")"
    + _ORG_END,
    re.IGNORECASE,
)
_BANK_TOKEN = r"[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü.&'’-]{0,40}"
_BANK_TAIL = r"(?:Bankası|Bankasi|Banka|Bank)(?:['’]?[a-zçğıöşü]{0,10})?"
_BANK_GRAMMAR = re.compile(
    rf"{_ORG_BOUND}(?P<bank>{_BANK_TOKEN}(?:\s+{_BANK_TOKEN}){{0,3}}\s+{_BANK_TAIL}){_ORG_END}",
    re.IGNORECASE,
)
_BANK_STOP = {
    "kan",
    "veri",
    "gen",
    "tohum",
    "sperma",
    "goz",
    "göz",
    "organ",
    "yumurta",
    "gida",
    "gıda",
    "kelime",
    "soru",
    "bilisim",
    "bilişim",
    "sistem",
    "sistemleri",
    "sistemler",
    "kredi",
    "kurum",
    "kurumlar",
    "kurumlari",
    "kurumları",
    "kurumlarinin",
    "kurumlarının",
    "arac",
    "araç",
    "dolandiricilik",
    "dolandırıcılık",
}
_STATUTE_AFTER_BANK = re.compile(
    r"^\s+veya\s+(?:kredi|kredi\s+kurum)",
    re.IGNORECASE,
)
_TEL_RE = re.compile(
    r"\b(" + "|".join(re.escape(name) for name in sorted(TURKISH_TELECOM, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_AUTH_RE = re.compile(
    r"\b("
    + "|".join(re.escape(name) for name in sorted(AUTHORITY_PHRASES | TURKISH_INSTITUTIONS | TURKISH_COURTS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
# "Silifke AGO da" — a place plus a short court/office desk, not a person name.
_LOCAL_DESK = re.compile(
    r"(?<![\wÇĞİÖŞÜçğıöşü])(?P<span>(?P<place>[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]{2,24})"
    r"\s+(?P<unit>AGO|BAM))(?![\wÇĞİÖŞÜçğıöşü])"
)
_CITY_INST = re.compile(
    rf"\b(?P<span>(?:{_CITY})\s+(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+)?"
    rf"(?:"
    + "|".join(re.escape(name) for name in sorted(TURKISH_INSTITUTIONS, key=len, reverse=True))
    + r"))",
    re.IGNORECASE,
)

_COURT_FOLDS = {fold_tr(name).replace("\u0307", "") for name in TURKISH_COURTS}


def _fold_place(value: str) -> str:
    return fold_tr(value).replace("\u0307", "").replace("ı", "i")


def _plausible_bank_span(value: str) -> bool:
    span = " ".join(value.split())
    tokens = span.split()
    if len(tokens) < 2:
        return False
    tail = re.sub(r"['’].*$", "", _fold_place(tokens[-1]))
    if not tail.startswith("bank"):
        return False
    heads = tokens[:-1]
    if any(_fold_place(token) in _BANK_STOP for token in heads):
        return False
    return all(token[0].isupper() for token in heads if token)


def iter_bank_spans(text: str) -> list[tuple[int, int, str]]:
    """Gazetteer names plus '{Ad} Bank/Banka/Bankası' grammar."""
    found: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int]] = set()

    def take(start: int, end: int, value: str) -> None:
        span = value.strip()
        if not span:
            return
        lead = len(value) - len(value.lstrip())
        start += lead
        end -= len(value) - len(value.rstrip())
        if start >= end:
            return
        for existing_start, existing_end in list(seen):
            if start < existing_end and end > existing_start:
                if (end - start) <= (existing_end - existing_start):
                    return
                seen.discard((existing_start, existing_end))
                found[:] = [
                    item for item in found if (item[0], item[1]) != (existing_start, existing_end)
                ]
        seen.add((start, end))
        found.append((start, end, text[start:end]))

    for match in _BANK_RE.finditer(text):
        take(match.start(), match.end(), match.group(0))
    for match in _BANK_GRAMMAR.finditer(text):
        raw = match.group("bank")
        if not _plausible_bank_span(raw):
            continue
        if _STATUTE_AFTER_BANK.match(text[match.end("bank") :]):
            continue
        take(match.start("bank"), match.end("bank"), raw)
    found.sort(key=lambda item: (item[0], item[1]))
    return found


def _is_place_junk(token: str) -> bool:
    folded = _fold_place(token)
    ascii_folded = folded.translate(_ASCII_PLACE)
    if not folded or folded in _PLACE_STOP or ascii_folded in _PLACE_STOP:
        return True
    return any(
        ascii_folded == stem or ascii_folded.startswith(stem)
        for stem in _PLACE_ROLE_STEMS
    )


def _prosecutor_place_span(value: str | None) -> tuple[str, int, int] | None:
    """Keep a 1–3 token place glued to 'Cumhuriyet Başsavcılığı'; gazetteer is optional.

    Drops leading role words so "Mağdurun Mersin Cumhuriyet Başsavcılığı" yields Mersin.
    Offsets are relative to ``value``.
    """
    if not value:
        return None
    pieces = [(match.start(), match.end(), match.group(0)) for match in _PLACE_WORD.finditer(value)]
    while pieces and _is_place_junk(pieces[0][2]):
        pieces.pop(0)
    if not pieces:
        return None
    start, end = pieces[0][0], pieces[-1][1]
    span = value[start:end]
    compact = re.sub(r"\s+", "", span)
    if not 2 <= len(compact) <= 40:
        return None
    if any(char.isdigit() for char in span):
        return None
    tokens = [token for _, _, token in pieces]
    if not 1 <= len(tokens) <= 3:
        return None
    folded_tokens = [_fold_place(token) for token in tokens]
    if any(item in _PLACE_STOP for item in folded_tokens):
        return None
    if _fold_place(span) in _PLACE_STOP:
        return None
    return span, start, end


def _prosecutor_place(value: str | None) -> str | None:
    kept = _prosecutor_place_span(value)
    return None if kept is None else kept[0]


def _place_in_gazetteer(span: str) -> bool:
    return any(_fold_place(token) in _PLACE_GAZETTEER for token in span.split())


def _is_court_label(label: str) -> bool:
    folded = fold_tr(label).replace("\u0307", "")
    return "mahkemesi" in folded or folded in _COURT_FOLDS


_KIND = {
    "BANK": "BANK",
    "TELECOM": "TELECOM_PROVIDER",
    "COURT": "COURT",
    "PROSECUTOR": "PROSECUTOR_OFFICE",
    "AUTHORITY": "PUBLIC_AUTHORITY",
}


def parse_organisations(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()

    def add_span(text: str, start: int, end: int, kind: str, entity_type: EntityType) -> None:
        if (start, end) in seen:
            return
        for existing_start, existing_end in list(seen):
            if start < existing_end and end > existing_start:
                if (end - start) <= (existing_end - existing_start):
                    return
        seen.add((start, end))
        found.append(
            make_candidate(
                page,
                text=text,
                local_start=start,
                local_end=end,
                entity_type=entity_type,
                detector="TR_ORG_AUTHORITY",
                reason="Gazetteer / authority grammar.",
                attributes={"org_kind": kind, "source": "organisation"},
            )
        )

    def add(match: re.Match[str], kind: str, entity_type: EntityType, group: int | str = 0) -> None:
        add_span(match.group(group), match.start(group), match.end(group), kind, entity_type)

    for match in _PROSECUTOR.finditer(page.text):
        place_raw = match.groupdict().get("place")
        kept = _prosecutor_place_span(place_raw)
        org_start = match.start()
        if place_raw:
            if kept:
                org_start = match.start("place") + kept[1]
            else:
                org_start = match.end("place")
                while org_start < match.end() and page.text[org_start].isspace():
                    org_start += 1
        add_span(
            page.text[org_start : match.end()],
            org_start,
            match.end(),
            "PROSECUTOR_OFFICE",
            EntityType.ORGANISATION,
        )
        if not kept:
            continue
        place, rel_start, rel_end = kept
        known = _place_in_gazetteer(place)
        found.append(
            make_candidate(
                page,
                text=place,
                local_start=match.start("place") + rel_start,
                local_end=match.start("place") + rel_end,
                entity_type=EntityType.LOCATION,
                detector="TR_ORG_AUTHORITY",
                reason="Place name attached to a prosecutor office.",
                validated=known,
                attributes={
                    "org_kind": "PROSECUTOR_CITY",
                    "source": "organisation",
                    "gazetteer_hit": known,
                },
            )
        )
    for match in _CITY_INST.finditer(page.text):
        add(match, "PUBLIC_AUTHORITY", EntityType.ORGANISATION, "span")
    for start, end, label in iter_bank_spans(page.text):
        add_span(label, start, end, "BANK", EntityType.ORGANISATION)
    for match in _TEL_RE.finditer(page.text):
        add(match, "TELECOM_PROVIDER", EntityType.ORGANISATION, 1)
    for match in _AUTH_RE.finditer(page.text):
        label = match.group(1)
        if _is_court_label(label):
            continue
        add(match, "PUBLIC_AUTHORITY", EntityType.ORGANISATION, 1)
    for match in _LOCAL_DESK.finditer(page.text):
        # AGO is Adli Görüşme Odası: a city desk that is masked as an institution.
        # BAM stays a place label; the court grammar owns the mahkeme span.
        unit = (match.group("unit") or "").upper()
        if unit == "AGO":
            add(match, "JUDICIAL_INTERVIEW_ROOM", EntityType.ORGANISATION, "span")
        else:
            add(match, "LOCAL_DESK", EntityType.LOCATION, "span")
    return found


_COMPANY_SUFFIX = re.compile(
    r"(?P<name>[A-ZÇĞİÖŞÜ0-9][A-Za-zÇĞİÖŞÜçğıöşü0-9'’&.-]{1,}"
    r"(?:[ \t]+[A-ZÇĞİÖŞÜ0-9][A-Za-zÇĞİÖŞÜçğıöşü0-9'’&.-]{1,}){0,6})[ \t]+"
    r"(?P<suffix>Anonim\s+Şirketi|A\.\s*Ş\.|AŞ|Limited\s+Şirketi|"
    r"Ltd\.?\s*(?:Ş|S)[tT][iİIı]\.?|Kooperatifi|Derneği|Vakfı|Sendikası)(?!\w)",
    re.IGNORECASE,
)
_PUBLIC_COMPANY_HINTS = (
    "mahkemesi",
    "savcılığı",
    "savciligi",
    "belediye",
    "valilik",
    "kaymakamlık",
    "kaymakamlik",
    "bakanlık",
    "bakanlik",
    "emniyet",
    "başsavcılık",
    "bassavcilik",
)


def parse_companies(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()
    for match in _COMPANY_SUFFIX.finditer(page.text):
        span = match.group(0)
        folded = span.casefold()
        if any(hint in folded for hint in _PUBLIC_COMPANY_HINTS):
            continue
        start, end = match.start(), match.end()
        if (start, end) in seen:
            continue
        seen.add((start, end))
        found.append(
            make_candidate(
                page,
                text=span,
                local_start=start,
                local_end=end,
                entity_type=EntityType.COMPANY_NAME,
                detector="TR_COMPANY_SUFFIX",
                reason="Legal-entity suffix grammar.",
                validated=False,
                attributes={"org_kind": "COMPANY", "source": "company_suffix"},
            )
        )
    return found
