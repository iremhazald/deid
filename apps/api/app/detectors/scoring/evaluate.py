"""Attach deterministic evidence to existing detector candidates."""

from __future__ import annotations

import re

from app.detectors.legal.names import (
    collapse_name,
    is_isolated_letter_person_surface,
    is_isolated_uppercase_fragment,
    is_non_person_surface,
    is_procedural_notice_surface,
    is_uets_label_surface,
    strip_possessive,
)
from app.detectors.legal.repeats import is_repeatable_person_name
from app.domain.models import EntityCandidate, EntityType

from app.detectors.scoring.context import DocumentIndex, person_surface_key
from app.detectors.scoring.exclusions import (
    fold,
    is_birth_context,
    is_case_reference,
    is_company_phrase,
    is_court_phrase,
    is_date_like,
    is_institution_phrase,
    is_legal_field_phrase,
    is_legal_heading_surface,
    is_legal_role_word,
    is_list_marker,
    is_paragraph_number_marker,
    is_month_name,
    is_non_birth_date_context,
    looks_like_hearing_date,
)
from app.detectors.scoring.first_names import is_known_first_name
from app.detectors.scoring.hard import hard_validate
from app.detectors.scoring.models import (
    CandidateClass,
    Evidence,
    EvidenceSource,
    HardValidation,
    ScoredCandidate,
    ScoringDecision,
)
from app.detectors.scoring.english_page import ordinary_english_page_noun_at
from app.detectors.scoring.ner_location_context import english_ner_location_contradiction
from app.detectors.scoring.ner_person_context import english_ner_person_contradiction
from app.detectors.scoring.person_families import (
    cap_en_role_structure_family,
    is_en_person_candidate,
)
from app.detectors.scoring.policy import (
    EVIDENCE_ADDRESS_DETECTOR,
    EXISTING_DETECTOR_WEIGHT,
    EXISTING_HIGH_CONFIDENCE_WEIGHT,
    HIGH_CONFIDENCE_STRUCTURED_SOURCE,
    LOCAL_NER_SOURCES,
    NARRATIVE_PERSON_DETECTOR,
    candidate_class_for,
    policy_for,
)

_TCKN_LABEL = re.compile(
    r"(?i)(?:t\.?\s*c\.?\s*)?(?:kimlik(?:\s+(?:no|numara(?:s[ıi])?))?|tckn)"
)
_IBAN_LABEL = re.compile(
    r"(?i)(?:iban|hesap(?:\s+no)?|banka|ödeme|odeme|havale|eft|transfer|"
    r"bank\s+account|account\s+(?:no|number)|sort\s+code|routing\s+number)"
)
_CARD_LABEL = re.compile(r"(?i)(?:kart|kredi\s+kart|card|visa|mastercard)")
_PHONE_LABEL = re.compile(
    r"(?i)(?:telefon|tel\.?|gsm|cep|iletişim|iletisim|hat|"
    r"phone(?:\s+number)?|telephone(?:\s+number)?|mobile|cell|contact\s+number)"
)
_PLATE_LABEL = re.compile(r"(?i)(?:plaka|araç|arac|otomobil|ruhsat|tescil)")
_VKN_LABEL = re.compile(r"(?i)(?:vergi|v\.?\s*k\.?\s*n\.?|vkn)")
_POSTAL_LABEL = re.compile(
    r"(?i)(?:posta\s+kodu|postakodu|pk[:.]|postal\s+code|postcode|zip(?:\s+code)?)"
)
_EMAIL_LABEL = re.compile(r"(?i)(?:e-?posta|email(?:\s+address)?|e-mail|mail)")
_URL_LABEL = re.compile(r"(?i)(?:adresinden|http|www|url)")
_IP_LABEL = re.compile(r"(?i)(?:ip(?:\s+no|\s+adres)?|port)")
_PARTY_CUE = re.compile(
    r"(?i)(?:sanık|sanik|davacı|davaci|davalı|davali|mağdur|magdur|"
    r"müşteki|musteki|borçlu|borclu|alacaklı|alacakli|vekil|avukat|müdafi|mudafi)"
)
_BIRTH_LABEL = re.compile(
    r"(?i)(?:doğum|dogum|doğumlu|dogumlu|nüfus|nufus|kimlik|"
    r"date\s+of\s+birth|birth\s+date|d\.?o\.?b\.?|born(?:\s+on)?|birthplace|place\s+of\s+birth)"
)
_NON_BIRTH = re.compile(
    r"(?i)(?:duruşma|durusma|karar\s+tarihi|tebli[gğ]\s+tarihi|"
    r"sözleşme|sozlesme|başvuru\s+tarihi|basvuru\s+tarihi|olay\s+tarihi|"
    r"hearing\s+date|decision\s+date|order\s+date|filing\s+date|"
    r"service\s+date|contract\s+date|execution\s+date)"
)
_LEGAL_REF_LABEL = re.compile(
    r"(?i)(?:esas|e\.|karar|k\.|dosya|soruşturma|sorusturma|talimat|iddianame|"
    r"arabuluculuk|case\s+(?:no|number)|claim\s+(?:no|number)|file\s+(?:no|number)|"
    r"docket\s+(?:no|number)|matter\s+(?:no|number)|reference\s+(?:no|number)|"
    r"proceeding\s+(?:no|number)|application\s+no|appeal\s+no|ref\.?)"
)
_ADDRESS_LABEL = re.compile(
    r"(?i)(?:adres(?:inde)?|ikamet|address(?:\s+for\s+service)?|"
    r"(?:home|residential|registered|service|correspondence|postal)\s+address)"
)
_ADDRESS_MARKERS = re.compile(
    r"(?i)(?:mahallesi|mah\.?|caddesi|cad\.?|soka[gğ]ı|sok\.?|bulvar[ıi]|bul\.?|"
    r"apartman[ıi]|apt\.?|sitesi|no:?|daire|kat|"
    r"street|st\.?|road|rd\.?|avenue|ave\.?|lane|ln\.?|drive|boulevard|blvd\.?|"
    r"place|square|way|terrace|close|crescent|parkway|highway|flat|suite|unit|floor)"
)
_MEDIATION = re.compile(r"(?i)arabuluculuk")
_BASVURU = re.compile(r"(?i)ba[şs]vuru")
_NARRATIVE_CUE = re.compile(
    r"(?i)(?:aracılığıyla|araciligiyla|tarafından|tarafindan|"
    r"adlı|adli|isimli|beyanında|beyaninda|ifadesinde|ifadesi|"
    r"beyan\s+etti|ile\s+birlikte)"
)
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
_SOFT_SURFACE_TYPES = _PERSON_TYPES | {
    EntityType.LOCATION,
    EntityType.BIRTH_PLACE,
    EntityType.ORGANISATION,
    EntityType.COMPANY_NAME,
}


