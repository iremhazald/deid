from __future__ import annotations

import re
import unicodedata

from app.detectors.label_packs import SemanticLabelGroup, label_lookup
from app.detectors.scoring.exclusions import (
    is_legal_heading_surface,
    is_legal_role_word,
    starts_with_paragraph_number,
)
from app.detectors.registry import (
    EMAIL,
    PageText,
    TR_LANDLINE,
    TR_PHONE,
    TR_PHONE_GROUPED,
    _is_tr_landline,
    _is_tr_mobile,
)
from app.detectors.scoring.derived import mark_outside_scoring
from app.domain.models import DetectionMethod, EntityCandidate, EntityType

# Generic structural patterns: LABEL : VALUE or LABEL on one line, VALUE on next.
_LABEL_VALUE = re.compile(
    r"(?P<label>[^\n:]{2,80})\s*:\s*(?P<value>[^\n]{1,500})",
    re.MULTILINE,
)
_LABEL_NEXT_LINE = re.compile(
    r"(?P<label>[^\n:]{2,80})\s*\n\s*(?P<value>[^\n:]{1,500})",
    re.MULTILINE,
)
# Contact form fields also use a dash separator. Not applied to PERSON.
_LABEL_DASH = re.compile(
    r"(?P<label>[^\n:]{2,40}?)\s+[-–]\s+(?P<value>[^\n]{1,200})",
    re.MULTILINE,
)
# Same value grammar as EN_PHONE_CONTEXT — do not invent a second phone validator.
_EN_PHONE_VALUE = re.compile(r"\+?\d[\d\s()./\-]{6,20}\d")

_MAX_VALUE_LEN = 500
_MIN_VALUE_LEN = 2
_PLACEHOLDER_VALUES = frozenset(
    {
        "-",
        "—",
        "n/a",
        "na",
        "none",
        "unknown",
        "yok",
        "belirtilmemiş",
        "belirtilmemis",
    }
)
_TRADE_AS_VALUE = re.compile(
    r"(?i)\b(?:t/a|t\.a\.|trading\s+as|doing\s+business\s+as|d/b/a|d\.b\.a\.|dba)\b"
)
_COMPANY_VALUE = re.compile(
    r"(?i)\b(?:limited|ltd\.?|llc|llp|inc(?:orporated)?|corp(?:oration)?|p\.?l\.?c\.?|plc)\b"
)
_BARE_ROLE_VALUE = frozenset(
    {
        "counsel",
        "solicitor",
        "barrister",
        "attorney",
        "lawyer",
        "advocate",
        "representative",
        "director",
        "employee",
        "manager",
    }
)
# Form labels only. A sentence that happens to end with "respondent" is not a label.
_PERSON_LABEL_MODIFIERS = frozenset(
    {
        "the",
        "a",
        "an",
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "1st",
        "2nd",
        "3rd",
        "4th",
        "5th",
    }
)

# Case facts, not personal data. Do not treat the label or its value as PII.
_SKIP_LABELS = frozenset(
    {
        "suç yeri",
        "suc yeri",
        "suç tarihi",
        "suc tarihi",
        "olay yeri",
        "olay tarihi",
        "suçun işlendiği yer",
        "sucun islendigi yer",
        "suçun tarihi",
        "sucun tarihi",
        "suç tarihi ve yeri",
        "suc tarihi ve yeri",
    }
)


_CONTACT_LABEL_MODIFIERS = frozenset(
    {
        "work",
        "home",
        "office",
        "business",
        "personal",
        "primary",
        "secondary",
        "daytime",
        "evening",
        "mobile",
        "cell",
        "direct",
        "main",
        "alt",
        "alternative",
        "no",
        "number",
        "address",
        "addr",
    }
)


def _contact_form_label(label_norm: str, alias: str) -> bool:
    """True when the label is a contact field, not prose that mentions email/website."""
    if label_norm == alias:
        return True
    if " " in alias:
        return False
    tokens = [token.strip("()[].,;#") for token in label_norm.split() if token.strip("()[].,;#")]
    if alias not in tokens or len(tokens) > 4:
        return False
    if tokens[-1] != alias and tokens[0] != alias:
        return False
    extras = [token for token in tokens if token != alias]
    return bool(extras) and all(token in _CONTACT_LABEL_MODIFIERS for token in extras)


