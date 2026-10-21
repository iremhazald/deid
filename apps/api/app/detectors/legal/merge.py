"""Overlap priority and UYAP reclassification for rule-based candidates."""

from __future__ import annotations

import re

from app.detectors.legal.names import (
    clip_trailing_uets_span,
    first_person_span,
    is_legal_role_label,
    is_non_person_surface,
    is_uets_label_surface,
    take_person_name,
    trailing_case_cut,
    uets_number_span,
)
from app.detectors.textutil import fold_tr_identity
from app.domain.models import EntityCandidate, EntityType

_DETECTOR_RANK: dict[str, int] = {
    "TR_UYAP_FOOTER": 100,
    "TR_JUDICIAL_ROSTER": 92,
    "TR_LEGAL_PARTY": 90,
    "TR_COUNSEL_BLOCK": 88,
    "TR_PARENTAGE": 84,
    "TR_BIRTH_INFO": 84,
    "TR_STATEMENT": 80,
    "TR_OWNERSHIP": 78,
    "TR_BANK_TX": 76,
    "TR_ROLE_PERSON": 72,
    "TR_NAME_PAIR": 71,
    "TR_MENTIONED_PERSON": 70,
    "TR_NARRATIVE_PERSON": 62,
    "TR_NAME_REPEAT": 69,
    "TR_ADDRESS_TOKENS": 68,
    "TR_PHONE_CONTEXT": 66,
    "TR_MOBILE_PHONE": 65,
    "TR_LANDLINE_PHONE": 64,
    "TR_IP_PORT": 66,
    "TR_PORT_REPEAT": 65,
    "TR_PHONE_REPEAT": 64,
    "TR_IBAN": 64,
    "TR_IBAN_REPEAT": 63,
    "TR_TCKN": 64,
    "TR_UETS": 64,
    "TR_VEHICLE_PLATE": 60,
    "TR_ORG_AUTHORITY": 56,
    "TR_LEGAL_ROLE_NAME": 73,
    "TR_COURT_LETTERHEAD": 71,
    "TR_COURT_GRAMMAR": 70,
    "TR_CASE_NUMBER": 50,
    "TR_DECISION_NUMBER": 50,
    "TR_FILE_NUMBER": 50,
    "TR_ADDRESS_GRAMMAR": 48,
    "TR_EVIDENCE_ADDRESS": 47,
    "TR_DATE_FORMAT": 46,
    "TR_POSTAL_CODE": 44,
    "STRUCTURAL": 40,
    "STRUCTURAL_CONTACT": 18,
    "GLOBAL_IBAN": 22,
    "GLOBAL_URL": 20,
    "GLOBAL_IPV4": 20,
    "GLOBAL_EMAIL": 20,
    "GLOBAL_LUHN_CARD": 20,
    "LOCAL_NER_TR": 54,
    "LOCAL_NER_EN": 53,
    "EN_LEGAL_PARTY": 90,
    "EN_ROLE_PERSON": 74,
    "EN_TITLED_PERSON": 73,
    "EN_SIGNATURE_PERSON": 72,
    "EN_NARRATIVE_PERSON": 62,
    "EN_COURT": 70,
    "EN_COMPANY_SUFFIX": 68,
    "EN_ORGANISATION": 66,
    "EN_ADDRESS": 67,
    "EN_CASE_NUMBER": 50,
    "EN_FILE_NUMBER": 50,
    "EN_BIRTH": 84,
    "EN_PASSPORT": 60,
    "EN_NATIONAL_ID": 48,
    "EN_PHONE_CONTEXT": 55,
    "EN_ACCOUNT": 46,
    "EN_POSTAL_CODE": 44,
}

_PREFIX_RANK: tuple[tuple[str, int], ...] = (
    ("TR_UYAP", 100),
    ("TR_LEGAL_PARTY", 90),
    ("EN_", 70),
    ("STRUCTURAL_", 40),
    ("GLOBAL_", 20),
    ("LOCAL_NER", 54),
)

