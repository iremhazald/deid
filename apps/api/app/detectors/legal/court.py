"""Court-name spans: inline prose and stacked gerekçeli-karar letterheads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.detectors.gazetteers import TURKISH_CITIES, TURKISH_COURTS, TURKISH_DISTRICTS
from app.detectors.textutil import fold_tr

if TYPE_CHECKING:
    from app.detectors.registry import PageText
    from app.domain.models import EntityCandidate

_OPEN_ERRORS = (OSError, ValueError, RuntimeError)


_ASCII_TR = str.maketrans({
    "ğ": "g",
    "ü": "u",
    "ş": "s",
    "ı": "i",
    "ö": "o",
    "ç": "c",
    "â": "a",
    "î": "i",
    "û": "u",
})


def _fold(value: str) -> str:
    return fold_tr(value).replace("\u0307", "")


def _ascii_tr(value: str) -> str:
    """Match AĞIR / AGIR / Ağır despite PDF fonts dropping diacritics."""
    return _fold(value).translate(_ASCII_TR)


def _strip_noise(value: str) -> str:
    """Default PDF fonts often emit · instead of İ/Ğ."""
    return value.replace("·", "").replace("•", "").replace("\ufffd", "")


def _flex_words(name: str) -> str:
    parts = [re.escape(part) for part in name.split() if part]
    return r"\s+".join(parts) if parts else re.escape(name)


def _court_tail_pattern() -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for name in sorted(TURKISH_COURTS, key=len, reverse=True):
        for form in (name, _ascii_tr(name)):
            token = _flex_words(form)
            if token not in seen:
                seen.add(token)
                parts.append(token)
    return "|".join(parts)


_CITY = "|".join(re.escape(name) for name in sorted(TURKISH_CITIES, key=len, reverse=True))
_TAIL = _court_tail_pattern()
_REGION = r"(?:Anadolu|Avrupa)"
_ORDINAL = r"\d{1,3}\s*\."
_WS = r"\s+"
_DAIRESI = r"Daires[iıIİ]"
_CHAMBER = rf"(?:\s+{_ORDINAL}\s+(?:[A-ZÇĞİÖŞÜa-zçğıöşüÂÎÛâîû]+\s+){{0,4}}{_DAIRESI})"
_CITY_FOLDS = {_fold(name) for name in TURKISH_CITIES}
_DISTRICT_FOLDS = {_fold(name) for name in TURKISH_DISTRICTS}
_PLACE_TOKEN = re.compile(
    r"^[A-ZÇĞİÖŞÜÂÎÛ][A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]{1,24}$"
)
_PLACE_STOP = frozenset(
    {
        "turk",
        "milleti",
        "adina",
        "geregi",
        "dusunuldu",
        "karar",
        "hukum",
        "gerekcesi",
        "davaci",
        "davali",
        "sanik",
        "katilan",
    }
)
_TAIL_RES = [
    re.compile(rf"^{_flex_words(_ascii_tr(name))}$", re.IGNORECASE)
    for name in sorted(TURKISH_COURTS, key=len, reverse=True)
]
_HIGH_COURT_MARKERS = (
    "yargitay",
    "danistay",
    "anayasa mahkemesi",
    "sayistay",
    "uyusmazlik mahkemesi",
    "bolge adliye mahkemesi",
    "bolge idare mahkemesi",
)
_BANNER_PROSE = re.compile(
    r"durus|erteledi|kararina|atif|gerekce|hukum|dusunuldu|belirttigi|"
    r"uyarinca|kararinda|yonelik|hakkinda",
    re.IGNORECASE,
)

# Mersin 9. Asliye Ceza Mahkemesi / İstanbul Anadolu 16. İş Mahkemesi
# Also stacked: MERSİN \n 9. \n AĞIR CEZA MAHKEMESİ
# BAM / Yargıtay: Adana Bölge Adliye Mahkemesi 8. Hukuk Dairesi
COURT_SPAN = re.compile(
    rf"(?<!\w)(?:(?:{_CITY}){_WS})?(?:{_REGION}{_WS})?(?:{_ORDINAL}\s*)?(?:{_TAIL}){_CHAMBER}?",
    re.IGNORECASE,
)
_CHAMBER_LINE = re.compile(
    rf"^{_ORDINAL}\s+(?:[A-ZÇĞİÖŞÜa-zçğıöşüÂÎÛâîû]+\s+){{0,4}}{_DAIRESI}\.?$",
    re.IGNORECASE,
)
LEADING_ORDINAL = re.compile(r"(\d{1,3}\s*\.)\s*$")
ORDINAL_IN_TEXT = re.compile(r"\b(\d{1,3})\s*\.")
TC_LINE = re.compile(r"^T\.?\s*C\.?$", re.IGNORECASE)
ORDINAL_ONLY = re.compile(r"^(\d{1,3})\s*\.$")
ORDINAL_THEN_TAIL = re.compile(rf"^({_ORDINAL})\s*(.+)$", re.IGNORECASE)
DOCKET_CUE = re.compile(
    r"(?<!\w)(?:dosya(?:\s*[-–]\s*karar)?(?:\s+no)?|karar\s*no)(?!\w)",
    re.IGNORECASE,
)
# Top-of-page header: mahkemesi and/or Dosya-Karar No (not a bare "dosya").
HEADER_CUE = re.compile(
    r"(?<!\w)(?:mahkemes[iı]|dosya\s*[-–]\s*karar(?:\s*no)?|dosya\s*no|karar\s*no)(?!\w)",
    re.IGNORECASE,
)
LEGAL_YEAR_NUM = re.compile(r"\d{4}\s*/\s*\d+")
HEADER_COURT = re.compile(
    rf"(?:T\.?\s*C\.?\s+)?(?:{_CITY}\s+)?(?:{_REGION}\s+)?(?:{_ORDINAL}\s+)?(?:{_TAIL})",
    re.IGNORECASE,
)
HEADER_LINE_SCOPE = "header_line"
TOP_HEADER_CM = 1.0
TOP_HEADER_PT = 72.0 / 2.54 * TOP_HEADER_CM
# Word boxes sit inside the ink; a short pad left serifs / dotted İ visible.
HEADER_MASK_PAD_PT = 4.0


def court_ordinal(text: str) -> str | None:
    match = ORDINAL_IN_TEXT.search(text)
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(0))


def is_high_court_name(text: str) -> bool:
    """Yargıtay / Anayasa / BAM and similar — detected, usually left visible."""
    folded = re.sub(r"\s+", " ", _ascii_tr(_fold(_strip_noise(text))))
    return any(marker in folded for marker in _HIGH_COURT_MARKERS)


def court_looks_like_banner(text: str) -> bool:
    """True for letterhead-style court lines, not running citations."""
    cut = re.sub(r"\s+", " ", _cut_docket(text)).strip()
    if not cut or len(cut) > 140:
        return False
    return not bool(_BANNER_PROSE.search(_ascii_tr(_fold(cut))))


def _is_page_opening(text: str, start: int) -> bool:
    if start < 480:
        return True
    return text[: max(0, start)].count("\n") < 3


def _is_chamber_line(value: str) -> bool:
    compact = re.sub(r"\s+", " ", _strip_noise(value)).strip()
    return bool(_CHAMBER_LINE.match(compact))


def _expand_trailing_chamber(text: str, start: int, end: int) -> tuple[int, int]:
    span = text[start:end]
    if court_ordinal(span) and re.search(_DAIRESI, span, re.IGNORECASE):
        return start, end
    nxt = _adjacent_line(text, end, direction=1)
    if nxt and _is_chamber_line(nxt[2]):
        return start, nxt[1]
    return start, end


def parse_courts(page: "PageText") -> list["EntityCandidate"]:
    from app.detectors.legal.common import make_candidate
    from app.domain.models import EntityType

    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()

    def add(start: int, end: int, *, force_header: bool = False) -> None:
        start, end = _expand_trailing_chamber(page.text, start, end)
        span = page.text[start:end]
        high = is_high_court_name(span)
        scope = None
        if not high and (force_header or _line_is_docket_header(page.text, start)):
            start, end = _expand_top_header_span(page.text, start)
            span = page.text[start:end]
            scope = HEADER_LINE_SCOPE
        if not high and not scope and not court_ordinal(span):
            return
        key = (start, end)
        if key in seen or end <= start:
            return
        seen.add(key)
        attributes = {
            "source": "court_span",
            "ordinal": court_ordinal(span),
            "court_kind": "high" if high else "local",
            "page_opening": _is_page_opening(page.text, start),
        }
        if scope:
            attributes["mask_scope"] = scope
        found.append(
            make_candidate(
                page,
                text=span,
                local_start=start,
                local_end=end,
                entity_type=EntityType.COURT_NAME,
                detector="TR_COURT_GRAMMAR",
                reason=(
                    "Top-of-page court / docket header line."
                    if scope
                    else "City, optional region, optional chamber number, and court type."
                ),
                attributes=attributes,
            )
        )

    for start, end in _page_top_header_spans(page.text):
        add(start, end, force_header=True)
    for match in COURT_SPAN.finditer(page.text):
        start, end = _expand_header_span(page.text, match.start(), match.end())
        add(start, end)
    for start, end in _letterhead_spans(page.text):
        add(start, end)
    return found


def _letterhead_spans(text: str) -> list[tuple[int, int]]:
    """T.C. / CITY / 9. COURT  — each piece may be its own extracted line."""
    lines = list(_iter_lines(text))
    spans: list[tuple[int, int]] = []
    used: set[int] = set()
    for index, (start, end, raw) in enumerate(lines):
        if index in used:
            continue
        ordinal, tail, span_start = _court_line_at(lines, index)
        if not tail or not _is_court_tail(tail):
            continue
        used.add(index)
        if ordinal and index > 0 and ORDINAL_ONLY.match(lines[index - 1][2].strip()):
            used.add(index - 1)
        city_start = span_start
        span_end = end
        if index + 1 < len(lines) and _is_chamber_line(lines[index + 1][2]):
            span_end = lines[index + 1][1]
            used.add(index + 1)
        for back in range(index - 1, max(-1, index - 4), -1):
            if back in used:
                continue
            candidate = lines[back][2].strip()
            if TC_LINE.match(candidate):
                continue
            if _is_place_line(candidate):
                city_start = lines[back][0]
                used.add(back)
            break
        spans.append((city_start, span_end))
    return spans


def _court_line_at(
    lines: list[tuple[int, int, str]], index: int
) -> tuple[str | None, str, int]:
    start, _end, raw = lines[index]
    stripped = raw.strip()
    headed = ORDINAL_THEN_TAIL.match(stripped)
    if headed and _is_court_tail(headed.group(2)):
        return re.sub(r"\s+", "", headed.group(1)), headed.group(2).strip(), start
    if _is_court_tail(stripped) and index > 0:
        previous = lines[index - 1][2].strip()
        only = ORDINAL_ONLY.match(previous)
        if only:
            return f"{only.group(1)}.", stripped, lines[index - 1][0]
    return None, stripped if _is_court_tail(stripped) else "", start


def _iter_lines(text: str) -> list[tuple[int, int, str]]:
    lines: list[tuple[int, int, str]] = []
    cursor = 0
    for chunk in text.splitlines(keepends=True):
        value = chunk.strip()
        if value:
            lead = len(chunk) - len(chunk.lstrip(" \t"))
            local_start = cursor + lead
            lines.append((local_start, local_start + len(value), value))
        cursor += len(chunk)
    return lines


def _has_header_cue(text: str) -> bool:
    folded = _ascii_tr(_fold(_strip_noise(text)))
    return bool(HEADER_CUE.search(folded))


def _has_docket_cue(text: str) -> bool:
    return bool(DOCKET_CUE.search(_ascii_tr(_fold(_strip_noise(text)))))


def _looks_like_letterhead_row(line: str) -> bool:
    """A short court banner, not running prose such as 'Mahkemesi duruşmayı…'."""
    cut = re.sub(r"\s+", " ", _cut_docket(line)).strip()
    if not _has_header_cue(cut):
        return False
    folded = _ascii_tr(_fold(cut))
    if re.search(r"durus|erteledi|kararina|atif|gerekce|hukum|dusunuldu", folded):
        return False
    if not re.search(r"\bt\.?\s*c\.?\b", folded) and not _span_has_city(cut):
        return False
    return bool(HEADER_COURT.search(cut)) or _is_court_tail(_split_ordinal_tail(cut)[1] or cut)


def _cut_docket(text: str) -> str:
    match = DOCKET_CUE.search(text)
    if not match:
        return text.strip()
    return text[: match.start()].strip(" \t-–—|")


def _is_docket_header_line(line: str) -> bool:
    return _has_docket_cue(line) or _looks_like_letterhead_row(line)


def _line_is_docket_header(text: str, index: int) -> bool:
    start, _end, raw = _line_at(text, index)
    if not _is_docket_header_line(raw):
        return False
    return start < 240 or text[: max(0, index)].count("\n") <= 2


def _page_top_header_spans(text: str) -> list[tuple[int, int]]:
    lines = _iter_lines(text)[:3]
    spans: list[tuple[int, int]] = []
    used: set[int] = set()
    for index, (start, end, raw) in enumerate(lines):
        if index in used or not _is_docket_header_line(raw):
            continue
        span_end = end
        if index + 1 < len(lines) and _is_docket_header_line(lines[index + 1][2]):
            span_end = lines[index + 1][1]
            used.add(index + 1)
        used.add(index)
        spans.append((start, span_end))
    return spans


def _expand_top_header_span(text: str, index: int) -> tuple[int, int]:
    start, end = _full_line_span(text, index)
    nxt_break = text.find("\n", end)
    if nxt_break >= 0:
        following = nxt_break + 1
        if following < len(text) and _line_is_docket_header(text, following):
            _nstart, nend = _full_line_span(text, following)
            end = nend
    prev_break = text.rfind("\n", 0, start)
    if prev_break >= 0:
        previous = prev_break - 1 if prev_break > 0 else 0
        if previous >= 0 and _line_is_docket_header(text, previous):
            pstart, _pend = _full_line_span(text, previous)
            start = min(start, pstart)
    return start, end


def _full_line_span(text: str, index: int) -> tuple[int, int]:
    start, end, raw = _line_at(text, index)
    lead = len(raw) - len(raw.lstrip())
    trail = len(raw) - len(raw.rstrip())
    return start + lead, end - trail


def _line_at(text: str, index: int) -> tuple[int, int, str]:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    if end < 0:
        end = len(text)
    return start, end, text[start:end]


def _is_court_tail(value: str) -> bool:
    compact = re.sub(r"\s+", " ", _ascii_tr(_strip_noise(value))).strip()
    if not compact:
        return False
    if any(pattern.fullmatch(compact) for pattern in _TAIL_RES):
        return True
    parts = compact.split()
    return len(parts) >= 2 and parts[-1].startswith("mahkemes")


def _expand_header_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Pull in a leading 9. and a nearby city line from official letterheads."""
    prefix = text[max(0, start - 8) : start]
    lead = LEADING_ORDINAL.search(prefix)
    if lead:
        start = start - (len(prefix) - lead.start())
    if not _span_has_city(text[start:end]):
        before = _adjacent_line(text, start, direction=-1)
        if before and _is_place_line(before[2]):
            start = before[0]
        else:
            after = _adjacent_line(text, end, direction=1)
            if after and _is_place_line(after[2]):
                end = after[1]
    return start, end


