"""Bounded English NER-only PERSON contradiction cues.

These are contextual, not a surface blacklist. They apply only to LOCAL_NER_EN
PERSON candidates that do not already overlap a deterministic person rule.
Turkish NER and deterministic detectors are unchanged.
"""

from __future__ import annotations

import re

from app.detectors.scoring.english_page import ordinary_english_page_noun_at
from app.detectors.scoring.context import DocumentIndex

_WS = re.compile(r"[\s\u00a0\u00ad\u2000-\u200d\u202f]+")

_OCCUPATION_AS = re.compile(
    r"(?:employed|worked|working|engaged|appointed|hired|recruited|retained)"
    r"\s+as(?:\s+an?)?$",
    re.IGNORECASE,
)
_ROLE_AS = re.compile(
    r"(?:role|job|position|occupation|duties|post)\s+as(?:\s+an?)?$",
    re.IGNORECASE,
)
_ONLY_SOLE = re.compile(r"(?:the\s+)?(?:only|sole)\s*$", re.IGNORECASE)
_EMPLOYED_RIGHT = re.compile(r"^(?:as\s+)?employed(?:\s+by|\s+as)?\b", re.IGNORECASE)
_FREELANCE_AS = re.compile(r"freelance(?:\s+\w+){0,4}\s+as$", re.IGNORECASE)
_TRADING_AS = re.compile(r"(?:trading\s+as|t/a|styled\s+as)$", re.IGNORECASE)

_CLAIM_FOR = re.compile(
    r"(?:claim|complaint|allegation|finding|cause\s+of\s+action)"
    r"\s+(?:for|of)(?:\s+an?)?\s*$",
    re.IGNORECASE,
)
_DISMISSED_FOR = re.compile(r"dismissed\s+for(?:\s+an?)?\s*$", re.IGNORECASE)
_CLAIM_RIGHT = re.compile(r"^claim\b", re.IGNORECASE)
_ISSUE_QUESTION = re.compile(
    r"\s+\d{1,3}\.\s+(?:What|Whether|Was|Is|Did|Has|Have|If)\b",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip()


def occupation_role_context(left: str, right: str) -> bool:
    """True when the span is used as a job, role, or trading style."""
    left_n = _norm(left)
    right_n = _norm(right)
    if _OCCUPATION_AS.search(left_n) or _ROLE_AS.search(left_n):
        return True
    if _FREELANCE_AS.search(left_n) or _TRADING_AS.search(left_n):
        return True
    if _EMPLOYED_RIGHT.search(right_n) and (
        _ONLY_SOLE.search(left_n) or re.search(r"(?:the|a|an|as)\s*$", left_n, re.IGNORECASE)
    ):
        return True
    return False


def legal_concept_context(left: str, right: str) -> bool:
    """True when the span is a claim, complaint, or cause of action."""
    left_n = _norm(left)
    right_n = _norm(right)
    if _CLAIM_FOR.search(left_n) or _DISMISSED_FOR.search(left_n):
        return True
    if _CLAIM_RIGHT.search(right_n):
        return True
    return False


def issue_heading_context(index: DocumentIndex, start: int, end: int) -> bool:
    """Standalone issue heading followed by a numbered tribunal question."""
    surface = index.full_text[start:end].strip()
    if not surface:
        return False
    line = index.line_window(start, end)
    if line.text.strip() != surface:
        return False
    return _ISSUE_QUESTION.match(index.right_window(end, 80)) is not None


def english_ner_person_contradiction(
    index: DocumentIndex, start: int, end: int
) -> list[str]:
    """Return category-specific negative codes for one English NER PERSON span."""
    left = index.left_window(start, 80)
    right = index.right_window(end, 80)
    codes: list[str] = []
    if occupation_role_context(left, right):
        codes.append("occupation_context")
    if legal_concept_context(left, right) or issue_heading_context(index, start, end):
        codes.append("legal_concept_context")
    if ordinary_english_page_noun_at(index, start, end):
        codes.append("english_lexical_page_noun")
    return codes