def _fit_contact_value(value: str) -> tuple[EntityType, str, int, int] | None:
    """Locate a real email or phone inside a structural value. Label is not enough."""
    email = EMAIL.search(value)
    if email:
        return EntityType.EMAIL, email.group(0), email.start(), email.end()
    for pattern in (TR_PHONE, TR_PHONE_GROUPED, TR_LANDLINE):
        match = pattern.search(value)
        if not match:
            continue
        surface = match.group(0)
        if _is_tr_mobile(surface) or _is_tr_landline(surface):
            return EntityType.PHONE_NUMBER, surface, match.start(), match.end()
    phone = _EN_PHONE_VALUE.search(value)
    if phone:
        return EntityType.PHONE_NUMBER, phone.group(0), phone.start(), phone.end()
    return None


def _person_form_label(label_norm: str, alias: str) -> bool:
    """True when the label is a form field, not narrative that mentions a party word."""
    if label_norm == alias:
        return True
    if " " in alias:
        return False
    tokens = label_norm.split()
    if alias not in tokens or len(tokens) > 4:
        return False
    if tokens[-1] != alias and tokens[0] != alias:
        return False
    extras = [token for token in tokens if token != alias]
    return bool(extras) and all(token in _PERSON_LABEL_MODIFIERS for token in extras)


def _structural_person_value_ok(value: str) -> bool:
    """STRUCTURAL PERSON values must look like a name. They skip evidence scoring."""
    from app.detectors.en.common import (
        fold_en,
        looks_like_person_name,
        looks_like_titled_name_body,
        titled_name_has_initials,
    )
    from app.detectors.en.vocab import PERSON_TITLES

    text = value.strip().strip('"')
    if "," in text:
        head, tail = text.split(",", 1)
        if _normalize_label(tail) in _BARE_ROLE_VALUE:
            text = head.strip()
    tokens = text.split()
    if tokens and fold_en(tokens[0].rstrip(".")) in PERSON_TITLES:
        text = " ".join(tokens[1:]).strip()
        tokens = text.split()
    if not text:
        return False
    if re.search(r"[^\x00-\x7F]", text):
        return True
    if not (looks_like_person_name(text) or looks_like_titled_name_body(text)):
        return False
    if len(tokens) >= 3 and not titled_name_has_initials(text):
        return False
    return True


def _normalize_label(value: str) -> str:
    folded = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", folded)


def _is_placeholder(value: str) -> bool:
    return _normalize_label(value) in _PLACEHOLDER_VALUES


def _pick_entity_type(
    group_types: tuple[EntityType, ...],
    value: str,
    label_norm: str = "",
) -> EntityType:
    """Choose the most specific entity type for a structural value."""
    if EntityType.DATE_OF_BIRTH in group_types:
        if any(token in label_norm for token in ("doğum", "dogum", "birth", "geburt")):
            return EntityType.DATE_OF_BIRTH
    if EntityType.CASE_NUMBER in group_types or EntityType.FILE_NUMBER in group_types:
        if any(token in label_norm for token in ("karar no", "karar numarası", "decision number")):
            return EntityType.DECISION_NUMBER
        if any(token in label_norm for token in ("dosya no", "dosya numarası", "dava no", "file number")):
            return EntityType.FILE_NUMBER
        if any(token in label_norm for token in ("esas", "case number", "docket")):
            return EntityType.CASE_NUMBER
    if len(group_types) == 1:
        return group_types[0]
    if "@" in value and EntityType.EMAIL in group_types:
        return EntityType.EMAIL
    phone_like = re.search(r"\+\d|\(\d|\d{3}[\s.-]\d", value)
    if phone_like and EntityType.PHONE_NUMBER in group_types:
        return EntityType.PHONE_NUMBER
    digits = re.sub(r"\D", "", value)
    if EntityType.TAX_IDENTIFIER in group_types and EntityType.NATIONAL_ID in group_types:
        if any(token in label_norm for token in ("vergi", "vkn", "tax")) and len(digits) == 10:
            return EntityType.TAX_IDENTIFIER
        if len(digits) == 11 and EntityType.NATIONAL_ID in group_types:
            return EntityType.NATIONAL_ID
    compact = value.replace(" ", "")
    iban_like = re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", compact)
    if iban_like and EntityType.IBAN in group_types:
        return EntityType.IBAN
    return group_types[0]