def _span_has_city(span: str) -> bool:
    folded = _ascii_tr(span)
    return any(city and _ascii_tr(city) in folded for city in _CITY_FOLDS)


def _is_city_line(line: str) -> bool:
    compact = re.sub(r"\s+", "", _ascii_tr(_strip_noise(line)))
    cities = {re.sub(r"\s+", "", _ascii_tr(city)) for city in _CITY_FOLDS}
    if compact in cities:
        return True
    return any(
        len(city) == len(compact) + 1
        and any(city[:index] + city[index + 1 :] == compact for index in range(len(city)))
        for city in cities
    )


def _is_place_line(line: str) -> bool:
    """Province, district, or the short all-caps place row of a stacked letterhead."""
    stripped = _strip_noise(line).strip()
    if not stripped or TC_LINE.match(stripped):
        return False
    if _has_docket_cue(stripped) or _is_court_tail(stripped) or ORDINAL_ONLY.match(stripped):
        return False
    if _is_city_line(stripped):
        return True
    compact = re.sub(r"\s+", "", _ascii_tr(stripped))
    districts = {re.sub(r"\s+", "", _ascii_tr(name)) for name in _DISTRICT_FOLDS}
    if compact in districts:
        return True
    tokens = stripped.split()
    if not 1 <= len(tokens) <= 3 or len(stripped) > 32:
        return False
    if any(char.isdigit() for char in stripped):
        return False
    if any(_ascii_tr(_fold(token)) in _PLACE_STOP for token in tokens):
        return False
    return all(_PLACE_TOKEN.match(token) for token in tokens)


