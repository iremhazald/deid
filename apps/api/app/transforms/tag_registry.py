"""Document-scoped PLACEHOLDER identity registry.

This is not coreference. Matching is exact normalized surface only, plus
already-trusted ``resolved_entity_id`` links from the detector pipeline.
Partial names, surnames, and fuzzy variants stay separate tags.

Numbering key for a numbered family:

    (family, canonical_entity_key) -> 1, 2, 3...

``canonical_entity_key`` is ``normalize_identity_value`` after conservative
exact-match grouping. Counters are family-local. Generic families stay
unnumbered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.models import EntityCandidate, EntityType, ResolutionState
from app.language.resolve import normalize_requested_language
from app.transforms.resolution import normalize_entity_text, person_resolution_base
from app.transforms.tag_taxonomy import (
    GENERIC_PERSON_FAMILY,
    PERSON_MATCH_TYPES,
    family_for_type,
    family_label,
    normalize_tag_locale,
    resolve_person_family,
    spec_for,
)

_ALNUM = re.compile(r"[\s\-_.]+")
_DIGITS = re.compile(r"\D+")


@dataclass
class _Identity:
    key: str
    members: list[EntityCandidate] = field(default_factory=list)
    family: str = GENERIC_PERSON_FAMILY
    canonical_key: str = ""
    number: int | None = None
    conflict: bool = False


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, node: str) -> None:
        self.parent.setdefault(node, node)

    def find(self, node: str) -> str:
        self.add(node)
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, left: str, right: str) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left == root_right:
            return
        if root_left < root_right:
            self.parent[root_right] = root_left
        else:
            self.parent[root_left] = root_right


def matching_bucket(entity_type: EntityType) -> str:
    if entity_type in PERSON_MATCH_TYPES:
        return "PERSON"
    return entity_type.value


def normalize_identity_value(entity: EntityCandidate) -> str:
    """Conservative exact-value key. Never a nickname or partial-name merge."""
    spec = spec_for(entity.type)
    text = entity.text
    if entity.type in PERSON_MATCH_TYPES:
        return person_resolution_base(text)
    if entity.type in {
        EntityType.IBAN,
        EntityType.BANK_ACCOUNT,
        EntityType.CREDIT_CARD,
        EntityType.NATIONAL_ID,
        EntityType.PASSPORT_NUMBER,
        EntityType.TAX_IDENTIFIER,
        EntityType.EMPLOYEE_ID,
        EntityType.CUSTOMER_ID,
        EntityType.OTHER_IDENTIFIER,
        EntityType.PROFESSIONAL_ID,
        EntityType.VEHICLE_PLATE,
        EntityType.CASE_NUMBER,
        EntityType.FILE_NUMBER,
        EntityType.DECISION_NUMBER,
    }:
        compact = _ALNUM.sub("", text).upper()
        return compact or normalize_entity_text(text)
    if entity.type == EntityType.PHONE_NUMBER:
        digits = _DIGITS.sub("", text)
        return digits or normalize_entity_text(text)
    if entity.type == EntityType.EMAIL:
        return normalize_entity_text(text).replace(" ", "")
    if not spec.reuse:
        return f"occ|{entity.id}"
    return normalize_entity_text(text)


def _surface_node(entity: EntityCandidate) -> str:
    bucket = matching_bucket(entity.type)
    value = normalize_identity_value(entity)
    return f"s|{bucket}|{value}"


def _resolved_node(entity: EntityCandidate) -> str | None:
    if not entity.resolved_entity_id:
        return None
    return f"r|{matching_bucket(entity.type)}|{entity.resolved_entity_id}"


def _alias_surface_node(entity: EntityCandidate) -> str | None:
    """Use detector alias metadata only when it is an exact normalized full match."""
    attrs = entity.attributes or {}
    seed = attrs.get("seed_text")
    if not isinstance(seed, str) or not seed.strip():
        return None
    if entity.type not in PERSON_MATCH_TYPES:
        return None
    if person_resolution_base(entity.text) != person_resolution_base(seed):
        return None
    return f"s|PERSON|{person_resolution_base(seed)}"


def tag_locale_for_document(
    *,
    resolved_document_language: str | None = None,
    requested_document_language: str | None = None,
    job_locale: str | None = None,
) -> str:
    """Tag language follows the user-selected document language.

    Never UI locale. Explicit ``tr`` / ``en`` win. Legacy jobs without a
    persisted document language keep the historical ``job.locale`` default
    of ``tr`` — they do not fall back to the interface language.
    """
    for raw in (resolved_document_language, requested_document_language, job_locale):
        if not raw:
            continue
        normalized = normalize_requested_language(raw)
        if normalized in {"tr", "en"}:
            return normalized
        folded = raw.strip().lower()
        if folded.startswith("en"):
            return "en"
        if folded.startswith("tr"):
            return "tr"
    return "tr"


def tag_locale_for_job(job: object) -> str:
    analysis = getattr(job, "analysis", None)
    resolved = getattr(analysis, "resolved_document_language", None) if analysis else None
    requested = getattr(job, "requested_document_language", None)
    if requested is None and analysis is not None:
        requested = getattr(analysis, "requested_document_language", None)
    return tag_locale_for_document(
        resolved_document_language=resolved,
        requested_document_language=requested,
        job_locale=getattr(job, "locale", None),
    )


@dataclass
class DocumentTagRegistry:
    """Job/document scoped map from entity id → numbered tag token."""

    locale: str
    identities: dict[str, _Identity] = field(default_factory=dict)
    entity_identity: dict[str, str] = field(default_factory=dict)

    def token_for(self, entity: EntityCandidate, *, prefer_stamped: bool = True) -> str:
        if prefer_stamped:
            stamped = getattr(entity, "placeholder_token", None)
            if isinstance(stamped, str) and stamped.strip():
                return stamped.strip()
        identity = self.identities.get(self.entity_identity.get(entity.id, ""))
        if identity is None:
            return _fallback_token(entity, self.locale)
        label = family_label(identity.family, self.locale)
        if identity.number is None:
            return f"[{label}]"
        return f"[{label}_{identity.number}]"

    def placeholder_key(self, entity: EntityCandidate) -> str:
        return self.entity_identity.get(entity.id) or entity.id

    def family_for(self, entity: EntityCandidate) -> str:
        identity = self.identities.get(self.entity_identity.get(entity.id, ""))
        if identity is None:
            return family_for_type(entity.type)
        return identity.family

    def number_for(self, entity: EntityCandidate) -> int | None:
        identity = self.identities.get(self.entity_identity.get(entity.id, ""))
        if identity is None:
            return None
        return identity.number


def bind_canonical_ids(
    entities: list[EntityCandidate],
    state: ResolutionState | None,
) -> list[EntityCandidate]:
    """Overlay user-confirmed canonical ids without changing surface grouping."""
    if state is None or not state.canonical_by_entity_id:
        return entities
    bound: list[EntityCandidate] = []
    for entity in entities:
        canonical = state.canonical_by_entity_id.get(entity.id)
        if canonical and canonical != entity.resolved_entity_id:
            bound.append(entity.model_copy(update={"resolved_entity_id": canonical}))
        else:
            bound.append(entity)
    return bound


def stable_canonical_id(entity: EntityCandidate) -> str:
    return entity.resolved_entity_id or entity.id


def _identity_canonical(identity: _Identity) -> str:
    first = min(identity.members, key=lambda item: (item.page, item.start, item.id))
    return first.resolved_entity_id or first.id


def build_document_tag_registry(
    entities: list[EntityCandidate],
    placeholder_entities: list[EntityCandidate],
    locale: str,
    *,
    state: ResolutionState | None = None,
    append_new: bool = False,
) -> DocumentTagRegistry:
    """Build the document registry.

    Display numbers are family-local and contiguous among identities that still
    have at least one active PLACEHOLDER occurrence. Persistent identity is
    ``resolved_entity_id`` / canonical group id, never PERSON_N.
    """
    locale = normalize_tag_locale(locale)
    entities = bind_canonical_ids(entities, state)
    forest = _UnionFind()
    entity_nodes: dict[str, str] = {}
    for entity in entities:
        node = f"e|{entity.id}"
        forest.add(node)
        forest.union(node, _surface_node(entity))
        resolved = _resolved_node(entity)
        if resolved:
            forest.union(node, resolved)
        alias = _alias_surface_node(entity)
        if alias:
            forest.union(node, alias)
        entity_nodes[entity.id] = node

    grouped: dict[str, _Identity] = {}
    for entity in entities:
        root = forest.find(entity_nodes[entity.id])
        identity = grouped.get(root)
        if identity is None:
            identity = _Identity(key=root)
            grouped[root] = identity
        identity.members.append(entity)

    appearance: list[tuple[str, int, int, str, str]] = []
    for root, identity in grouped.items():
        types = {member.type for member in identity.members}
        if any(member.type in PERSON_MATCH_TYPES for member in identity.members):
            identity.family = resolve_person_family(types)
            identity.conflict = (
                len(
                    {
                        family_for_type(item)
                        for item in types
                        if item in PERSON_MATCH_TYPES
                        and family_for_type(item) != GENERIC_PERSON_FAMILY
                    }
                )
                > 1
            )
        else:
            identity.family = family_for_type(identity.members[0].type)
        first = min(identity.members, key=lambda item: (item.page, item.start, item.id))
        identity.canonical_key = first.resolved_entity_id or first.id
        spec = spec_for(
            next(
                (
                    member.type
                    for member in identity.members
                    if family_for_type(member.type) == identity.family
                ),
                identity.members[0].type,
            )
        )
        if not spec.numbered:
            identity.number = None
            continue
        appearance.append((identity.family, first.page, first.start, first.id, root))

    appearance.sort()
    by_family: dict[str, list[str]] = {}
    root_by_canonical: dict[tuple[str, str], str] = {}
    family_roots: dict[str, list[str]] = {}
    for family, _page, _start, _eid, root in appearance:
        canonical = grouped[root].canonical_key
        by_family.setdefault(family, []).append(canonical)
        family_roots.setdefault(family, []).append(root)
        root_by_canonical[(family, canonical)] = root

    append_ids = set(state.append_ids) if state else set()
    if state is not None:
        for family, canonicals in by_family.items():
            existing = list(state.family_order.get(family) or [])
            known = set(existing)
            if not existing:
                state.family_order[family] = list(canonicals)
                continue
            for canonical in canonicals:
                if canonical in known:
                    continue
                existing.append(canonical)
                known.add(canonical)
                if append_new or canonical in append_ids:
                    if canonical not in state.append_ids:
                        state.append_ids.append(canonical)
            state.family_order[family] = existing

    restrict_active = bool(placeholder_entities) and set(item.id for item in placeholder_entities) != {
        item.id for item in entities
    }
    active_ids = {item.id for item in placeholder_entities} if placeholder_entities else set()

    def _is_active(root: str) -> bool:
        if not restrict_active:
            return True
        return any(member.id in active_ids for member in grouped[root].members)

    for family, roots in family_roots.items():
        order_ids = (state.family_order.get(family) if state else None) or by_family.get(family, [])
        ordered_roots: list[str] = []
        seen_roots: set[str] = set()
        for canonical in order_ids:
            item_root = root_by_canonical.get((family, canonical))
            if item_root is None or item_root in seen_roots:
                continue
            seen_roots.add(item_root)
            ordered_roots.append(item_root)
        for item_root in roots:
            if item_root not in seen_roots:
                ordered_roots.append(item_root)
                seen_roots.add(item_root)
        counter = 0
        for item_root in ordered_roots:
            if not _is_active(item_root):
                grouped[item_root].number = None
                continue
            counter += 1
            grouped[item_root].number = counter

    entity_identity = {entity.id: forest.find(entity_nodes[entity.id]) for entity in entities}
    return DocumentTagRegistry(
        locale=locale,
        identities=grouped,
        entity_identity=entity_identity,
    )


def stamp_placeholder_tokens(
    entities: list[EntityCandidate],
    locale: str,
    *,
    state: ResolutionState | None = None,
    placeholder_entities: list[EntityCandidate] | None = None,
    append_new: bool = False,
) -> list[EntityCandidate]:
    """Attach the authoritative PLACEHOLDER token to every entity."""
    entities = bind_canonical_ids(entities, state)
    active = placeholder_entities if placeholder_entities is not None else entities
    registry = build_document_tag_registry(
        entities,
        active,
        locale,
        state=state,
        append_new=append_new,
    )
    stamped: list[EntityCandidate] = []
    for entity in entities:
        stamped.append(
            entity.model_copy(
                update={"placeholder_token": registry.token_for(entity, prefer_stamped=False)}
            )
        )
    return stamped


def _fallback_token(entity: EntityCandidate, locale: str) -> str:
    spec = spec_for(entity.type)
    label = spec.labels_tr if normalize_tag_locale(locale) == "tr" else spec.labels_en
    if spec.numbered:
        return f"[{label}_1]"
    return f"[{label}]"
