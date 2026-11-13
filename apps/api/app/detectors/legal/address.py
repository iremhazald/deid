"""Address token-sequence parser for Turkish legal documents."""

from __future__ import annotations

import re

from app.detectors.gazetteers import TURKISH_CITIES, TURKISH_DISTRICTS
from app.detectors.legal.common import fold_tr, make_candidate
from app.detectors.legal.names import clip_trailing_uets_span
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate, EntityType

_MARKERS: tuple[tuple[str, str], ...] = (
    (r"mahallesi|mahalle|mah\.?", "mah"),
    (r"caddesi|cadde|cad\.?|cd\.?", "cad"),
    (r"sokağı|sokagi|sokak|sok\.?|sk\.?", "sok"),
    (r"bulvarı|bulvari|bul\.?|blv\.?", "bul"),
    (r"küme\s+evleri|kume\s+evleri", "kume"),
    (r"mevkii|mevki", "mevki"),
    (r"sitesi", "site"),
    (r"apartmanı|apartmani|apt\.?", "apt"),
    (r"blok", "blok"),
    (r"iç\s+kapı\s+no:?|ic\s+kapi\s+no:?", "ickapi"),
    (r"dış\s+kapı\s+no:?|dis\s+kapi\s+no:?", "diskapi"),
    (r"no:?", "no"),
    (r"kat:?", "kat"),
    (r"daire:?", "daire"),
    (r"köyü|koyu", "koy"),
)

_MARKER_RE = re.compile(
    r"(?<![\w.])(?:"
    + "|".join(f"(?P<{name}>{pattern})" for pattern, name in _MARKERS)
    + r")(?=\s|[.,;:]|$)",
    re.IGNORECASE,
)
# Nüfus formula / residence verbs must not glue two address-like fragments.
_CLUSTER_BREAK = re.compile(
    r"n[uü]fusunda|kay[iı]tl[iı]|adresinde|oturur|do[gğ]umlu|\bUETS\b",
    re.IGNORECASE,
)
_TRAILING_BOILERPLATE = re.compile(
    r"(?is)\s+(?:n[uü]fusunda|kay[iı]tl[iı]|olup\b|adresinde|oturur|t\.?\s*c\.?\s*kimlik).*$"
)
_IDENTITY_NO_PREFIX = re.compile(
    r"(?i)(?:t\.?\s*c\.?\s*)?(?:kimlik|tckn|vergi|vkn|sicil)\s*$",
)
_PREFIX_NAME = re.compile(
    r"((?:\d{1,3}\.\s*[A-ZÇĞİÖŞÜÂÎÛ][A-Za-zÇĞİÖŞÜçğıöşüâîû0-9]+,\s+)?"
    r"(?:\d{1,3}\.\s*)?[A-ZÇĞİÖŞÜÂÎÛ][A-Za-zÇĞİÖŞÜçğıöşüâîû0-9]+"
    r"(?:\s+[A-ZÇĞİÖŞÜÂÎÛ][A-Za-zÇĞİÖŞÜçğıöşüâîû0-9]+){0,2})\s*$",
)
_CITY_RE = re.compile(
    r"\b("
    + "|".join(re.escape(name) for name in sorted(TURKISH_CITIES | TURKISH_DISTRICTS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
_SLASH_PLACE = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+)\s*/\s*([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+)\b"
)
# House number and door token between the street marker and the city.
# "156/A" must not block "Beşiktaş/İstanbul". A word does not count as a door.
_PLACE_LEAD = re.compile(r"[\s.:-]*(?:\d+(?:\s*/\s*[A-Za-z0-9]{1,4})?[\s.:-]*)*")


def place_tail_end(tail: str) -> int | None:
    """Include a district and the city that follows it.

    ``Kadıköy İstanbul`` and ``Konak/İzmir`` are one place. The house number
    between the street and that place stays inside the span.
    """
    cursor = 0
    end: int | None = None
    first = True
    while cursor < len(tail):
        rest = tail[cursor:]
        options: list[re.Match[str]] = []
        for match in (_SLASH_PLACE.search(rest), _CITY_RE.search(rest)):
            if match is None:
                continue
            gap = rest[: match.start()]
            if first:
                if gap and _PLACE_LEAD.fullmatch(gap) is None:
                    continue
            elif gap.strip(" /"):
                continue
            options.append(match)
        if not options:
            break
        chosen = min(options, key=lambda match: (match.start(), match.start() - match.end()))
        new_end = cursor + chosen.end()
        if end is not None and new_end <= end:
            break
        end = new_end
        cursor = end
        first = False
        while cursor < len(tail) and tail[cursor] in " /":
            cursor += 1
    if end is not None:
        postal = re.match(r"\s+\d{5}\b", tail[end:])
        if postal:
            end += postal.end()
    return end

def _kind(match: re.Match[str]) -> str:
    for _pattern, name in _MARKERS:
        if match.group(name):
            return name
    return "other"


def _is_identity_no(text: str, match: re.Match[str]) -> bool:
    if _kind(match) != "no":
        return False
    return bool(_IDENTITY_NO_PREFIX.search(text[max(0, match.start() - 24) : match.start()]))


def parse_address_tokens(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    text = page.text
    markers = [item for item in _MARKER_RE.finditer(text) if not _is_identity_no(text, item)]
    if not markers:
        return found

    clusters: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = [markers[0]]
    for match in markers[1:]:
        gap = text[current[-1].end() : match.start()]
        if match.start() - current[-1].end() <= 80 and not _CLUSTER_BREAK.search(gap):
            current.append(match)
        else:
            clusters.append(current)
            current = [match]
    clusters.append(current)

    for cluster in clusters:
        kinds = {_kind(item) for item in cluster}
        street = kinds - {"no", "kat", "daire"}
        has_place = bool(_CITY_RE.search(text[cluster[0].start() : min(len(text), cluster[-1].end() + 40)]))
        has_slash = bool(_SLASH_PLACE.search(text[cluster[0].start() : min(len(text), cluster[-1].end() + 40)]))
        if not street:
            continue
        if len(kinds) < 2 and not (has_place or has_slash):
            continue

        start = cluster[0].start()
        prefix = text[max(0, start - 60) : start]
        lead = _PREFIX_NAME.search(prefix)
        if lead:
            start = start - len(prefix) + lead.start(1)

        end = cluster[-1].end()
        tail = text[end : min(len(text), end + 50)]
        cut = _CLUSTER_BREAK.search(tail)
        if cut:
            tail = tail[: cut.start()]
        place_end = place_tail_end(tail)
        if place_end:
            end = end + place_end

        raw = text[start:end]
        trimmed = _TRAILING_BOILERPLATE.sub("", raw)
        clipped = clip_trailing_uets_span(trimmed)
        if clipped is None:
            continue
        span = trimmed[clipped[0] : clipped[1]].strip(" ,;.")
        if len(span) < 8:
            continue
        # Do not emit a bare city/district as an address.
        if fold_tr(span) in {fold_tr(name) for name in TURKISH_CITIES | TURKISH_DISTRICTS}:
            continue
        found.append(
            make_candidate(
                page,
                text=span,
                local_start=start,
                local_end=start + clipped[1],
                entity_type=EntityType.ADDRESS,
                detector="TR_ADDRESS_TOKENS",
                reason="Address token sequence.",
                attributes={"markers": sorted(kinds)},
            )
        )
    return found