def _adjacent_line(text: str, index: int, direction: int) -> tuple[int, int, str] | None:
    if direction < 0:
        cursor = index
        while cursor > 0 and text[cursor - 1] in "\r\n":
            cursor -= 1
        if cursor <= 0:
            return None
        line_start = text.rfind("\n", 0, cursor) + 1
        raw = text[line_start:cursor]
    else:
        cursor = index
        while cursor < len(text) and text[cursor] in "\r\n":
            cursor += 1
        if cursor >= len(text):
            return None
        line_end = text.find("\n", cursor)
        if line_end < 0:
            line_end = len(text)
        raw = text[cursor:line_end]
        line_start = cursor
        cursor = line_end
    value = raw.strip()
    if not value or TC_LINE.match(value):
        return None
    lead = len(raw) - len(raw.lstrip())
    trail = len(raw) - len(raw.rstrip())
    return line_start + lead, cursor - trail, value


def detect_court_letterheads(source_path: Path, document_text: str) -> list["EntityCandidate"]:
    """Read T.C. / city / N. court from PDF word boxes, not only extracted newlines."""
    import pymupdf

    from app.domain.models import DetectionMethod, EntityCandidate, EntityType, ManualRect

    try:
        document = pymupdf.open(str(source_path))
    except _OPEN_ERRORS:
        return []
    found: list[EntityCandidate] = []
    try:
        for page_number in range(document.page_count):
            page = document[page_number]
            headers = _top_centimeter_header_lines(page)
            if headers:
                page_text = page.get_text() or ""
                emitted = False
                for box, label in headers:
                    if is_high_court_name(label):
                        continue
                    start, end = _header_text_offsets(document_text, page_text, label, page_number)
                    found.append(
                        EntityCandidate(
                            text=label.strip() or "T.C. mahkeme başlığı",
                            type=EntityType.COURT_NAME,
                            start=start,
                            end=end,
                            page=page_number,
                            detector="TR_COURT_LETTERHEAD",
                            method=DetectionMethod.DETERMINISTIC,
                            validated=True,
                            reason="First centimetre of the page contains a court / docket header.",
                            rectangles=[
                                ManualRect(
                                    x0=float(box.x0),
                                    y0=float(box.y0),
                                    x1=float(box.x1),
                                    y1=float(box.y1),
                                )
                            ],
                            attributes={
                                "source": "court_top_band",
                                "mask_scope": HEADER_LINE_SCOPE,
                                "ordinal": court_ordinal(label),
                                "court_kind": "local",
                                "page_opening": True,
                            },
                        )
                    )
                    emitted = True
                if emitted:
                    continue
            if page_number >= 8:
                continue
            lines = _pdf_lines(page)
            hit = _letterhead_from_lines(lines)
            if hit is None:
                continue
            city, ordinal, tail, boxes, ordinal_box = hit
            label = " ".join(part for part in (city, ordinal, tail) if part)
            start = document_text.find(label) if label else -1
            if start < 0:
                # Stacked letterhead is not one contiguous span. Binding to the
                # tail ("Ağır Ceza Mahkemesi") steals the body citation; the
                # preview then paints "Mersin …" onto the word "Ceza".
                start = len(document_text) + 2000 + page_number * 8
                end = start + max(1, len(label))
            else:
                end = start + len(label)
            attributes: dict[str, Any] = {
                "source": "court_letterhead",
                "ordinal": ordinal,
                "court_kind": "high" if is_high_court_name(label) else "local",
                "page_opening": True,
            }
            if ordinal_box is not None:
                attributes["ordinal_rect"] = {
                    "x0": float(ordinal_box.x0),
                    "y0": float(ordinal_box.y0),
                    "x1": float(ordinal_box.x1),
                    "y1": float(ordinal_box.y1),
                }
            found.append(
                EntityCandidate(
                    text=label,
                    type=EntityType.COURT_NAME,
                    start=start,
                    end=end,
                    page=page_number,
                    detector="TR_COURT_LETTERHEAD",
                    method=DetectionMethod.DETERMINISTIC,
                    validated=True,
                    reason="Stacked gerekçeli karar letterhead.",
                    rectangles=[
                        ManualRect(x0=float(box.x0), y0=float(box.y0), x1=float(box.x1), y1=float(box.y1))
                        for box in boxes
                    ],
                    attributes=attributes,
                )
            )
    except _OPEN_ERRORS:
        return []
    finally:
        document.close()
    return found


