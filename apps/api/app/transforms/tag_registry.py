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
    GENERIC_PERSON_TYPES,
    PERSON_MATCH_TYPES,
    ROLE_SPECIFIC_TYPES,
    family_for_type,
    family_label,
    normalize_tag_locale,
    resolve_person_family,
    spec_for,
)

_DUAL_PARTY_ROLES = frozenset({"COMPLAINANT", "ACCUSED", "COMPLAINANT_ACCUSED"})

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


def reading_order_key(entity: EntityCandidate) -> tuple[int, float, float, int, str]:
    """Top to bottom, then left to right, then earlier text.

    ``reading_page`` / ``reading_y`` / ``reading_x`` are the box the reviewer
    sees. PDF points grow downward, so a smaller ``y`` is higher on the page.
    Without a box, page order and the text offset decide.
    """
    attributes = entity.attributes or {}
    page = entity.page
    raw_page = attributes.get("reading_page")
    if isinstance(raw_page, int):
        page = raw_page
    y_value = attributes.get("reading_y")
    x_value = attributes.get("reading_x")
    if isinstance(y_value, (int, float)) and isinstance(x_value, (int, float)):
        line = round(float(y_value) / 3.0) * 3.0
        return (page, line, float(x_value), entity.start, entity.id)
    return (page, float(entity.start), 0.0, entity.start, entity.id)


def remember_reading_anchor(
    entity: EntityCandidate, page: int, y: float, x: float
) -> EntityCandidate:
    attributes = dict(entity.attributes or {})
    attributes["reading_page"] = page
    attributes["reading_y"] = round(float(y), 2)
    attributes["reading_x"] = round(float(x), 2)
    return entity.model_copy(update={"attributes": attributes})


def apply_layout_reading_order(
    entities: list[EntityCandidate],
    pages: list,
    layouts: list[dict] | None,
) -> list[EntityCandidate]:
    """Record each span's line box from the PDF layout, when one exists."""
    if not layouts:
        return entities
    offsets = {
        page.page: page.document_offset
        for page in pages
        if hasattr(page, "page") and hasattr(page, "document_offset")
    }
    runs_by_page = {int(item["page"]): list(item.get("runs") or []) for item in layouts}
    updated: list[EntityCandidate] = []
    for entity in entities:
        runs = runs_by_page.get(entity.page) or []
        local = entity.start - offsets.get(entity.page, 0)
        chosen = next((run for run in runs if run["start"] <= local < run["end"]), None)
        if chosen is None:
            prior = [run for run in runs if run["start"] <= local]
            chosen = max(prior, key=lambda run: run["start"]) if prior else None
        if chosen is None:
            updated.append(entity)
            continue
        updated.append(
            remember_reading_anchor(entity, entity.page, float(chosen["y0"]), float(chosen["x0"]))
        )
    return updated


def apply_span_reading_order(
    entities: list[EntityCandidate], page_spans: list[dict] | None
) -> list[EntityCandidate]:
    """Record the page and corner of the box actually drawn for each finding."""
    anchors: dict[str, tuple[int, float, float]] = {}
    for page in page_spans or []:
        page_num = int(page["page"])
        for span in page.get("spans") or []:
            rectangles = span.get("rectangles") or []
            if not rectangles:
                continue
            anchor = (
                page_num,
                min(float(item["y0"]) for item in rectangles),
                min(float(item["x0"]) for item in rectangles),
            )
            current = anchors.get(span["entity_id"])
            if current is None or anchor < current:
                anchors[span["entity_id"]] = anchor
    if not anchors:
        return entities
    updated: list[EntityCandidate] = []
    for entity in entities:
        anchor = anchors.get(entity.id)
        if anchor is None:
            updated.append(entity)
            continue
        page, y_value, x_value = anchor
        updated.append(remember_reading_anchor(entity, page, y_value, x_value))
    return updated


def _layout_painted_ids(
    entities: list[EntityCandidate], eligible_ids: set[str]
) -> set[str]:
    """Spans the text view actually draws.

    A longer span wins. A name that starts inside it is not a visible tag, so
    it must not occupy [KİŞİ_1].
    """
    ordered = sorted(
        entities,
        key=lambda item: (item.start, item.start - item.end, item.id),
    )
    cursor = -1
    painted: set[str] = set()
    for entity in ordered:
        if entity.start < cursor:
            continue
        if entity.id in eligible_ids:
            painted.add(entity.id)
        if entity.end > cursor:
            cursor = entity.end
    return painted


