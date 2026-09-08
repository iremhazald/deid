"""Bounded document index. Precomputed once per scan; no per-candidate full-document walks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.detectors.legal.names import collapse_name, strip_possessive
from app.detectors.legal.repeats import is_repeatable_person_name
from app.detectors.textutil import fold_tr_identity
from app.domain.models import EntityCandidate, EntityType

from app.detectors.scoring.policy import HIGH_CONFIDENCE_DETECTORS

_PERSON_TYPES = {
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

_DIGIT_NEIGHBOR = frozenset(
    " \t\r\n-./()[]\u00a0\u00ad\u2000\u2001\u2002\u2003\u2004\u2005"
    "\u2006\u2007\u2008\u2009\u200a\u200b\u202f\u2060\ufeff"
)


def person_surface_key(value: str) -> str:
    return fold_tr_identity("".join(collapse_name(strip_possessive(value)).split()))


@dataclass
class LineSpan:
    start: int
    end: int
    text: str


@dataclass
class DocumentIndex:
    pages: list[Any]
    full_text: str
    line_starts: list[int]
    iban_spans: list[tuple[int, int]] = field(default_factory=list)
    tckn_spans: list[tuple[int, int]] = field(default_factory=list)
    url_spans: list[tuple[int, int]] = field(default_factory=list)
    person_spans: list[tuple[int, int]] = field(default_factory=list)
    address_spans: list[tuple[int, int]] = field(default_factory=list)
    org_spans: list[tuple[int, int]] = field(default_factory=list)
    local_person_keys: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(cls, pages: list[Any], candidates: list[EntityCandidate]) -> "DocumentIndex":
        chunks: list[str] = []
        line_starts = [0]
        for page in pages:
            chunks.append(page.text)
        full_text = "".join(chunks)
        for match in re.finditer(r"\n", full_text):
            line_starts.append(match.end())
        index = cls(pages=pages, full_text=full_text, line_starts=line_starts)
        for item in candidates:
            span = (item.start, item.end)
            if item.type == EntityType.IBAN:
                index.iban_spans.append(span)
            elif item.type == EntityType.NATIONAL_ID:
                index.tckn_spans.append(span)
            elif item.type in {EntityType.URL, EntityType.SYSTEM_URL, EntityType.UYAP_ACCESS}:
                index.url_spans.append(span)
            elif item.type in _PERSON_TYPES:
                index.person_spans.append(span)
                if (
                    item.detector in HIGH_CONFIDENCE_DETECTORS
                    and is_repeatable_person_name(item.text)
                ):
                    key = person_surface_key(item.text)
                    if len(key) >= 6:
                        index.local_person_keys.setdefault(key, item.text)
            elif item.type == EntityType.ADDRESS:
                index.address_spans.append(span)
            elif item.type in {EntityType.ORGANISATION, EntityType.COMPANY_NAME, EntityType.COURT_NAME}:
                index.org_spans.append(span)
        return index

    def page_for(self, start: int) -> Any | None:
        for page in self.pages:
            local = start - page.document_offset
            if 0 <= local <= len(page.text):
                return page
        return self.pages[0] if self.pages else None

    def line_window(self, start: int, end: int) -> LineSpan:
        line_start = 0
        for offset in self.line_starts:
            if offset <= start:
                line_start = offset
            else:
                break
        line_end = len(self.full_text)
        for offset in self.line_starts:
            if offset > start:
                line_end = offset
                break
        return LineSpan(line_start, line_end, self.full_text[line_start:line_end])

    def adjacent_lines(self, start: int, end: int) -> str:
        current = self.line_window(start, end)
        prev_start = 0
        for offset in self.line_starts:
            if offset < current.start:
                prev_start = offset
            else:
                break
        next_end = len(self.full_text)
        seen_current = False
        for offset in self.line_starts:
            if offset == current.start:
                seen_current = True
                continue
            if seen_current:
                next_end = min(len(self.full_text), offset + 200)
                break
        return self.full_text[prev_start:next_end]

    def char_window(self, start: int, end: int, radius: int) -> str:
        left = max(0, start - radius)
        right = min(len(self.full_text), end + radius)
        return self.full_text[left:right]

    def left_window(self, start: int, radius: int) -> str:
        return self.full_text[max(0, start - radius) : start]

    def right_window(self, end: int, radius: int) -> str:
        return self.full_text[end : min(len(self.full_text), end + radius)]

    def contains_span(self, start: int, end: int, covers: list[tuple[int, int]]) -> bool:
        return any(inner_start <= start and end <= inner_end for inner_start, inner_end in covers)

    def overlaps_any(self, start: int, end: int, covers: list[tuple[int, int]]) -> bool:
        return any(start < other_end and end > other_start for other_start, other_end in covers)

    def inside_iban(self, start: int, end: int) -> bool:
        return self.contains_span(start, end, self.iban_spans)

    def inside_tckn(self, start: int, end: int) -> bool:
        return self.contains_span(start, end, self.tckn_spans)

    def inside_url(self, start: int, end: int) -> bool:
        return self.contains_span(start, end, self.url_spans)

    def isolated_from_digit_run(self, start: int, end: int) -> bool:
        text = self.full_text
        left = start - 1
        while left >= 0 and text[left] in _DIGIT_NEIGHBOR:
            left -= 1
        if left >= 0 and text[left].isdigit():
            return False
        right = end
        while right < len(text) and text[right] in _DIGIT_NEIGHBOR:
            right += 1
        if right < len(text) and text[right].isdigit():
            return False
        return True

    def register_person(self, start: int, end: int, text: str, detector: str) -> None:
        self.person_spans.append((start, end))
        if detector in HIGH_CONFIDENCE_DETECTORS and is_repeatable_person_name(text):
            key = person_surface_key(text)
            if len(key) >= 6:
                self.local_person_keys.setdefault(key, text)