def _pdf_lines(page: Any) -> list[tuple[Any, str, list[Any]]]:
    import pymupdf

    words = list(page.get_text("words") or [])
    if not words:
        return []
    words.sort(key=lambda item: (round(float(item[1]), 1), float(item[0])))
    grouped: list[list[Any]] = []
    for word in words:
        token = str(word[4]).strip()
        if not token:
            continue
        box = pymupdf.Rect(word[0], word[1], word[2], word[3])
        if grouped:
            previous = grouped[-1][-1]
            prev_box = pymupdf.Rect(previous[0], previous[1], previous[2], previous[3])
            same_line = abs(box.y0 - prev_box.y0) <= max(4.0, prev_box.height * 0.55)
            if same_line:
                grouped[-1].append(word)
                continue
        grouped.append([word])
    lines: list[tuple[Any, str, list[Any]]] = []
    for group in grouped:
        group.sort(key=lambda item: float(item[0]))
        text = _join_pdf_tokens([str(item[4]).strip() for item in group])
        box = pymupdf.Rect(group[0][0], group[0][1], group[0][2], group[0][3])
        for item in group[1:]:
            box |= pymupdf.Rect(item[0], item[1], item[2], item[3])
        lines.append((box, text, group))
    return lines


def page_line_rects(page: Any) -> list[Any]:
    """Word-union boxes for each visual line — used to clip overlay covers."""
    return [box for box, _text, _words in _pdf_lines(page)]


