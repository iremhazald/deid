"""Advanced Turkish legal document detectors using grammar patterns and gazetteers."""

from __future__ import annotations

import re
from typing import Iterable

from app.detectors.gazetteers import (
    TURKISH_CITIES,
    TURKISH_DISTRICTS,
    TURKISH_INSTITUTIONS,
)
from app.detectors.textutil import fold_tr
from app.detectors.registry import PageText, _candidate
from app.domain.models import DetectionMethod, EntityCandidate, EntityType


# Institution patterns
# Matches: "Ankara Cumhuriyet Başsavcılığı", "İstanbul Emniyet Müdürlüğü"
INSTITUTION_PATTERN = re.compile(
    r"\b("
    + "|".join(re.escape(city) for city in sorted(TURKISH_CITIES, key=len, reverse=True))
    + r")\s+(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+)?"
    + r"(?:"
    + "|".join(re.escape(inst) for inst in sorted(TURKISH_INSTITUTIONS, key=len, reverse=True))
    + r")",
    re.IGNORECASE,
)

# Case/file number patterns
# E.2021/1234, Esas: 2020/456, C.Savcılığı Esas No: 2025/4539
# Karar: 2021/789, Dosya No: 2025/198 Esas
# Talimat No: 2025/203 Talimat  (İ/I variants — IGNORECASE does not fold İ)
_LEGAL_NUMBER = r"(\d{4}\s*/\s*\d+(?:\s+Esas)?)"
_TALIMAT = r"[Tt]al[iıIİ]mat"
_FILE_DOCKET = rf"(\d{{4}}\s*/\s*\d+(?:\s+(?:Esas|{_TALIMAT}))?)"
CASE_NUMBER_PATTERN = re.compile(
    r"\b(?:E\.|Esas(?:\s+No)?[:.]?|C\.?\s*Savcılı[gğ]ı\s+Esas(?:\s+No)?[:.]?)\s*"
    + _LEGAL_NUMBER,
    re.IGNORECASE,
)
DECISION_NUMBER_PATTERN = re.compile(
    r"\b(?:K\.|Karar(?:\s+No)?[:.]?)\s*" + _LEGAL_NUMBER,
    re.IGNORECASE,
)
FILE_NUMBER_PATTERN = re.compile(
    rf"\b(?:Dosya(?:\s*[-–]\s*Karar)?|{_TALIMAT})(?:\s+No)?[:.]?\s*" + _FILE_DOCKET,
    re.IGNORECASE,
)

# Number first, label after: 2023/57021 Soruşturma, 2025/4539 Esas, 2025/203 Talimat
_DOCKET_AFTER_LABEL = re.compile(
    rf"\b(?P<num>\d{{4}}\s*/\s*\d+)\s+"
    rf"(?P<label>Soruşturma|Esas|Karar|{_TALIMAT})\b",
    re.IGNORECASE,
)
_INDICTMENT_NUMBER = re.compile(
    r"\b(?P<num>\d{4}\s*/\s*\d+)\s+nolu\s+iddianame(?:si)?\b",
    re.IGNORECASE,
)
# Arbitration number: 2024/3234 başvuru dosya ve 2024/200740 arabuluculuk numarası
# Also: arabuluculuk no, arabuluculuk başvurusu
# Pattern 1: Number followed by arabuluculuk/başvuru label
_ARBITRATION_NUMBER = re.compile(
    r"\b(?P<num>\d{4}\s*/\s*\d+)\s+"
    r"(?:arabuluculuk\s+(?:numaras[ıi]|no|ba[şs]vurusu|dosyas[ıi])|ba[şs]vurusu|ba[şs]vuru)\b",
    re.IGNORECASE,
)
# Pattern 2: Label followed by number (arabuluculuk no: 2024/1234)
_ARBITRATION_PREFIX = re.compile(
    r"\b(?:arabuluculuk|ba[şs]vurusu|ba[şs]vuru)(?:\s+(?:numaras[ıi]|no|dosyas[ıi]))?\s*[:.]?\s*"
    r"(?P<num>\d{4}\s*/\s*\d+)\b",
    re.IGNORECASE,
)
_DOCKET_LABEL_TYPE = {
    "soruşturma": EntityType.FILE_NUMBER,
    "sorusturma": EntityType.FILE_NUMBER,
    "esas": EntityType.CASE_NUMBER,
    "karar": EntityType.DECISION_NUMBER,
    "talimat": EntityType.FILE_NUMBER,
    "arabuluculuk": EntityType.FILE_NUMBER,
}