def _identity_canonical(identity: _Identity) -> str:
    first = min(identity.members, key=reading_order_key)
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

    Display numbers are family-local and follow reading order. A numbered
    category keeps ``[SANIK_1]`` even when the current preview masks that span
    with another method. Persistent identity is ``resolved_entity_id`` /
    canonical group id, never PERSON_N.
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

    appearance: list[tuple[str, tuple[int, float, float, int, str], str]] = []
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
        chosen = _explicit_reclassify_family(identity.members)
        if chosen is not None:
            identity.family = chosen
            identity.conflict = False
        first = min(identity.members, key=reading_order_key)
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
        appearance.append((identity.family, reading_order_key(first), root))

    appearance.sort()
    by_family: dict[str, list[str]] = {}
    root_by_canonical: dict[tuple[str, str], str] = {}
    family_roots: dict[str, list[str]] = {}
    for family, _position, root in appearance:
        canonical = grouped[root].canonical_key
        by_family.setdefault(family, []).append(canonical)
        family_roots.setdefault(family, []).append(root)
        root_by_canonical[(family, canonical)] = root

    if state is not None:
        for family, canonicals in by_family.items():
            previous = set(state.family_order.get(family) or [])
            state.family_order[family] = list(canonicals)
            if not append_new:
                continue
            for canonical in canonicals:
                if canonical in previous or canonical in state.append_ids:
                    continue
                state.append_ids.append(canonical)

    # Spans that are not drawn as a label must not keep [KİŞİ_1]. A removed
    # finding and a name buried inside a longer span are numbered after the
    # labels the reader actually sees, and a numbered category still gets an index.
    all_ids = {item.id for item in entities}
    eligible_ids = {item.id for item in placeholder_entities}
    paint_ids = all_ids if eligible_ids == all_ids else eligible_ids
    painted = _layout_painted_ids(entities, paint_ids)

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
        visible_roots = [
            item_root
            for item_root in ordered_roots
            if any(member.id in painted for member in grouped[item_root].members)
        ]
        hidden_roots = [item_root for item_root in ordered_roots if item_root not in set(visible_roots)]
        for counter, item_root in enumerate([*visible_roots, *hidden_roots], start=1):
            grouped[item_root].number = counter

    entity_identity = {entity.id: forest.find(entity_nodes[entity.id]) for entity in entities}
    return DocumentTagRegistry(
        locale=locale,
        identities=grouped,
        entity_identity=entity_identity,
    )


def _number_unnumbered_courts(
    entities: list[EntityCandidate], locale: str
) -> list[EntityCandidate]:
    """Courts with no chamber number are labeled [MAHKEME_n], not left as prose.

    Numbered chambers stay on the X substitution. Nöbetçi courts without a
    number are not assigned a file, so they keep the generic token.
    """
    from app.detectors.legal.court import court_ordinal, is_duty_court

    label = "MAHKEME" if normalize_tag_locale(locale) == "tr" else "COURT"
    ordered = sorted(
        (
            entity
            for entity in entities
            if entity.type == EntityType.COURT_NAME
            and not court_ordinal(entity.text)
            and not is_duty_court(entity.text)
        ),
        key=reading_order_key,
    )
    tokens = {
        entity.id: f"[{label}_{index}]" for index, entity in enumerate(ordered, start=1)
    }
    if not tokens:
        return entities
    return [
        entity.model_copy(update={"placeholder_token": tokens[entity.id]})
        if entity.id in tokens
        else entity
        for entity in entities
    ]


def promote_complainant_accused(entities: list[EntityCandidate]) -> list[EntityCandidate]:
    """Retype a name that is both müşteki and sanık as Müşteki/Sanık.

    Generic person spans of that same identity follow the combined category.
    Any other role on the name leaves the members unchanged.
    """
    forest = _UnionFind()
    nodes: dict[str, str] = {}
    for entity in entities:
        if entity.type not in PERSON_MATCH_TYPES:
            continue
        node = f"e|{entity.id}"
        forest.add(node)
        forest.union(node, _surface_node(entity))
        resolved = _resolved_node(entity)
        if resolved:
            forest.union(node, resolved)
        alias = _alias_surface_node(entity)
        if alias:
            forest.union(node, alias)
        nodes[entity.id] = node

    grouped: dict[str, list[EntityCandidate]] = {}
    for entity in entities:
        node = nodes.get(entity.id)
        if node is None:
            continue
        grouped.setdefault(forest.find(node), []).append(entity)

    retype: set[str] = set()
    for members in grouped.values():
        if any((member.attributes or {}).get("reclassified") for member in members):
            continue
        roles = {
            family_for_type(member.type)
            for member in members
            if member.type in ROLE_SPECIFIC_TYPES
        }
        both_sides = "COMPLAINANT" in roles and "ACCUSED" in roles
        already_combined = "COMPLAINANT_ACCUSED" in roles and roles != {"COMPLAINANT_ACCUSED"}
        if not roles <= _DUAL_PARTY_ROLES or not (both_sides or already_combined):
            continue
        for member in members:
            if member.type in GENERIC_PERSON_TYPES or member.type in {
                EntityType.COMPLAINANT_NAME,
                EntityType.ACCUSED_NAME,
            }:
                retype.add(member.id)
    if not retype:
        return entities
    return [
        entity.model_copy(
            update={"type": EntityType.COMPLAINANT_ACCUSED_NAME, "role": "COMPLAINANT_ACCUSED"}
        )
        if entity.id in retype
        else entity
        for entity in entities
    ]


def _explicit_reclassify_family(members: list[EntityCandidate]) -> str | None:
    """A category the user just picked owns the tag, even if another span remains."""
    families = {
        family_for_type(member.type)
        for member in members
        if (member.attributes or {}).get("reclassified")
    }
    if len(families) == 1:
        return next(iter(families))
    return None


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
    entities = promote_complainant_accused(entities)
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
    return _number_unnumbered_courts(stamped, locale)


def _fallback_token(entity: EntityCandidate, locale: str) -> str:
    spec = spec_for(entity.type)
    label = spec.labels_tr if normalize_tag_locale(locale) == "tr" else spec.labels_en
    if spec.numbered:
        return f"[{label}_1]"
    return f"[{label}]"
