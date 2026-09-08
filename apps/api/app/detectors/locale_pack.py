"""Locale pack system for extensible multi-jurisdiction detection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterable

if TYPE_CHECKING:
    from app.detectors.registry import Detector, PageText
    from app.domain.models import EntityCandidate


@dataclass
class LocalePack:
    """A collection of detection rules, gazetteers, and label packs for a jurisdiction.
    
    Example: Turkish pack includes TR-specific detectors, Turkish city/court names,
    Turkish structural label patterns (e.g., "Doğum Tarihi:"), etc.
    """
    
    locale_id: str  # e.g., "tr", "de", "en-us"
    name: str  # Human-readable name (e.g., "Turkish Legal Documents")
    detectors: list[tuple[str, Detector]]  # [(detector_name, detector_function)]
    structural_labels: dict[str, tuple[str, ...]] | None = None  # semantic label → aliases
    checksum_validators: dict[str, Callable[[str], bool]] | None = None
    placeholder_prefixes: dict[str, str] | None = None  # entity_type → localized prefix
    role_labels: dict[str, str] | None = None  # role_key → localized label


# Global registry of available locale packs
_LOCALE_PACKS: dict[str, LocalePack] = {}


def register_locale_pack(pack: LocalePack) -> None:
    """Register a locale pack for use in detection."""
    _LOCALE_PACKS[pack.locale_id] = pack


def get_locale_pack(locale_id: str) -> LocalePack | None:
    """Get a registered locale pack by ID."""
    return _LOCALE_PACKS.get(locale_id)


def list_locale_packs() -> list[LocalePack]:
    """List all registered locale packs."""
    return list(_LOCALE_PACKS.values())


def locale_ids_for_document(raw: str | None) -> list[str] | None:
    """Map job/document language to locale-pack IDs.

    English documents use the English-General pack plus global structured
    detectors. Turkish and unset languages keep the legacy path (``None``)
    so existing TR tests and call sites stay unchanged.

    Future jurisdiction packs (en-GB, en-US, …) can be appended here without
    changing detector internals. V1 still routes all English locales to ``en``.
    """
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"en", "en-us", "en-gb", "en-ca", "en-au", "english"}:
        return ["global", "en"]
    return None


def run_locale_detectors(
    pages: list["PageText"],
    locale_ids: list[str],
) -> tuple[list["EntityCandidate"], list[str]]:
    """Run detectors from multiple locale packs.
    
    Args:
        pages: Document pages to scan
        locale_ids: List of locale pack IDs to use (e.g., ["global", "tr"])
    
    Returns:
        (candidates, detector_names)
    """
    candidates: list[EntityCandidate] = []
    detector_names: list[str] = []
    
    for locale_id in locale_ids:
        pack = get_locale_pack(locale_id)
        if pack is None:
            continue
        
        for detector_name, detector_func in pack.detectors:
            for page in pages:
                candidates.extend(detector_func(page))
            detector_names.append(detector_name)
    
    # Deduplicate exact span/type matches (country-specific > global)
    candidates.sort(key=lambda item: (
        item.start,
        item.end,
        not item.detector.startswith("GLOBAL"),  # Non-global first
    ))
    
    unique: dict[tuple[int, int, str], EntityCandidate] = {}
    for candidate in candidates:
        key = (candidate.start, candidate.end, candidate.type.value)
        unique.setdefault(key, candidate)

    from app.detectors.legal.merge import merge_rule_candidates, promote_counsel_titles
    from app.detectors.scoring import apply_scoring
    from app.detectors.legal.identifier_repeats import (
        IBAN_REPEAT,
        PHONE_REPEAT,
        PORT_REPEAT,
        propagate_identifier_repeats,
    )
    from app.detectors.legal.repeats import DETECTOR_NAME as NAME_REPEAT
    from app.detectors.legal.repeats import pair_adjacent_person_name_tokens
    from app.detectors.legal.repeats import propagate_person_name_repeats
    from app.detectors.verification import apply_verification

    scored = apply_scoring(pages, list(unique.values()))
    merged = merge_rule_candidates(scored)
    if any(item.detector.startswith("EN_") for item in merged):
        detector_names.append("EN_EVIDENCE_SCORING")
    if any(item.detector.startswith("TR_") for item in merged) or "tr" in locale_ids:
        detector_names.append("TR_EVIDENCE_SCORING")
    if any(item.detector == "TR_NARRATIVE_PERSON" for item in merged):
        detector_names.append("TR_NARRATIVE_PERSON")
    if any(item.detector == "TR_EVIDENCE_ADDRESS" for item in merged):
        detector_names.append("TR_EVIDENCE_ADDRESS")
    for extra in (
        "EN_ROLE_PERSON",
        "EN_LEGAL_PARTY",
        "EN_TITLED_PERSON",
        "EN_SIGNATURE_PERSON",
        "EN_NARRATIVE_PERSON",
        "EN_CASE_NUMBER",
        "EN_FILE_NUMBER",
        "EN_COURT",
        "EN_COMPANY_SUFFIX",
        "EN_ORGANISATION",
        "EN_ADDRESS",
        "EN_BIRTH",
        "EN_PASSPORT",
    ):
        if extra not in detector_names and any(item.detector == extra for item in merged):
            detector_names.append(extra)
    paired = pair_adjacent_person_name_tokens(pages, merged)
    if paired:
        merged = merge_rule_candidates(merged + paired)
        detector_names.append("TR_NAME_PAIR")
    repeats = propagate_person_name_repeats(pages, merged)
    if repeats:
        merged = merge_rule_candidates(merged + repeats)
        detector_names.append(NAME_REPEAT)
    identifiers = propagate_identifier_repeats(pages, merged)
    if identifiers:
        merged = merge_rule_candidates(merged + identifiers)
        detector_names.extend(
            detector
            for detector in (IBAN_REPEAT, PHONE_REPEAT, PORT_REPEAT)
            if any(item.detector == detector for item in identifiers)
        )
    merged = promote_counsel_titles(pages, merged)
    from app.detectors.registry import drop_retired_detections

    return apply_verification(drop_retired_detections(merged)), detector_names