# Turkish address patterns
# Matches: "Atatürk Caddesi 45/12 Çankaya/Ankara"
ADDRESS_PATTERN = re.compile(
    r"\b(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){0,3})\s+"
    r"(?:Caddesi|Bulvarı|Sokağı|Mahallesi)\s+"
    r"(?:No:?\s*)?\d+(?:/\d+)?\s+"
    r"(?:("
    + "|".join(re.escape(district) for district in sorted(TURKISH_DISTRICTS, key=len, reverse=True))
    + r")/)?("
    + "|".join(re.escape(city) for city in sorted(TURKISH_CITIES, key=len, reverse=True))
    + r")",
    re.IGNORECASE,
)

# Legal role patterns
# Title may be glued to the name in OCR ("Av.İrem"). Name tokens may be ALL CAPS.
_ROLE_TITLE = (
    r"(?:[Aa][Vv]\.?|[Aa][Vv][Uu][Kk][Aa][Tt]"
    r"|[Hh][Aa][Kk][İIıi][Mm]|[Hh][Ââ][Kk][İIıi][Mm]"
    r"|[Yy][Aa][Rr][Gg][Iİıi][ÇçCc]"
    r"|[Ss][Aa][Vv][Cc][Iİıi]"
    r"|[Bb][Aa][ŞşSs][Kk][Aa][Nn]"
    r"|[ÜüUu][Yy][Ee]"
    r"|[Kk][ÂâAa][Tt][İIıi][Pp]"
    r"|[Dd][Rr]\.?"
    r"|[Bb][İIıi][Ll][İIıi][Rr][Kk][İIıi][ŞşSs][İIıi]"
    r"|[Mm][ÜüUu][Dd][Aa][Ff][İIıi])"
)
_ROLE_NAME = (
    r"([A-ZÇĞİÖŞÜÂÎÛ]"
    r"[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+"
    r"(?:\s+[A-ZÇĞİÖŞÜÂÎÛ][A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+){1,3})"
)
LEGAL_ROLE_PREFIX = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü]){_ROLE_TITLE}\s*{_ROLE_NAME}"
)

# Turkish vehicle plate with province code validation
# Valid formats: 34 ABC 1234, 06 XYZ 123
# Province codes: 01-81 (Turkish administrative divisions)
VEHICLE_PLATE = re.compile(r"\b([1-7]\d|0[1-9]|80|81)\s+([A-Z]{1,3})\s+(\d{2,4})\b")
_PLATE_LETTER_STOP = frozenset(
    {"NO", "KAT", "MAH", "SOK", "CAD", "SK", "CD", "APT", "HAN", "BLK", "BLOK"}
)

# Turkish date patterns - detect only with birth/identity context to reduce false positives
# 12.03.2023, 01/05/2022
TURKISH_DATE = re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{4}\b")
DATE_CONTEXT_KEYWORDS = frozenset({
    "doğum", "dogum", "doğum tarihi", "dogum tarihi",
    "d.t.", "d.tarihi",
    "kimlik", "nüfus", "nufus",
})

# Postal code (5 digits, starts with 0-8)
POSTAL_CODE = re.compile(r"\b[0-8]\d{4}\b")