def _join_pdf_tokens(tokens: list[str]) -> str:
    merged: list[str] = []
    for token in tokens:
        if merged and token in {".", ",", ";", ":"}:
            merged[-1] += token
            continue
        merged.append(token)
    if merged and sum(1 for item in merged if len(item) == 1) >= max(3, len(merged) - 1):
        return "".join(merged)
    return " ".join(merged)


def _header_text_offsets(
    document_text: str, page_text: str, label: str, page_number: int
) -> tuple[int, int]:
    needle = (label.strip() or "")[:32]
    start = -1
    if needle:
        start = document_text.find(needle)
        if start < 0:
            start = page_text.find(needle)
            if start >= 0:
                page_origin = document_text.find(page_text[:24]) if page_text.strip() else -1
                if page_origin >= 0:
                    start += page_origin
    if start < 0:
        start = len(document_text) + 2000 + page_number * 8
        return start, start + max(1, len(label))
    line_start, line_end = _expand_top_header_span(document_text, start)
    return line_start, line_end


def _top_centimeter_header_lines(page: Any) -> list[tuple[Any, str]]:
    """Full-width paper mask for the docket strip in the first 1 cm.

    Stacked gerekçeli-karar titles (T.C. / CITY / 9. AĞIR CEZA MAHKEMESİ) also
    sit near the top, but only the chamber number should be blacked out.
    """
    import pymupdf

    band = float(page.rect.y0) + TOP_HEADER_PT
    lines = _pdf_lines(page)
    if not lines:
        return []
    hits: list[tuple[Any, str]] = []
    used: set[int] = set()
    for index, (box, text, _words) in enumerate(lines):
        if index in used:
            continue
        if float(box.y0) >= band:
            continue
        if not _has_header_cue(text):
            continue
        union = pymupdf.Rect(box)
        parts = [text]
        grouped = {index}
        mid = (float(box.y0) + float(box.y1)) / 2
        tol = max(6.0, float(box.height) * 0.75)
        for other_index, (other, other_text, _other_words) in enumerate(lines):
            if other_index in grouped:
                continue
            other_mid = (float(other.y0) + float(other.y1)) / 2
            if abs(other_mid - mid) <= tol:
                union |= other
                parts.append(other_text)
                grouped.add(other_index)
        label = " ".join(part for part in parts if part)
        if not _has_docket_cue(label):
            continue
        used.update(grouped)
        page_box = page.rect
        full = pymupdf.Rect(
            float(page_box.x0),
            max(float(page_box.y0), float(union.y0) - HEADER_MASK_PAD_PT),
            float(page_box.x1),
            min(float(page_box.y1), float(union.y1) + HEADER_MASK_PAD_PT),
        )
        hits.append((full, label))
    return hits


