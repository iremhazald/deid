from __future__ import annotations

import hashlib
import re
import unicodedata

from app.detectors.textutil import fold_tr_identity
from app.domain.models import EntityCandidate, EntityType
from app.transforms.catalog import ROLE_TYPED, TYPE_TO_ROLE, normalize_role_key
from app.transforms.turkish_morphology import (
    analyze_inflected_surface,
    strip_inflection_if_safe,
)

_WHITESPACE = re.compile(r"\s+")


def normalize_entity_text(value: str) -> str:
    return _WHITESPACE.sub(" ", fold_tr_identity(value).strip())


def person_resolution_base(value: str) -> str:
    """Conservative person key: strip only a safe apostrophe case suffix.

    This produces a *normalized_text_group* key, not a real-world identity.
    ``Mehmet Yılmaz'ın`` may share a key with ``Mehmet Yılmaz``; ``Mehmet``
    and ``M. Yılmaz`` never collapse into that key here.

    Requires a multi-token base so surnames alone never merge with full names.
    Known closed-set leftovers are stripped without Zemberek. Extended
    leftovers such as ``'la`` are stripped only when morphology confirms them.
    """
    stripped = strip_inflection_if_safe(value, require_multi_token_base=True)
    normalized = normalize_entity_text(stripped)
    return "".join(normalized.split())


def split_name_suffix(value: str, *, extended: bool = False) -> tuple[str, str]:
    """Return (base, apostrophe+suffix) when a Turkish case suffix is attached.

    Default ``extended=False`` keeps the historical closed set so pre-LLM
    sanitization, which also calls this helper, does not change. Transforms
    that need to *copy* productive leftovers (``'la``) pass ``extended=True``.
    """
    parsed = analyze_inflected_surface(
        value,
        allow_extended_local=extended,
        allow_zemberek=False,
    )
    if parsed.source == "none" or not parsed.apostrophe_suffix:
        return value, ""
    normalized = unicodedata.normalize("NFKC", value).strip()
    mark_match = re.search(r"['’′][A-Za-zçğıöşüâîûÇĞİÖŞÜ]+$", normalized)
    if not mark_match:
        return value, ""
    return normalized[: mark_match.start()], mark_match.group(0)


def assign_resolved_entities(entities: list[EntityCandidate]) -> list[EntityCandidate]:
    """Group spans that share the same normalized surface text.

    ``resolved_entity_id`` is a *normalized_text_group* key for UI collapsing
    and exact-string convenience. It is not document-level person identity,
    coreference, or a claim that two mentions are the same real person.
    """
    buckets: dict[str, str] = {}
    updated: list[EntityCandidate] = []
    for entity in entities:
        role_key = normalize_role_key(entity.role, entity.type)
        role_confident = bool(
            entity.type in ROLE_TYPED
            or (role_key and entity.type in TYPE_TO_ROLE)
        )
        if entity.needs_review:
            role_confident = False
        elif entity.type in ROLE_TYPED:
            role_confident = True
            role_key = role_key or TYPE_TO_ROLE.get(entity.type)

        group = _resolution_group(entity.type)
        identity = (
            person_resolution_base(entity.text)
            if group == "PERSON"
            else normalize_entity_text(entity.text)
        )
        key = f"{group}|{identity}|{role_key or ''}"
        resolved = buckets.get(key)
        if resolved is None:
            digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
            resolved = f"ent_{digest}"
            buckets[key] = resolved

        updated.append(
            entity.model_copy(
                update={
                    "resolved_entity_id": resolved,
                    "role": role_key or entity.role,
                    "role_confident": role_confident,
                    "needs_review": entity.needs_review,
                }
            )
        )
    return updated


def _resolution_group(entity_type: EntityType) -> str:
    if entity_type in {
        EntityType.PERSON_NAME,
        EntityType.FIRST_NAME,
        EntityType.LAST_NAME,
        EntityType.ALIAS,
        EntityType.CLAIMANT_NAME,
        EntityType.DEFENDANT_NAME,
        EntityType.WITNESS_NAME,
        EntityType.EXPERT_NAME,
        EntityType.LAWYER_NAME,
        EntityType.JUDGE_NAME,
    }:
        return "PERSON"
    return entity_type.value
