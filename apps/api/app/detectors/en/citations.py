"""Cited-authority context spans for English-General legal documents.

This is not a second identity system and does not emit a user-facing category.
Detectors may still produce PERSON / COMPANY / ORGANISATION candidates inside a
citation. The policy layer then KEEP those nested spans locally.

Strong evidence is required. Bare ``Name v Name`` is not enough: a private
pleading can name the current parties that way.
"""

from __future__ import annotations

import re

from app.domain.models import EntityCandidate, EntityType

# Closed report / neutral tokens used as citation evidence, not as identifiers.
# UK-specific locators (UKEAT, EWHC, UKSC, …) stay here as structure evidence
# only. Full en-GB identifier work is deferred.
_PARTY_GLUE = r"(?:the|of|for|and|upon|in|de|van|von|da|di|&|UK)"
_PARTY_WORD = rf"(?:[A-Z][A-Za-z0-9'’&.-]*|{_PARTY_GLUE})"
_PARTY = rf"{_PARTY_WORD}(?:[ \t]+{_PARTY_WORD}){{0,11}}"
_VS = r"(?:v\.?|vs\.?)"
_YEAR = r"\[\s*[12]\d{3}\s*\]"
# Volume + report/neutral token + pinpoint. Do not consume following prose.
_CITE_TAIL = (
    r"(?:[ \t]+\d+)?"
    r"(?:[ \t]+[A-Z][A-Za-z.]{1,10})?"
    r"(?:[ \t]*\d+[A-Za-z()]*)?"
    r"(?:[ \t]*\([A-Za-z]+\))?"
)
# Native PDF text sometimes drops the closing paren ("(UKEAT/0329/15/DA.").
_PAREN_LOCATOR = r"\([A-Z]{2,10}/\d{1,4}/\d{1,4}(?:/[A-Za-z0-9]{1,6})?\)?"

_BRACKETED = re.compile(
    rf"(?<![A-Za-z])(?P<span>(?P<left>{_PARTY})[ \t]+{_VS}[ \t]+(?P<right>{_PARTY})"
    rf"[ \t]+{_YEAR}{_CITE_TAIL})"
)
_PARENTHETICAL = re.compile(
    rf"(?<![A-Za-z])(?P<span>(?P<left>{_PARTY})[ \t]+{_VS}[ \t]+(?P<right>{_PARTY})"
    rf"[ \t\n\r]*{_PAREN_LOCATOR})"
)

_CONTEXT_TYPES = frozenset(
    {
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
        EntityType.COMPANY_NAME,
        EntityType.ORGANISATION,
        EntityType.COURT_NAME,
        EntityType.CASE_NUMBER,
        EntityType.FILE_NUMBER,
        EntityType.DECISION_NUMBER,
    }
)


def iter_cited_authority_spans(text: str) -> list[tuple[int, int]]:
    """Return inclusive document-local spans for strongly structured citations."""
    found: list[tuple[int, int]] = []
    for pattern in (_BRACKETED, _PARENTHETICAL):
        for match in pattern.finditer(text):
            found.append((match.start("span"), match.end("span")))
    if not found:
        return []
    found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    merged: list[tuple[int, int]] = []
    for start, end in found:
        if merged and start <= merged[-1][1] and end <= merged[-1][1]:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            continue
        merged.append((start, end))
    return merged


def annotate_cited_authority_context(
    pages: list,
    candidates: list[EntityCandidate],
) -> list[EntityCandidate]:
    """Mark nested party/org spans that sit inside a citation. Span-local only."""
    if not pages or not candidates:
        return candidates
    spans: list[tuple[int, int, int]] = []
    for page in pages:
        offset = getattr(page, "document_offset", 0)
        page_no = getattr(page, "page", 0)
        text = getattr(page, "text", "") or ""
        for start, end in iter_cited_authority_spans(text):
            spans.append((page_no, offset + start, offset + end))
    if not spans:
        return candidates
    marked: list[EntityCandidate] = []
    for item in candidates:
        if item.type not in _CONTEXT_TYPES:
            marked.append(item)
            continue
        covering = next(
            (
                (page_no, start, end)
                for page_no, start, end in spans
                if page_no == item.page and item.start >= start and item.end <= end
            ),
            None,
        )
        if covering is None:
            marked.append(item)
            continue
        attrs = dict(item.attributes or {})
        if attrs.get("cited_authority_context"):
            marked.append(item)
            continue
        evidence = list(attrs.get("evidence") or [])
        if not any(
            isinstance(entry, dict) and entry.get("code") == "en_cited_authority_context"
            for entry in evidence
        ):
            evidence.append(
                {"code": "en_cited_authority_context", "weight": 0, "source": "context"}
            )
        attrs["cited_authority_context"] = True
        attrs["identity_resolved"] = False
        attrs["evidence"] = evidence
        marked.append(item.model_copy(update={"attributes": attrs}))
    return marked