def _extract_candidates(
    text: str,
    *,
    page: PageText,
    lookup: dict[str, SemanticLabelGroup],
) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen: set[tuple[int, int]] = set()

    for pattern in (_LABEL_VALUE, _LABEL_NEXT_LINE, _LABEL_DASH):
        for match in pattern.finditer(text):
            label_raw = match.group("label").strip()
            value_group = match.group("value")
            value_raw = value_group.strip()
            if len(value_raw) < _MIN_VALUE_LEN or len(value_raw) > _MAX_VALUE_LEN:
                continue
            if _is_placeholder(value_raw):
                continue

            label_norm = _normalize_label(label_raw)
            if label_norm in _SKIP_LABELS or any(
                label_norm.endswith(f" {skip}") or label_norm.startswith(f"{skip} ")
                for skip in _SKIP_LABELS
            ):
                continue
            group = lookup.get(label_norm)
            if group is None:
                # Partial match: label ends with known alias
                for alias, candidate_group in lookup.items():
                    prefix_match = label_norm.startswith(f"{alias} ")
                    suffix_match = label_norm.endswith(f" {alias}")
                    # "Mr J Allsop, Counsel" is a name + role, not a person label.
                    if suffix_match and alias in _BARE_ROLE_VALUE and "," in label_raw:
                        continue
                    person_group = EntityType.PERSON_NAME in candidate_group.entity_types
                    if person_group:
                        if not _person_form_label(label_norm, alias):
                            continue
                        group = candidate_group
                        break
                    if candidate_group.concept == "contact":
                        if not _contact_form_label(label_norm, alias):
                            continue
                        group = candidate_group
                        break
                    if label_norm == alias or prefix_match or suffix_match:
                        group = candidate_group
                        break
            if group is None:
                continue
            if pattern is _LABEL_DASH and group.concept != "contact":
                continue

            lead = len(value_group) - len(value_group.lstrip())
            local_start = match.start("value") + lead
            local_end = local_start + len(value_raw)
            entity_type = _pick_entity_type(group.entity_types, value_raw, label_norm)
            if group.concept == "contact":
                fitted = _fit_contact_value(value_raw)
                if fitted is None:
                    continue
                entity_type, fitted_text, rel_start, rel_end = fitted
                value_raw = fitted_text
                local_start = match.start("value") + lead + rel_start
                local_end = match.start("value") + lead + rel_end
            if (local_start, local_end) in seen:
                continue
            seen.add((local_start, local_end))

            global_start = page.document_offset + local_start
            global_end = page.document_offset + local_end
            if entity_type == EntityType.PERSON_NAME and (
                _TRADE_AS_VALUE.search(value_raw)
                or _COMPANY_VALUE.search(value_raw)
                or _normalize_label(value_raw) in _BARE_ROLE_VALUE
                or is_legal_heading_surface(value_raw)
                or is_legal_role_word(value_raw)
                or not _structural_person_value_ok(value_raw)
            ):
                continue
            # Next-line 67.8. / 83.4. is paragraph structure. Live ET text
            # also does this after a sentence that merely starts with a
            # party alias ("claimant had placed her…\n67.8."), which the
            # generic PERSON_NAME label pack would otherwise accept.
            # STRUCTURAL_* is outside evidence scoring, so the paragraph
            # hard-reject in evaluate.py never sees these hits.
            if starts_with_paragraph_number(value_raw) and (
                pattern is _LABEL_NEXT_LINE or entity_type == EntityType.PERSON_NAME
            ):
                continue
            found.append(
                mark_outside_scoring(
                    EntityCandidate(
                        text=value_raw,
                        type=entity_type,
                        start=global_start,
                        end=global_end,
                        page=page.page,
                        method=DetectionMethod.STRUCTURAL,
                        detector=f"STRUCTURAL_{group.concept.upper()}",
                        validated=True,
                    )
                )
            )
    return found


def run_structural_detectors(pages: list[PageText]) -> list[EntityCandidate]:
    """Detect label-associated values using generic structural patterns."""
    lookup = label_lookup()
    candidates: list[EntityCandidate] = []
    for page in pages:
        candidates.extend(_extract_candidates(page.text, page=page, lookup=lookup))
    return candidates