def _letterhead_from_lines(
    lines: list[tuple[Any, str, list[Any]]],
) -> tuple[str, str, str, list[Any], Any] | None:
    top = lines[:16]
    for index, (_box, text, words) in enumerate(top):
        ordinal, tail = _split_ordinal_tail(_cut_docket(text))
        if not tail or not _is_court_tail(tail):
            if _is_court_tail(text) and index > 0:
                prev_ord, prev_rest = _split_ordinal_tail(top[index - 1][1])
                if prev_ord and not prev_rest:
                    ordinal, tail = prev_ord, text
                else:
                    continue
            else:
                continue
        city = ""
        boxes = [_box]
        for back in range(index - 1, max(-1, index - 4), -1):
            other_box, other_text, _other_words = top[back]
            if TC_LINE.match(other_text.strip()):
                continue
            if _is_place_line(other_text):
                city = re.sub(r"\s+", "", other_text) if " " in other_text.strip() else other_text
                boxes.insert(0, other_box)
            break
        if not tail:
            continue
        if index + 1 < len(top) and _is_chamber_line(top[index + 1][1]):
            chamber_box, chamber_text, chamber_words = top[index + 1]
            ch_ord, _ch_rest = _split_ordinal_tail(chamber_text)
            if ch_ord:
                ordinal = ordinal or ch_ord
            tail = f"{tail} {chamber_text.strip()}".strip()
            boxes.append(chamber_box)
            words = list(words) + list(chamber_words)
        ordinal_box = _ordinal_box_from_words(words, ordinal) if ordinal else None
        if ordinal_box is None and index > 0 and ordinal:
            ordinal_box = _ordinal_box_from_words(top[index - 1][2], ordinal)
            boxes.insert(0, top[index - 1][0])
        return city, ordinal or "", tail, boxes, ordinal_box
    return None


def _split_ordinal_tail(text: str) -> tuple[str | None, str]:
    stripped = text.strip()
    only = ORDINAL_ONLY.match(stripped)
    if only:
        return f"{only.group(1)}.", ""
    headed = ORDINAL_THEN_TAIL.match(stripped)
    if headed:
        return re.sub(r"\s+", "", headed.group(1)), headed.group(2).strip()
    return None, stripped


def _ordinal_box_from_words(words: list[Any], ordinal: str) -> Any | None:
    import pymupdf

    digits = re.sub(r"\D", "", ordinal)
    if not digits:
        return None
    for index, word in enumerate(words):
        token = str(word[4]).strip()
        box = pymupdf.Rect(word[0], word[1], word[2], word[3])
        if token == ordinal or re.fullmatch(rf"{digits}\s*\.", token):
            return box
        if token == digits and index + 1 < len(words) and str(words[index + 1][4]).strip() == ".":
            nxt = words[index + 1]
            return box | pymupdf.Rect(nxt[0], nxt[1], nxt[2], nxt[3])
    return None