_TYPE_RANK = {
    EntityType.UYAP_ACCESS: 10,
    EntityType.DATE_OF_BIRTH: 8,
    EntityType.BIRTH_PLACE: 8,
    EntityType.COURT_NAME: 7,
    EntityType.SYSTEM_URL: 6,
    EntityType.PROFESSIONAL_ID: 6,
    EntityType.LAWYER_NAME: 5,
    EntityType.JUDGE_NAME: 5,
    EntityType.DEFENDANT_NAME: 5,
    EntityType.CLAIMANT_NAME: 5,
    EntityType.WITNESS_NAME: 5,
}

_PERSON = {
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

_GROUPS: dict[str, frozenset[EntityType]] = {
    "PERSON": frozenset(_PERSON),
    "ADDRESS": frozenset({EntityType.ADDRESS, EntityType.POSTAL_CODE}),
    "PLACE": frozenset({EntityType.LOCATION, EntityType.BIRTH_PLACE}),
    "DATE": frozenset({EntityType.DATE, EntityType.DATE_OF_BIRTH}),
    "IBAN": frozenset(
        {
            EntityType.IBAN,
            EntityType.BANK_ACCOUNT,
            EntityType.CREDIT_CARD,
            EntityType.FINANCIAL_IDENTIFIER,
        }
    ),
    "PHONE": frozenset({EntityType.PHONE_NUMBER}),
    "URL": frozenset({EntityType.URL, EntityType.SYSTEM_URL, EntityType.UYAP_ACCESS}),
    "IP": frozenset({EntityType.IP_ADDRESS}),
    "ORG": frozenset({EntityType.ORGANISATION, EntityType.COMPANY_NAME, EntityType.COURT_NAME}),
    "ID": frozenset({EntityType.PROFESSIONAL_ID, EntityType.OTHER_IDENTIFIER, EntityType.EMPLOYEE_ID}),
}

_UYAP_HOST = "vatandas.uyap.gov.tr"

_BOILERPLATE_EXACT = {
    fold_tr_identity(item)
    for item in (
        "suç yeri",
        "suc yeri",
        "suç tarihi",
        "suc tarihi",
        "olay yeri",
        "olay tarihi",
        "kredi kurumlarının araç",
        "kredi kurumlarinin arac",
        "suretiyle dolandırıcılık",
        "suretiyle dolandiricilik",
        "uets",
    )
}
_PROSE_CUES = tuple(
    fold_tr_identity(item)
    for item in (
        "bilindiği üzere",
        "bilindigi uzere",
        "bilinen bir gerçek",
        "bilinen bir gercek",
        "kendi adına tahsisli",
        "kendi adina tahsisli",
        "adına tahsisli hat",
        "adina tahsisli hat",
        "göz yumulan",
        "goz yumulan",
        "suçlarında hizmet",
        "suclarinda hizmet",
        "dolandırıcılık suçlarında",
        "dolandiricilik suclarinda",
        "ıp numaraları",
        "ip numaralari",
        "kimlik bilgilerini",
        "gsm hatlarının",
        "gsm hatlarinin",
        "kredi kurumlarının araç",
        "suretiyle dolandırıcılık",
        "bilişim sistemleri banka",
        "bilisim sistemleri banka",
    )
)
_WRAPPER_CUES = tuple(
    fold_tr_identity(item)
    for item in (
        "nezdinde",
        "adına kayıtlı",
        "adina kayitli",
        "anlaştıkları",
        "anlastiklari",
        "ibana",
    )
)
_CONNECTOR_EXACT = frozenset(
    fold_tr_identity(item)
    for item in (
        "nezdinde",
        "ibana",
        "iban",
        "anlaştıkları",
        "anlastiklari",
        "adına kayıtlı",
        "adina kayitli",
        "adına",
        "adina",
        "kayıtlı",
        "kayitli",
        "gibi",
        "gönderdiğini",
        "gonderdigini",
    )
)
_AMOUNT_VALUE = re.compile(
    r"\b\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?\s*(?:TL|TRY|Türk\s+Lirası|Turk\s+Lirasi)\b",
    re.IGNORECASE,
)
_INNER_VALUE_TYPES = frozenset(
    {
        EntityType.IBAN,
        EntityType.BANK_ACCOUNT,
        EntityType.CREDIT_CARD,
        EntityType.NATIONAL_ID,
        EntityType.PHONE_NUMBER,
        EntityType.PERSON_NAME,
        EntityType.FIRST_NAME,
        EntityType.LAST_NAME,
        EntityType.MONEY_AMOUNT,
        EntityType.IP_ADDRESS,
        EntityType.PORT_NUMBER,
        EntityType.EMAIL,
        EntityType.PROFESSIONAL_ID,
        EntityType.UETS,
    }
)
_KEEP_WRAPPER_TYPES = frozenset(
    {
        EntityType.UYAP_ACCESS,
        EntityType.COURT_NAME,
        EntityType.ADDRESS,
        EntityType.IBAN,
        EntityType.BANK_ACCOUNT,
        EntityType.CREDIT_CARD,
        EntityType.NATIONAL_ID,
    }
)
_INSIDE_IBAN = frozenset(
    {
        EntityType.PHONE_NUMBER,
        EntityType.CREDIT_CARD,
        EntityType.OTHER_IDENTIFIER,
    }
)


_KEEP_FROM_BOILERPLATE = frozenset(
    {
        EntityType.IBAN,
        EntityType.BANK_ACCOUNT,
        EntityType.CREDIT_CARD,
        EntityType.NATIONAL_ID,
        EntityType.ADDRESS,
        EntityType.UETS,
    }
)


def _folded_span(text: str) -> str:
    return re.sub(r"\s+", " ", fold_tr_identity(text)).strip(" \t,.;:\"'")


def is_connector_only(text: str) -> bool:
    folded = _folded_span(text)
    if not folded or folded in _CONNECTOR_EXACT or folded in _BOILERPLATE_EXACT:
        return True
    words = folded.split()
    return bool(words) and all(word in _CONNECTOR_EXACT for word in words)


def _is_connector_only(text: str) -> bool:
    return is_connector_only(text)


def _looks_like_legal_boilerplate(text: str) -> bool:
    folded = _folded_span(text)
    if not folded:
        return False
    if folded in _BOILERPLATE_EXACT or _is_connector_only(text):
        return True
    if is_legal_role_label(text) or is_non_person_surface(text):
        return True
    words = folded.split()
    if any(cue in folded for cue in _WRAPPER_CUES) and len(words) >= 2:
        return True
    if len(words) >= 8 and any(cue in folded for cue in _PROSE_CUES):
        return True
    if 2 <= len(words) <= 6 and any(cue in folded for cue in _PROSE_CUES):
        return True
    return False


def detector_rank(detector: str) -> int:
    if detector in _DETECTOR_RANK:
        return _DETECTOR_RANK[detector]
    for prefix, rank in _PREFIX_RANK:
        if detector.startswith(prefix):
            return rank
    return 30


def _group_of(entity_type: EntityType) -> str | None:
    for name, types in _GROUPS.items():
        if entity_type in types:
            return name
    return None


def _evidence_score(item: EntityCandidate) -> int:
    raw = (item.attributes or {}).get("evidence_score")
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _hard_valid(item: EntityCandidate) -> bool:
    return (item.attributes or {}).get("hard_validation") == "VALID"


def _score(item: EntityCandidate) -> tuple[int, int, int, int, int, int]:
    """Overlap winner among the same semantic group.

    Order is not highest-score-wins:
    1. hard VALID
    2. trusted detector rank
    3. entity-type specificity
    4. evidence score
    5. span length
    6. earlier start
    """
    return (
        1 if _hard_valid(item) else 0,
        detector_rank(item.detector),
        _TYPE_RANK.get(item.type, 0),
        _evidence_score(item),
        item.end - item.start,
        -item.start,
    )


_LEADING_DETERMINERS = frozenset({"the", "a", "an", "this", "that"})


def _has_professional_title(text: str) -> bool:
    return bool(
        re.match(
            r"(?i)^(?:prof(?:essor)?|dr|avukat|av|h[âa]k[iı]m|yarg[ıi][çc])\.?",
            text.strip(),
        )
    )


def _overlaps(left: EntityCandidate, right: EntityCandidate) -> bool:
    return left.page == right.page and left.start < right.end and right.start < left.end


def _folded_tokens(text: str) -> list[str]:
    return [token for token in re.sub(r"\s+", " ", text).casefold().split() if token]


def _person_is_institutional_partial(institution: EntityCandidate, person: EntityCandidate) -> bool:
    """True when a person span is only a determiner + court-head inside a court name.

    Proven on 'the Employment' overlapping 'Employment Tribunals'. Containment
    alone misses this because the determiner sits just outside the court span.
    """
    if not _overlaps(institution, person):
        return False
    if _contains(institution, person):
        return True
    inst = _folded_tokens(institution.text)
    person_tokens = [token for token in _folded_tokens(person.text) if token not in _LEADING_DETERMINERS]
    return bool(inst) and bool(person_tokens) and all(token in inst for token in person_tokens)


def _contains(outer: EntityCandidate, inner: EntityCandidate) -> bool:
    return (
        outer.page == inner.page
        and inner.start >= outer.start
        and inner.end <= outer.end
    )


def _reclassify_uyap_urls(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    updated: list[EntityCandidate] = []
    for item in candidates:
        if item.type == EntityType.URL and _UYAP_HOST in item.text.lower():
            updated.append(
                item.model_copy(
                    update={
                        "type": EntityType.SYSTEM_URL,
                        "reason": "UYAP system URL; not a general web address.",
                        "attributes": {**item.attributes, "kind": "UYAP_SYSTEM_URL"},
                    }
                )
            )
        else:
            updated.append(item)
    return updated


def _drop_contained_in_uyap(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    covers = [item for item in candidates if item.type == EntityType.UYAP_ACCESS]
    if not covers:
        return candidates
    swallow = {EntityType.URL, EntityType.SYSTEM_URL}
    kept: list[EntityCandidate] = []
    for item in candidates:
        if item.type == EntityType.UYAP_ACCESS:
            kept.append(item)
            continue
        if item.type in swallow and any(_contains(cover, item) for cover in covers):
            continue
        if any(_contains(cover, item) and item.type != EntityType.UYAP_ACCESS for cover in covers):
            # Keep identifiers that are not the generic URL itself? User asked
            # not to double-count the footer URL. Other contained types stay
            # dropped so the footer remains one redaction unit.
            if item.type in swallow:
                continue
        kept.append(item)
    return kept


def _drop_contained_in_court_header(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    covers = [
        item
        for item in candidates
        if item.type == EntityType.COURT_NAME
        and item.attributes.get("mask_scope") == "header_line"
    ]
    if not covers:
        return candidates
    swallow = {
        EntityType.CASE_NUMBER,
        EntityType.FILE_NUMBER,
        EntityType.DECISION_NUMBER,
    }
    kept: list[EntityCandidate] = []
    for item in candidates:
        if item.type == EntityType.COURT_NAME and item.attributes.get("mask_scope") == "header_line":
            kept.append(item)
            continue
        if item.type in swallow and any(
            cover.page == item.page
            and (
                _contains(cover, item)
                or _overlaps(cover, item)
                or bool(item.text.strip() and item.text.strip() in cover.text)
            )
            for cover in covers
        ):
            continue
        if (
            item.type == EntityType.COURT_NAME
            and item.attributes.get("mask_scope") != "header_line"
            and any(
                _contains(cover, item)
                or (item.text.strip() and item.text.strip() in cover.text)
                for cover in covers
            )
        ):
            continue
        if item.type in {EntityType.LOCATION, EntityType.BIRTH_PLACE} and any(
            cover.page == item.page
            and item.text.strip()
            and (
                _contains(cover, item)
                or _overlaps(cover, item)
                or item.text.strip() in cover.text
            )
            for cover in covers
        ):
            continue
        kept.append(item)
    return kept


def _drop_places_inside_courts(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    courts = [item for item in candidates if item.type == EntityType.COURT_NAME]
    if not courts:
        return candidates
    kept: list[EntityCandidate] = []
    for item in candidates:
        if (
            item.type in {EntityType.LOCATION, EntityType.BIRTH_PLACE}
            and item.attributes.get("org_kind") != "PROSECUTOR_CITY"
            and any(
                court.page == item.page
                and item.text.strip()
                and (
                    _contains(court, item)
                    or _overlaps(court, item)
                    or item.text.strip() in court.text
                )
                for court in courts
            )
        ):
            continue
        kept.append(item)
    return kept


def _clip_person_candidates(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    """Keep only the given-name / surname; drop legal labels and prose."""
    kept: list[EntityCandidate] = []
    for item in candidates:
        if item.type not in _PERSON:
            kept.append(item)
            continue
        item = _expose_case_suffix(item)
        if item.detector in {
            "TR_NAME_REPEAT",
            "TR_NAME_PAIR",
            "LOCAL_NER_TR",
            "LOCAL_NER_EN",
            "EN_TITLED_PERSON",
            "EN_ROLE_PERSON",
            "EN_LEGAL_PARTY",
            "EN_SIGNATURE_PERSON",
            "EN_NARRATIVE_PERSON",
        } or item.attributes.get("parent_role"):
            kept.append(item)
            continue
        if re.match(
            r"(?i)^(?:prof(?:essor)?|dr|avukat|av|h[âa]k[iı]m|yarg[ıi][çc])\.?",
            item.text.strip(),
        ):
            kept.append(item)
            continue
        clipped = _person_value_span(item.text)
        if clipped is None:
            if len(item.text.split()) <= 1:
                if is_legal_role_label(item.text) or is_non_person_surface(item.text):
                    continue
                kept.append(item)
            continue
        name, rel_start, rel_end = clipped
        if re.search(
            r"(?i)\b(?:t/a|t\.a\.|trading\s+as|doing\s+business\s+as|d/b/a|dba)\b",
            item.text,
        ):
            continue
        if rel_start == 0 and rel_end == len(item.text) and name == item.text.strip():
            kept.append(item)
            continue
        kept.append(_resized(item, name, rel_start, rel_end))
    return kept


def _expose_case_suffix(item: EntityCandidate) -> EntityCandidate:
    """Leave ``'ın`` and other case endings outside the labeled span.

    ``Av. Mehmet Yılmaz'ın`` labels ``Av. Mehmet Yılmaz``. The apostrophe and
    the ending stay in the document. A capitalized piece such as ``O'Brien``
    is not an ending and is left intact. Professional titles stay inside.
    """
    cut = trailing_case_cut(item.text)
    if cut is None or cut <= 0:
        return item
    return _resized(item, item.text[:cut], 0, cut)


def _resized(item: EntityCandidate, value: str, rel_start: int, rel_end: int) -> EntityCandidate:
    return item.model_copy(
        update={
            "text": value,
            "start": item.start + rel_start,
            "end": item.start + rel_end,
        }
    )


def _person_value_span(text: str) -> tuple[str, int, int] | None:
    taken = take_person_name(text)
    if taken:
        name, lead, trail = taken
        return name, lead, len(text) - trail
    match = first_person_span(text)
    if match is None:
        return None
    inner = take_person_name(match.group(1))
    if inner is None:
        return None
    name, lead, trail = inner
    rel_start = match.start(1) + lead
    rel_end = match.end(1) - trail
    return name, rel_start, rel_end


def _iban_value_span(text: str) -> tuple[str, int, int] | None:
    from app.detectors.registry import IBAN, _fit_iban, iter_tr_iban_spans

    match = IBAN.search(text)
    if match is not None:
        fitted = _fit_iban(match)
        if fitted:
            return fitted
    spans = iter_tr_iban_spans(text)
    if spans:
        return max(spans, key=lambda item: item[2] - item[1])
    if match is not None:
        return match.group(0), match.start(), match.end()
    return None


def _phone_value_span(text: str) -> tuple[str, int, int] | None:
    from app.detectors.registry import TR_PHONE, TR_PHONE_GROUPED

    match = TR_PHONE.search(text) or TR_PHONE_GROUPED.search(text)
    if match is None:
        return None
    return match.group(0), match.start(), match.end()


def _ip_value_span(text: str) -> tuple[str, int, int] | None:
    from app.detectors.registry import IPV4, _valid_ipv4

    match = IPV4.search(text)
    if match is None or not _valid_ipv4(match.group(0)):
        return None
    return match.group(0), match.start(), match.end()


def _clip_value_spans(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    """Shrink identifier / amount hits that swallowed surrounding legal prose."""
    kept: list[EntityCandidate] = []
    for item in candidates:
        if item.detector == "USER_DEFINED_TERM":
            kept.append(item)
            continue
        if item.type == EntityType.UETS:
            clipped = uets_number_span(item.text)
            if clipped:
                kept.append(_resized(item, *clipped))
            continue
        if is_uets_label_surface(item.text):
            continue
        uets_clip = clip_trailing_uets_span(item.text)
        if uets_clip is None:
            continue
        if uets_clip != (0, len(item.text)):
            prefix = item.text[uets_clip[0] : uets_clip[1]]
            item = _resized(item, prefix, uets_clip[0], uets_clip[1])
        if item.type in {
            EntityType.IBAN,
            EntityType.BANK_ACCOUNT,
            EntityType.FINANCIAL_IDENTIFIER,
        }:
            clipped = _iban_value_span(item.text)
            if clipped:
                kept.append(_resized(item, *clipped))
                continue
            amount = _AMOUNT_VALUE.search(item.text)
            if amount:
                continue
        if item.type == EntityType.PHONE_NUMBER:
            clipped = _phone_value_span(item.text)
            if clipped:
                kept.append(_resized(item, *clipped))
                continue
        if item.type == EntityType.IP_ADDRESS:
            clipped = _ip_value_span(item.text)
            if clipped:
                kept.append(_resized(item, *clipped))
                continue
            if len(item.text.split()) >= 2:
                continue
        if item.type == EntityType.MONEY_AMOUNT:
            continue
        kept.append(item)
    return kept


def _drop_nested_wrappers(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    """Drop a clause-sized overlay that only exists because it contains real PII."""
    kept: list[EntityCandidate] = []
    for item in candidates:
        if item.detector == "USER_DEFINED_TERM" or item.type in _KEEP_WRAPPER_TYPES:
            kept.append(item)
            continue
        inners = [
            other
            for other in candidates
            if other.id != item.id
            and other.type in _INNER_VALUE_TYPES
            and _contains(item, other)
            and (other.end - other.start) < (item.end - item.start)
        ]
        if not inners:
            kept.append(item)
            continue
        folded = fold_tr_identity(item.text)
        extra_tokens = len(item.text.split()) - max(len(inner.text.split()) for inner in inners)
        if extra_tokens >= 2 or any(cue in folded for cue in _WRAPPER_CUES):
            continue
        kept.append(item)
    return kept


def _drop_inside_ibans(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    covers = [item for item in candidates if item.type == EntityType.IBAN]
    if not covers:
        return candidates
    kept: list[EntityCandidate] = []
    for item in candidates:
        if item.type in _INSIDE_IBAN and any(_contains(cover, item) for cover in covers):
            continue
        kept.append(item)
    return kept


def _drop_courts_without_chamber(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    """Keep high courts and chambered local courts; drop petition addressees."""
    from app.detectors.legal.court import court_ordinal, is_duty_court, is_high_court_name

    kept: list[EntityCandidate] = []
    for item in candidates:
        if item.type != EntityType.COURT_NAME:
            kept.append(item)
            continue
        if item.detector.startswith("EN_"):
            kept.append(item)
            continue
        if is_high_court_name(item.text):
            kept.append(item)
            continue
        if item.attributes.get("mask_scope") == "header_line":
            kept.append(item)
            continue
        ordinal = item.attributes.get("ordinal") or court_ordinal(item.text)
        if ordinal:
            kept.append(item)
            continue
        if is_duty_court(item.text):
            continue
        kept.append(item)
    return kept


_COMPANY_SUFFIX_KEEP = re.compile(r"(?i)a\.?\s*ş\.?|\bltd\.?|limited\s+şirket")


def _drop_legal_boilerplate(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    kept: list[EntityCandidate] = []
    for item in candidates:
        if item.detector == "USER_DEFINED_TERM" or item.type in _KEEP_FROM_BOILERPLATE:
            kept.append(item)
            continue
        if item.detector.startswith("EN_"):
            kept.append(item)
            continue
        if item.type == EntityType.COMPANY_NAME and _COMPANY_SUFFIX_KEEP.search(item.text):
            kept.append(item)
            continue
        if _looks_like_legal_boilerplate(item.text):
            continue
        kept.append(item)
    return kept


_AV_HEAD = re.compile(r"(?i)^(av\.?|avukat)(?:\s|\.|$)")
_COUNSEL_LEFT = re.compile(
    r"(?i)(?:av\.?|avukat|müdafi[iı]?|mudafi[iı]?|vekil[iı]?)\s*[.:]?\s*$"
)
_PROMOTE_TO_COUNSEL = frozenset(
    {
        EntityType.PERSON_NAME,
        EntityType.FIRST_NAME,
        EntityType.LAST_NAME,
        EntityType.ALIAS,
    }
)


def promote_counsel_titles(pages: list, candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    """Reclassify a person span that sits immediately after Av./avukat/vekil."""
    by_page = {getattr(page, "page", 0): page for page in pages}
    updated: list[EntityCandidate] = []
    for item in candidates:
        if item.type == EntityType.LAWYER_NAME:
            updated.append(item)
            continue
        if item.type not in _PROMOTE_TO_COUNSEL:
            updated.append(item)
            continue
        page = by_page.get(item.page)
        left = ""
        if page is not None:
            local_start = item.start - getattr(page, "document_offset", 0)
            left = page.text[max(0, local_start - 28) : max(0, local_start)]
        if _AV_HEAD.match(item.text.strip()) or _COUNSEL_LEFT.search(left):
            updated.append(
                item.model_copy(update={"type": EntityType.LAWYER_NAME, "role": "COUNSEL"})
            )
            continue
        updated.append(item)
    return updated


def merge_rule_candidates(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    """Keep the most specific overlapping candidate per semantic group."""
    working = _drop_nested_wrappers(
        _drop_inside_ibans(
            _drop_legal_boilerplate(
                _drop_courts_without_chamber(
                    _clip_value_spans(
                        _clip_person_candidates(
                            _drop_places_inside_courts(
                                _drop_contained_in_court_header(
                                    _drop_contained_in_uyap(_reclassify_uyap_urls(candidates))
                                )
                            )
                        )
                    )
                )
            )
        )
    )
    ordered = sorted(working, key=_score, reverse=True)
    kept: list[EntityCandidate] = []
    for item in ordered:
        group = _group_of(item.type)
        conflict = False
        for other in kept:
            if not _overlaps(item, other):
                continue
            other_group = _group_of(other.type)
            if group and group == other_group:
                if _has_professional_title(item.text) and _contains(item, other):
                    kept = [kept_item for kept_item in kept if kept_item.id != other.id]
                    continue
                if _has_professional_title(other.text) and _contains(other, item):
                    conflict = True
                    break
                conflict = True
                break
            if item.type == other.type:
                conflict = True
                break
            if other.type in {EntityType.ORGANISATION, EntityType.COMPANY_NAME, EntityType.COURT_NAME} and item.type in _PERSON:
                if _contains(other, item) or (
                    other.type == EntityType.COURT_NAME and _person_is_institutional_partial(other, item)
                ):
                    conflict = True
                    break
            if item.type in {EntityType.ORGANISATION, EntityType.COMPANY_NAME, EntityType.COURT_NAME} and other.type in _PERSON:
                if _contains(item, other) or (
                    item.type == EntityType.COURT_NAME and _person_is_institutional_partial(item, other)
                ):
                    kept = [kept_item for kept_item in kept if kept_item.id != other.id]
        if not conflict:
            kept.append(item)
    kept.sort(key=lambda item: (item.start, item.end, item.type.value))
    return kept