# UYAP citizen-portal footer: URL plus the one-time access token on that line.
UYAP_VATANDAS = re.compile(
    r"(?:https?://)?(?:www\.)?vatandas\.uyap\.gov\.tr",
    re.IGNORECASE,
)
UYAP_ACCESS_TAIL = re.compile(
    r"[ \t-]*[A-Za-z0-9+/=]{3,}(?:[ \t]*-[ \t]*[A-Za-z0-9+/=]{2,}){0,8}"
)
UYAP_STOP = re.compile(r"ile\s+erişebilirsin(?:iz)?\.?", re.IGNORECASE)
UYAP_FOOTER_CUE = re.compile(
    r"UYAP\s+Bilişim|adresinden|ile\s+erişebilirsin",
    re.IGNORECASE,
)


def detect_turkish_advanced(page: PageText) -> Iterable[EntityCandidate]:
    """Advanced Turkish legal document detection using grammar + gazetteer."""

    # Court names are owned by parse_courts (TR_LEGAL_STRUCTURE). 
    # Institutions
    for match in INSTITUTION_PATTERN.finditer(page.text):
        # Don't mark as PII, these are public entities
        pass  # Could add ORGANISATION type if needed
    
    # Case/decision/file numbers — capture the docket value only
    for match in CASE_NUMBER_PATTERN.finditer(page.text):
        yield _candidate(page, match, EntityType.CASE_NUMBER, "TR_CASE_NUMBER", group=1)
    
    for match in DECISION_NUMBER_PATTERN.finditer(page.text):
        yield _candidate(page, match, EntityType.DECISION_NUMBER, "TR_DECISION_NUMBER", group=1)
    
    for match in FILE_NUMBER_PATTERN.finditer(page.text):
        yield _candidate(page, match, EntityType.FILE_NUMBER, "TR_FILE_NUMBER", group=1)

    for match in _DOCKET_AFTER_LABEL.finditer(page.text):
        folded = fold_tr(match.group("label")).replace("\u0307", "")
        entity_type = _DOCKET_LABEL_TYPE.get(folded, EntityType.FILE_NUMBER)
        detector = {
            EntityType.CASE_NUMBER: "TR_CASE_NUMBER",
            EntityType.DECISION_NUMBER: "TR_DECISION_NUMBER",
        }.get(entity_type, "TR_FILE_NUMBER")
        yield _candidate(
            page,
            match,
            entity_type,
            detector,
            group="num",
        )

    for match in _INDICTMENT_NUMBER.finditer(page.text):
        yield _candidate(page, match, EntityType.FILE_NUMBER, "TR_FILE_NUMBER", group="num")
    
    # Arbitration numbers
    for match in _ARBITRATION_NUMBER.finditer(page.text):
        yield _candidate(page, match, EntityType.FILE_NUMBER, "TR_ARBITRATION_NUMBER", group="num")
    
    for match in _ARBITRATION_PREFIX.finditer(page.text):
        yield _candidate(page, match, EntityType.FILE_NUMBER, "TR_ARBITRATION_NUMBER", group="num")
    
    # Addresses
    for match in ADDRESS_PATTERN.finditer(page.text):
        yield _candidate(page, match, EntityType.ADDRESS, "TR_ADDRESS_GRAMMAR")
    
    # Legal roles with names — group 1 is the name; the title stays outside the span.
    for match in LEGAL_ROLE_PREFIX.finditer(page.text):
        title = match.group(0)[: match.start(1) - match.start()]
        role_type = fold_tr(re.sub(r"[.\s]+", "", title))
        entity_type = EntityType.PERSON_NAME
        role = None
        if role_type.startswith("av") or "avukat" in role_type or "mudafi" in role_type:
            entity_type = EntityType.LAWYER_NAME
            role = "COUNSEL"
        elif any(token in role_type for token in ("hakim", "yargic", "yargıç", "baskan", "uye")):
            entity_type = EntityType.JUDGE_NAME
            role = "JUDGE"
        elif "savci" in role_type:
            entity_type = EntityType.PERSON_NAME
            role = "PROSECUTOR"
        elif "katip" in role_type:
            entity_type = EntityType.PERSON_NAME
            role = "CLERK"
        elif "bilirkisi" in role_type or "bilirkişi" in role_type:
            entity_type = EntityType.EXPERT_NAME

        candidate = _candidate(page, match, entity_type, "TR_LEGAL_ROLE_NAME", group=1)
        if role:
            candidate = candidate.model_copy(update={"role": role})
        yield candidate
    
    # Vehicle plates
    for match in VEHICLE_PLATE.finditer(page.text):
        if match.group(2).upper() in _PLATE_LETTER_STOP:
            continue
        yield _candidate(page, match, EntityType.VEHICLE_PLATE, "TR_VEHICLE_PLATE")
    
    # Dates - only with birth/identity context to avoid false positives
    for match in TURKISH_DATE.finditer(page.text):
        # Check 30 chars before the date for context keywords
        context_start = max(0, match.start() - 30)
        context = page.text[context_start:match.start()].lower()
        if any(keyword in context for keyword in DATE_CONTEXT_KEYWORDS):
            yield _candidate(page, match, EntityType.DATE_OF_BIRTH, "TR_DATE_FORMAT")
    
    # UYAP footer access line (URL + document token) — whole line
    yield from _detect_uyap_footer(page)

    # Postal codes - only with explicit context
    for match in POSTAL_CODE.finditer(page.text):
        # Only yield if preceded by "posta kodu:" or similar
        context = page.text[max(0, match.start()-20):match.start()].lower()
        if "posta" in context or "kod" in context:
            yield _candidate(page, match, EntityType.POSTAL_CODE, "TR_POSTAL_CODE")