def _ev(code: str, weight: int, source: str, hard_reject: bool = False) -> Evidence:
    return Evidence(code=code, weight=weight, source=source, hard_reject=hard_reject)


def _nearby(index: DocumentIndex, start: int, end: int, radius: int, adjacent: bool) -> str:
    window = index.char_window(start, end, radius)
    if adjacent:
        window = f"{window} {index.adjacent_lines(start, end)}"
    return window


def _legal_ref_kind(detector: str, nearby: str) -> str | None:
    folded = fold(nearby)
    if detector == "TR_ARBITRATION_NUMBER" or "arabuluculuk" in folded:
        return "MEDIATION"
    if "sorusturma" in folded:
        return "INVESTIGATION"
    if "talimat" in folded:
        return "INSTRUCTION"
    if "iddianame" in folded:
        return "INDICTMENT"
    if detector == "TR_DECISION_NUMBER" or "karar" in folded:
        return "DECISION"
    if detector == "TR_CASE_NUMBER" or "esas" in folded:
        return "CASE"
    if detector == "TR_FILE_NUMBER" or "dosya" in folded:
        return "FILE"
    return None


def _add_existing_floor(scored: ScoredCandidate) -> None:
    detector = scored.detector
    if detector in {NARRATIVE_PERSON_DETECTOR, EVIDENCE_ADDRESS_DETECTOR, "EN_NARRATIVE_PERSON"}:
        return
    if detector in LOCAL_NER_SOURCES:
        return
    if detector == "EN_ACCOUNT":
        return
    if detector in HIGH_CONFIDENCE_STRUCTURED_SOURCE:
        if scored.entity.type in _PERSON_TYPES:
            # Provenance only. PERSON score uses this as a minimum floor, not +10.
            scored.evidence.append(_ev("existing_high_confidence", 0, EvidenceSource.DETECTOR))
            return
        scored.evidence.append(
            _ev("existing_high_confidence", EXISTING_HIGH_CONFIDENCE_WEIGHT, EvidenceSource.DETECTOR)
        )
        return
    scored.evidence.append(
        _ev("existing_detector_candidate", EXISTING_DETECTOR_WEIGHT, EvidenceSource.DETECTOR)
    )