def _line_bounds(text: str, index: int) -> tuple[int, int]:
    start = index
    while start > 0 and text[start - 1] not in "\n\r":
        start -= 1
    end = index
    while end < len(text) and text[end] not in "\n\r":
        end += 1
    return start, end


def _uyap_footer_end(text: str, host_end: int, line_end: int) -> int:
    """Include the access token and the closing 'ile erişebilirsin' phrase."""
    window = min(len(text), host_end + 400)
    stop = UYAP_STOP.search(text, host_end, window)
    if stop:
        return stop.end()
    end = line_end
    cursor = line_end
    for _ in range(3):
        while cursor < len(text) and text[cursor] in "\r\n":
            cursor += 1
        if cursor >= len(text):
            break
        next_end = cursor
        while next_end < len(text) and text[next_end] not in "\r\n":
            next_end += 1
        chunk = text[cursor:next_end]
        stop = UYAP_STOP.search(text, cursor, next_end)
        if stop:
            return stop.end()
        if UYAP_ACCESS_TAIL.match(chunk) or re.search(r"[A-Za-z0-9+/=]{4,}\s*-", chunk):
            end = next_end
            cursor = next_end
            continue
        break
    return end


def _has_uyap_access_payload(text: str, host_end: int, end: int) -> bool:
    tail = text[host_end:end]
    if UYAP_STOP.search(tail) or UYAP_FOOTER_CUE.search(text[max(0, host_end - 80) : end]):
        return True
    return bool(re.search(r"[A-Za-z0-9+/=]{4,}\s*-\s*[A-Za-z0-9+/=]{2,}", tail))


def _detect_uyap_footer(page: PageText) -> Iterable[EntityCandidate]:
    seen: set[tuple[int, int]] = set()
    for match in UYAP_VATANDAS.finditer(page.text):
        start, line_end = _line_bounds(page.text, match.start())
        end = _uyap_footer_end(page.text, match.end(), line_end)
        if not _has_uyap_access_payload(page.text, match.end(), end):
            continue
        span = (start, end)
        if span in seen:
            continue
        seen.add(span)
        raw = page.text[start:end]
        value = raw.strip()
        if not value:
            continue
        lead = len(raw) - len(raw.lstrip())
        span_start = start + lead
        span_end = span_start + len(value)
        yield EntityCandidate(
            text=value,
            type=EntityType.UYAP_ACCESS,
            start=page.document_offset + span_start,
            end=page.document_offset + span_end,
            page=page.page,
            detector="TR_UYAP_FOOTER",
            method=DetectionMethod.DETERMINISTIC,
            validated=True,
            reason="UYAP citizen-portal access line.",
        )