def _score_identifier(scored: ScoredCandidate, index: DocumentIndex) -> None:
    entity = scored.entity
    start, end = entity.start, entity.end
    nearby = _nearby(index, start, end, 40, True)
    line = index.line_window(start, end).text

    if entity.type == EntityType.NATIONAL_ID:
        if scored.hard_validation == HardValidation.VALID:
            scored.evidence.append(_ev("valid_tckn_checksum", 10, EvidenceSource.VALIDATOR))
        if _TCKN_LABEL.search(line) or _TCKN_LABEL.search(index.left_window(start, 40)):
            scored.evidence.append(_ev("tckn_label_nearby", 3, EvidenceSource.CONTEXT))
        if _PARTY_CUE.search(nearby):
            scored.evidence.append(_ev("party_block_context", 2, EvidenceSource.CONTEXT))
        if index.inside_iban(start, end):
            scored.negative_evidence.append(
                _ev("inside_iban", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if not index.isolated_from_digit_run(start, end):
            scored.negative_evidence.append(
                _ev("inside_longer_digit_run", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )

    elif entity.type == EntityType.IBAN:
        if scored.hard_validation == HardValidation.VALID:
            scored.evidence.append(_ev("valid_mod97", 10, EvidenceSource.VALIDATOR))
        elif scored.hard_validation == HardValidation.INVALID:
            scored.negative_evidence.append(_ev("invalid_mod97", -10, EvidenceSource.VALIDATOR))
        if _IBAN_LABEL.search(nearby):
            scored.evidence.append(_ev("iban_label_nearby", 3, EvidenceSource.CONTEXT))
        if re.search(r"(?i)(?:banka|havale|eft|ödeme|odeme|transfer)", nearby):
            scored.evidence.append(_ev("bank_context", 2, EvidenceSource.CONTEXT))

    elif entity.type == EntityType.CREDIT_CARD:
        if scored.hard_validation == HardValidation.VALID:
            scored.evidence.append(_ev("valid_luhn", 8, EvidenceSource.VALIDATOR))
        if _CARD_LABEL.search(nearby):
            scored.evidence.append(_ev("card_label", 3, EvidenceSource.CONTEXT))
        if re.search(r"(?i)(?:ödeme|odeme|tahsil|pos)", nearby):
            scored.evidence.append(_ev("payment_context", 2, EvidenceSource.CONTEXT))
        if index.inside_iban(start, end):
            scored.negative_evidence.append(
                _ev("valid_iban_component", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if index.inside_tckn(start, end) or index.overlaps_any(start, end, index.tckn_spans):
            scored.negative_evidence.append(
                _ev("valid_tckn_candidate", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if is_case_reference(entity.text, nearby):
            scored.negative_evidence.append(_ev("case_number_structure", -6, EvidenceSource.NEGATIVE))

    elif entity.type == EntityType.EMAIL:
        scored.evidence.append(_ev("email_pattern", 8, EvidenceSource.STRUCTURE))
        if _EMAIL_LABEL.search(nearby):
            scored.evidence.append(_ev("email_label", 2, EvidenceSource.CONTEXT))

    elif entity.type == EntityType.URL:
        if re.match(r"(?i)https?://", entity.text):
            scored.evidence.append(_ev("explicit_scheme", 8, EvidenceSource.STRUCTURE))
        if "vatandas.uyap.gov.tr" in entity.text.lower():
            scored.evidence.append(_ev("uyap_domain", 4, EvidenceSource.STRUCTURE))
        if _URL_LABEL.search(nearby):
            scored.evidence.append(_ev("url_label", 1, EvidenceSource.CONTEXT))

    elif entity.type == EntityType.IP_ADDRESS:
        if scored.hard_validation == HardValidation.VALID:
            scored.evidence.append(_ev("valid_ipv4", 8, EvidenceSource.VALIDATOR))
        if _IP_LABEL.search(nearby):
            scored.evidence.append(_ev("ip_label", 2, EvidenceSource.CONTEXT))

    elif entity.type == EntityType.PHONE_NUMBER:
        compact = re.sub(r"\D", "", entity.text)
        if compact[-10:].startswith("5") if len(compact) >= 10 else False:
            scored.evidence.append(_ev("valid_05xx_structure", 5, EvidenceSource.STRUCTURE))
        else:
            scored.evidence.append(_ev("known_area_code", 4, EvidenceSource.STRUCTURE))
        if _PHONE_LABEL.search(nearby):
            scored.evidence.append(_ev("phone_tel_label", 3, EvidenceSource.CONTEXT))
        if _PARTY_CUE.search(nearby):
            scored.evidence.append(_ev("party_lawyer_block", 2, EvidenceSource.CONTEXT))
        if index.inside_iban(start, end):
            scored.negative_evidence.append(
                _ev("inside_iban", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if index.inside_tckn(start, end):
            scored.negative_evidence.append(
                _ev("inside_tckn", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if not index.isolated_from_digit_run(start, end):
            scored.negative_evidence.append(_ev("inside_long_digit_run", -5, EvidenceSource.NEGATIVE))
        if is_case_reference(entity.text, nearby):
            scored.negative_evidence.append(_ev("case_number_context", -5, EvidenceSource.NEGATIVE))
        if is_date_like(entity.text) or is_date_like(nearby[max(0, len(nearby) // 3) :]):
            if is_date_like(entity.text):
                scored.negative_evidence.append(_ev("date_structure", -5, EvidenceSource.NEGATIVE))

    elif entity.type == EntityType.TAX_IDENTIFIER:
        scored.evidence.append(_ev("ten_digit_structure", 2, EvidenceSource.STRUCTURE))
        if _VKN_LABEL.search(index.left_window(start, 48)) or _VKN_LABEL.search(line):
            scored.evidence.append(_ev("vkn_vergi_no_label", 6, EvidenceSource.CONTEXT))
        else:
            scored.negative_evidence.append(
                _ev("unlabeled_vkn", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if scored.hard_validation == HardValidation.VALID:
            scored.evidence.append(_ev("valid_checksum_if_available", 4, EvidenceSource.VALIDATOR))

    elif entity.type in {EntityType.CASE_NUMBER, EntityType.FILE_NUMBER, EntityType.DECISION_NUMBER}:
        if is_list_marker(entity.text):
            scored.negative_evidence.append(
                _ev("list_numbering", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        elif is_paragraph_number_marker(entity.text, index.full_text, start):
            scored.negative_evidence.append(
                _ev("paragraph_numbering", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        scored.evidence.append(_ev("valid_year_number_pattern", 3, EvidenceSource.STRUCTURE))
        if _LEGAL_REF_LABEL.search(nearby):
            scored.evidence.append(_ev("legal_ref_label", 5, EvidenceSource.CONTEXT))
        if _MEDIATION.search(nearby):
            scored.evidence.append(_ev("arabuluculuk", 6, EvidenceSource.CONTEXT))
            if _BASVURU.search(nearby):
                scored.evidence.append(_ev("basvuru_in_mediation", 2, EvidenceSource.CONTEXT))
        if is_date_like(entity.text) and not _LEGAL_REF_LABEL.search(nearby):
            scored.negative_evidence.append(_ev("date_context", -7, EvidenceSource.NEGATIVE))
        kind = _legal_ref_kind(entity.detector, line)
        if kind and "legal_ref_kind" not in entity.attributes:
            entity.attributes["legal_ref_kind"] = kind

    elif entity.type == EntityType.VEHICLE_PLATE:
        scored.evidence.append(_ev("plate_syntax", 4, EvidenceSource.STRUCTURE))
        scored.evidence.append(_ev("valid_province_code", 3, EvidenceSource.STRUCTURE))
        if _PLATE_LABEL.search(nearby):
            scored.evidence.append(_ev("plaka_context", 4, EvidenceSource.CONTEXT))
        if is_case_reference(entity.text, nearby):
            scored.negative_evidence.append(_ev("case_number", -6, EvidenceSource.NEGATIVE))

    elif entity.type == EntityType.DATE_OF_BIRTH:
        scored.evidence.append(_ev("valid_date", 2, EvidenceSource.STRUCTURE))
        left = index.left_window(start, 36)
        right = index.right_window(end, 24)
        nearby_birth = f"{left} {right}"
        if _BIRTH_LABEL.search(nearby_birth) or is_birth_context(nearby_birth):
            scored.evidence.append(_ev("birth_label", 6, EvidenceSource.CONTEXT))
        elif entity.detector not in {
            "TR_BIRTH_INFO",
            "TR_LEGAL_PARTY",
            "TR_DATE_FORMAT",
            "TR_PARENTAGE",
            "EN_BIRTH",
        }:
            scored.negative_evidence.append(
                _ev("missing_birth_context", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if looks_like_hearing_date(left) or _NON_BIRTH.search(left):
            scored.negative_evidence.append(
                _ev("hearing_or_procedural_date", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if is_non_birth_date_context(left) and not is_birth_context(nearby_birth):
            scored.negative_evidence.append(_ev("karar_teblig_or_event_date", -8, EvidenceSource.NEGATIVE))

    elif entity.type == EntityType.POSTAL_CODE:
        scored.evidence.append(_ev("five_digit", 1, EvidenceSource.STRUCTURE))
        if _POSTAL_LABEL.search(index.left_window(start, 24)):
            scored.evidence.append(_ev("posta_kodu_label", 7, EvidenceSource.CONTEXT))
        else:
            scored.negative_evidence.append(
                _ev("unlabeled_postal", -10, EvidenceSource.NEGATIVE, hard_reject=True)
            )
        if index.overlaps_any(start, end, index.address_spans):
            scored.evidence.append(_ev("near_address_candidate", 2, EvidenceSource.CONTEXT))

    elif entity.type == EntityType.UYAP_ACCESS:
        scored.evidence.append(_ev("vatandas_uyap_gov_tr", 8, EvidenceSource.STRUCTURE))
        scored.evidence.append(_ev("footer_structure", 4, EvidenceSource.STRUCTURE))


def _reject_unusable_surface(scored: ScoredCandidate) -> None:
    """Drop isolated letters, OP-like fragments, and notice wording on soft types."""
    entity = scored.entity
    if entity.detector == "USER_DEFINED_TERM":
        return
    if is_uets_label_surface(entity.text):
        scored.negative_evidence.append(
            _ev("uets_field_label", -10, EvidenceSource.NEGATIVE, hard_reject=True)
        )
        return
    if is_procedural_notice_surface(entity.text):
        scored.negative_evidence.append(
            _ev("procedural_notice_term", -10, EvidenceSource.NEGATIVE, hard_reject=True)
        )
        return
    if entity.type not in _SOFT_SURFACE_TYPES:
        return
    if is_isolated_letter_person_surface(entity.text):
        scored.negative_evidence.append(
            _ev("isolated_letter_person", -10, EvidenceSource.NEGATIVE, hard_reject=True)
        )
        return
    if is_isolated_uppercase_fragment(entity.text):
        scored.negative_evidence.append(
            _ev("isolated_uppercase_fragment", -10, EvidenceSource.NEGATIVE, hard_reject=True)
        )
        return
    if is_procedural_notice_surface(entity.text):
        scored.negative_evidence.append(
            _ev("procedural_notice_term", -10, EvidenceSource.NEGATIVE, hard_reject=True)
        )


def _score_person(scored: ScoredCandidate, index: DocumentIndex) -> None:
    entity = scored.entity
    if entity.detector != "USER_DEFINED_TERM" and is_isolated_letter_person_surface(
        entity.text
    ):
        scored.negative_evidence.append(
            _ev("isolated_letter_person", -10, EvidenceSource.NEGATIVE, hard_reject=True)
        )
        return
    tokens = collapse_name(strip_possessive(entity.text)).split()
    nearby = _nearby(index, entity.start, entity.end, 60, True)
    if 2 <= len(tokens) <= 4:
        scored.evidence.append(_ev("two_to_four_proper_name_tokens", 3, EvidenceSource.STRUCTURE))
    if tokens and is_known_first_name(tokens[0]):
        scored.evidence.append(_ev("first_name_lexicon", 4, EvidenceSource.LEXICON))
    if len(tokens) >= 2:
        scored.evidence.append(_ev("surname_like", 1, EvidenceSource.STRUCTURE))
    if entity.type == EntityType.LAWYER_NAME or entity.role in {"COUNSEL", "DEFENSE_COUNSEL", "LAWYER"}:
        scored.evidence.append(_ev("lawyer_title_or_role", 7, EvidenceSource.CONTEXT))
    if entity.type == EntityType.JUDGE_NAME or entity.role in {"JUDGE", "PRESIDENT"}:
        scored.evidence.append(_ev("roster_or_judge_role", 7, EvidenceSource.CONTEXT))
    if entity.detector in {
        "TR_LEGAL_PARTY",
        "TR_COUNSEL_BLOCK",
        "TR_JUDICIAL_ROSTER",
        "TR_ROLE_PERSON",
        "TR_MENTIONED_PERSON",
        "TR_STATEMENT",
        "TR_PARENTAGE",
        "TR_LEGAL_ROLE_NAME",
        "EN_LEGAL_PARTY",
        "EN_ROLE_PERSON",
        "EN_TITLED_PERSON",
        "EN_SIGNATURE_PERSON",
    }:
        scored.evidence.append(_ev("title_or_party_or_roster", 6, EvidenceSource.DETECTOR))
    if entity.detector == "USER_DEFINED_TERM":
        scored.evidence.append(_ev("user_dictionary", 10, EvidenceSource.USER))
    key = person_surface_key(entity.text)
    if (
        is_repeatable_person_name(entity.text)
        and key in index.local_person_keys
        and entity.detector in {NARRATIVE_PERSON_DETECTOR, "TR_NAME_REPEAT", "EN_NARRATIVE_PERSON"}
    ):
        scored.evidence.append(_ev("document_local_person_surface", 5, EvidenceSource.LOCAL))
    narrative = entity.detector == NARRATIVE_PERSON_DETECTOR
    if is_non_person_surface(entity.text) or is_legal_role_word(entity.text):
        scored.negative_evidence.append(
            _ev("known_role_or_stopword", -8, EvidenceSource.NEGATIVE, hard_reject=True)
        )
    if is_court_phrase(entity.text) or is_institution_phrase(entity.text):
        scored.negative_evidence.append(
            _ev("court_or_institution_phrase", -8, EvidenceSource.NEGATIVE, hard_reject=True)
        )
    if is_legal_heading_surface(entity.text):
        scored.negative_evidence.append(
            _ev("legal_heading_surface", -8, EvidenceSource.NEGATIVE, hard_reject=True)
        )
    if is_company_phrase(entity.text):
        scored.negative_evidence.append(
            _ev("company_suffix", -7, EvidenceSource.NEGATIVE, hard_reject=narrative)
        )
    if is_month_name(entity.text):
        scored.negative_evidence.append(
            _ev("month_name", -6, EvidenceSource.NEGATIVE, hard_reject=narrative)
        )
    if is_legal_field_phrase(entity.text):
        scored.negative_evidence.append(
            _ev("legal_field_phrase", -6, EvidenceSource.NEGATIVE, hard_reject=narrative)
        )
    if index.overlaps_any(entity.start, entity.end, index.org_spans) and narrative:
        scored.negative_evidence.append(
            _ev("overlaps_institution", -8, EvidenceSource.NEGATIVE, hard_reject=True)
        )
    if narrative and _NARRATIVE_CUE.search(nearby):
        scored.evidence.append(_ev("legal_narrative_context", 2, EvidenceSource.CONTEXT))
    if ordinary_english_page_noun_at(index, entity.start, entity.end):
        scored.negative_evidence.append(
            _ev("english_lexical_page_noun", -10, EvidenceSource.NEGATIVE, hard_reject=True)
        )
    entity.attributes["normalized_text_group"] = key
    entity.attributes["identity_resolved"] = False


def _score_address(scored: ScoredCandidate, index: DocumentIndex) -> None:
    entity = scored.entity
    nearby = _nearby(index, entity.start, entity.end, 80, True)
    markers = _ADDRESS_MARKERS.findall(entity.text)
    if markers:
        scored.evidence.append(_ev("address_markers", min(9, 3 * len(set(m.lower()[:3] for m in markers))), EvidenceSource.STRUCTURE))
    if _ADDRESS_LABEL.search(nearby):
        scored.evidence.append(_ev("adres_label", 4, EvidenceSource.CONTEXT))
    if is_institution_phrase(entity.text) and len(entity.text.split()) <= 5:
        scored.negative_evidence.append(_ev("institution_name", -5, EvidenceSource.NEGATIVE))
    if is_court_phrase(entity.text):
        scored.negative_evidence.append(_ev("court_name", -6, EvidenceSource.NEGATIVE, hard_reject=True))
    if is_company_phrase(entity.text):
        scored.negative_evidence.append(_ev("company_name", -4, EvidenceSource.NEGATIVE))


def _score_org(scored: ScoredCandidate, index: DocumentIndex) -> None:
    text = scored.entity.text
    if re.search(
        r"(?i)(?:a\.?\s*ş\.?|ltd\.?|limited|llc|llp|inc(?:orporated)?|corp(?:oration)?|p\.?l\.?c\.?)",
        text,
    ):
        scored.evidence.append(_ev("company_suffix", 6, EvidenceSource.STRUCTURE))
    if re.search(r"(?i)(?:savcılı[gğ]ı|müdürlü[gğ]ü|bakanlı[gğ]ı)", text):
        scored.evidence.append(_ev("institution_suffix", 4, EvidenceSource.STRUCTURE))
    if scored.entity.type == EntityType.COURT_NAME:
        scored.evidence.append(_ev("court_type", 4, EvidenceSource.STRUCTURE))
    if re.search(
        r"(?i)(?:supreme court|high court|court of appeal|employment tribunal|"
        r"ministry of justice)",
        text,
    ):
        scored.evidence.append(_ev("en_court_structure", 3, EvidenceSource.STRUCTURE))
    folded_org = fold(text)
    generic_court = folded_org in {"tribunal", "tribunals", "court", "courts"} or folded_org in {
        "the tribunal",
        "this tribunal",
        "that tribunal",
        "a tribunal",
        "the court",
        "this court",
        "that court",
        "a court",
    }
    if generic_court:
        scored.negative_evidence.append(
            _ev("generic_court_term", -8, EvidenceSource.NEGATIVE, hard_reject=True)
        )


def decide(scored: ScoredCandidate) -> ScoringDecision:
    """HARD INVALID always IGNORE. No positive evidence may rescue it."""
    if scored.hard_validation == HardValidation.INVALID:
        return ScoringDecision.IGNORE
    if any(item.hard_reject for item in scored.negative_evidence):
        return ScoringDecision.IGNORE
    policy = policy_for(scored.entity.type, scored.detector)
    score = scored.evidence_score
    if scored.candidate_class == CandidateClass.STRICT and scored.hard_validation == HardValidation.VALID:
        return ScoringDecision.ACCEPT
    if scored.entity.type in {EntityType.EMAIL, EntityType.IP_ADDRESS, EntityType.URL, EntityType.UYAP_ACCESS}:
        if score >= policy.accept_threshold:
            return ScoringDecision.ACCEPT
    if score >= policy.accept_threshold:
        return ScoringDecision.ACCEPT
    if score >= policy.review_threshold:
        return ScoringDecision.REVIEW
    return ScoringDecision.IGNORE


def _evidence_payload(item: Evidence) -> dict:
    payload = {"code": item.code, "weight": item.weight, "source": item.source}
    if item.hard_reject:
        payload["hard_reject"] = True
    return payload


def _seed_evidence(raw: object) -> list[Evidence]:
    if not isinstance(raw, list):
        return []
    found: list[Evidence] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        try:
            weight = int(item.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0
        found.append(
            Evidence(
                code=str(item["code"]),
                weight=weight,
                source=str(item.get("source") or EvidenceSource.DETECTOR),
                hard_reject=bool(item.get("hard_reject")),
            )
        )
    return found


def _dedupe_evidence(items: list[Evidence]) -> list[Evidence]:
    seen: set[str] = set()
    unique: list[Evidence] = []
    for item in items:
        if item.code in seen:
            continue
        seen.add(item.code)
        unique.append(item)
    return unique


def attach_score(entity: EntityCandidate, scored: ScoredCandidate) -> EntityCandidate:
    """Write machine-readable evidence onto the public candidate without exposing a % score."""
    from app.detectors.scoring.models import verification_for

    attributes = dict(entity.attributes)
    attributes["evidence"] = [_evidence_payload(item) for item in scored.evidence]
    attributes["negative_evidence"] = [_evidence_payload(item) for item in scored.negative_evidence]
    attributes["evidence_score"] = scored.evidence_score
    attributes["hard_validation"] = scored.hard_validation.value
    attributes["scoring_decision"] = scored.decision.value
    attributes["candidate_class"] = scored.candidate_class.value
    if scored.conflict_reason:
        attributes["conflict_reason"] = scored.conflict_reason
    if scored.parent_candidate_id:
        attributes["parent_candidate_id"] = scored.parent_candidate_id
    update: dict = {
        "attributes": attributes,
        "needs_review": scored.decision == ScoringDecision.REVIEW,
        "verification_method": entity.verification_method or "evidence_weight",
    }
    if scored.decision == ScoringDecision.ACCEPT:
        update["needs_review"] = False
        if scored.hard_validation == HardValidation.VALID or entity.validated:
            update["validated"] = True
        if scored.hard_validation == HardValidation.VALID:
            update["verification_level"] = verification_for(scored.decision, scored.hard_validation)
        # Leave verification_level unset for soft ACCEPT so apply_verification
        # keeps the existing detector contract (e.g. validated landline).
    elif scored.decision == ScoringDecision.REVIEW:
        update["validated"] = False
        update["verification_level"] = verification_for(scored.decision, scored.hard_validation)
    return entity.model_copy(update=update)


def _add_ner_evidence(scored: ScoredCandidate, index: DocumentIndex) -> None:
    """Supporting local-NER evidence. Model score is never the decision."""
    if scored.detector not in LOCAL_NER_SOURCES:
        return
    entity = scored.entity
    attrs = entity.attributes or {}
    if entity.type in _PERSON_TYPES:
        scored.evidence.append(_ev("ner_person", 4, EvidenceSource.LOCAL))
    elif entity.type in {EntityType.ORGANISATION, EntityType.COMPANY_NAME}:
        scored.evidence.append(_ev("ner_organisation", 4, EvidenceSource.LOCAL))
    elif entity.type in {EntityType.LOCATION, EntityType.BIRTH_PLACE}:
        scored.evidence.append(_ev("ner_location", 5, EvidenceSource.LOCAL))
    raw_score = attrs.get("ner_model_score")
    try:
        model_score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        model_score = None
    if model_score is not None:
        if model_score >= 0.90:
            scored.evidence.append(_ev("ner_high_model_score", 2, EvidenceSource.LOCAL))
        elif model_score < 0.50:
            scored.negative_evidence.append(_ev("ner_weak_model_score", -2, EvidenceSource.NEGATIVE))
    if attrs.get("ner_overlap_existing_rule"):
        scored.evidence.append(_ev("ner_overlap_existing_rule", 2, EvidenceSource.CONTEXT))
    nearby = _nearby(index, entity.start, entity.end, 60, True)
    if _PARTY_CUE.search(nearby) or _NARRATIVE_CUE.search(nearby):
        scored.evidence.append(_ev("ner_legal_context", 2, EvidenceSource.CONTEXT))
    if ordinary_english_page_noun_at(index, entity.start, entity.end):
        scored.negative_evidence.append(
            _ev("english_lexical_page_noun", -10, EvidenceSource.NEGATIVE, hard_reject=True)
        )
    if (
        entity.type in _PERSON_TYPES
        and entity.detector == "LOCAL_NER_EN"
        and not attrs.get("ner_overlap_existing_rule")
    ):
        for code in english_ner_person_contradiction(index, entity.start, entity.end):
            hard = code == "english_lexical_page_noun"
            scored.negative_evidence.append(
                _ev(code, -10 if hard else -5, EvidenceSource.NEGATIVE, hard_reject=hard)
            )
    if entity.type == EntityType.LOCATION and entity.detector == "LOCAL_NER_EN":
        for code in english_ner_location_contradiction(
            index, entity.start, entity.end, entity.text
        ):
            scored.negative_evidence.append(_ev(code, -5, EvidenceSource.NEGATIVE))


def evaluate_candidate(entity: EntityCandidate, index: DocumentIndex) -> ScoredCandidate:
    """Build one authoritative evidence set. Seeded codes are not counted twice."""
    hard = hard_validate(entity)
    seeded_pos = _seed_evidence((entity.attributes or {}).get("evidence"))
    seeded_neg = _seed_evidence((entity.attributes or {}).get("negative_evidence"))
    scored = ScoredCandidate(
        entity=entity,
        candidate_class=candidate_class_for(entity.type, entity.detector),
        hard_validation=hard,
        evidence=list(seeded_pos),
        negative_evidence=list(seeded_neg),
    )
    _add_existing_floor(scored)
    _add_ner_evidence(scored, index)
    _reject_unusable_surface(scored)
    if entity.type in _PERSON_TYPES:
        _score_person(scored, index)
    elif entity.type == EntityType.ADDRESS:
        _score_address(scored, index)
    elif entity.type in {EntityType.ORGANISATION, EntityType.COMPANY_NAME, EntityType.COURT_NAME}:
        _score_org(scored, index)
    else:
        _score_identifier(scored, index)
    scored.evidence = _dedupe_evidence(scored.evidence)
    scored.negative_evidence = _dedupe_evidence(scored.negative_evidence)
    if is_en_person_candidate(scored):
        scored.evidence = cap_en_role_structure_family(scored.evidence)
    scored.evidence_score = sum(item.weight for item in scored.evidence) + sum(
        item.weight for item in scored.negative_evidence
    )
    if (
        scored.entity.type in _PERSON_TYPES
        and scored.detector in HIGH_CONFIDENCE_STRUCTURED_SOURCE
        and any(item.code == "existing_high_confidence" for item in scored.evidence)
        and scored.hard_validation != HardValidation.INVALID
        and not any(item.hard_reject for item in scored.negative_evidence)
    ):
        scored.evidence_score = max(scored.evidence_score, EXISTING_HIGH_CONFIDENCE_WEIGHT)
        scored.entity.attributes = dict(scored.entity.attributes or {})
        scored.entity.attributes["high_confidence_floor"] = EXISTING_HIGH_CONFIDENCE_WEIGHT
    scored.decision = decide(scored)
    return scored
