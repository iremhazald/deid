"""User-confirmed PERSON merge and keep-separate persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.models import (
    EntityCandidate,
    EntityType,
    ResolutionState,
    TransformationStrategy,
)
from app.transforms.possible_matches import generate_possible_matches
from app.transforms.tag_registry import (
    bind_canonical_ids,
    matching_bucket,
    normalize_identity_value,
    stamp_placeholder_tokens,
    tag_locale_for_job,
)
from app.transforms.catalog import TYPE_TO_ROLE, recommended_strategy
from app.transforms.tag_taxonomy import (
    PERSON_MATCH_TYPES,
    family_for_type,
    resolve_person_family,
)

if TYPE_CHECKING:
    from app.services.jobs import Job
    from app.transforms.strategies import TransformOp


def _canonical(entity: EntityCandidate) -> str:
    return entity.resolved_entity_id or entity.id


def _pair(left: str, right: str) -> list[str]:
    return sorted((left, right))


def restamp_analysis(
    job: Job,
    *,
    append_new: bool = False,
    placeholder_entities: list[EntityCandidate] | None = None,
):
    if not job.analysis:
        return job.analysis
    locale = tag_locale_for_job(job)
    entities = bind_canonical_ids(list(job.analysis.entities), job.resolution_state)
    entities = stamp_placeholder_tokens(
        entities,
        locale,
        state=job.resolution_state,
        placeholder_entities=placeholder_entities,
        append_new=append_new,
    )
    matches = generate_possible_matches(
        entities, job.analysis.text, job.resolution_state
    )
    job.analysis = job.analysis.model_copy(
        update={
            "entities": entities,
            "possible_matches": matches,
            "resolution_state": job.resolution_state,
        }
    )
    return job.analysis


def placeholder_tokens_for_operations(
    job: Job, operations: list[TransformOp]
) -> dict[str, str]:
    if not job.analysis:
        return {}
    placeholder_ids = {
        operation.entity_id
        for operation in operations
        if operation.entity_id
        and operation.strategy == TransformationStrategy.PLACEHOLDER
    }
    placeholder_entities = [
        entity for entity in job.analysis.entities if entity.id in placeholder_ids
    ]
    stamped = stamp_placeholder_tokens(
        bind_canonical_ids(list(job.analysis.entities), job.resolution_state),
        tag_locale_for_job(job),
        state=job.resolution_state,
        placeholder_entities=placeholder_entities,
    )
    return {
        entity.id: entity.placeholder_token
        for entity in stamped
        if entity.placeholder_token
    }


def _winner_canonical(members: list[EntityCandidate], state: ResolutionState) -> str:
    ids = {_canonical(item) for item in members}
    for order in state.family_order.values():
        for canonical in order:
            if canonical in ids:
                return canonical
    first = min(members, key=lambda item: (item.page, item.start, item.id))
    return _canonical(first)


def _apply_merge_order(
    state: ResolutionState,
    winner_id: str,
    loser_ids: set[str],
    target_family: str,
) -> None:
    member_ids = {winner_id, *loser_ids}
    insert_at: int | None = None
    for family, order in list(state.family_order.items()):
        for index, canonical in enumerate(order):
            if canonical in member_ids and family == target_family:
                insert_at = index if insert_at is None else min(insert_at, index)
        state.family_order[family] = [
            canonical
            for canonical in order
            if canonical not in loser_ids
            and not (canonical == winner_id and family != target_family)
        ]
    target = list(state.family_order.get(target_family) or [])
    if winner_id not in target:
        position = 0 if insert_at is None else min(insert_at, len(target))
        target.insert(position, winner_id)
    state.family_order[target_family] = target
    state.append_ids = [item for item in state.append_ids if item not in loser_ids]


def confirm_entity_merge(job: Job, entity_ids: list[str]):
    if not job.analysis:
        raise ValueError("ANALYSIS_REQUIRED")
    by_id = {item.id: item for item in job.analysis.entities}
    members: list[EntityCandidate] = []
    for entity_id in entity_ids:
        entity = by_id.get(entity_id)
        if entity is None:
            continue
        canonical = _canonical(entity)
        members.extend(
            item for item in job.analysis.entities if _canonical(item) == canonical
        )
    unique: dict[str, EntityCandidate] = {}
    for item in members:
        unique[item.id] = item
    members = list(unique.values())
    if len({_canonical(item) for item in members}) < 2:
        return restamp_analysis(job)

    types = {item.type for item in members}
    selected_types = {by_id[entity_id].type for entity_id in entity_ids if entity_id in by_id}
    role_type: EntityType | None = None
    if types <= PERSON_MATCH_TYPES:
        family = resolve_person_family(types)
        # The two names the user picked decide the tag. A short name and the
        # full name that are both müşteki/sanık stay on that tag.
        if selected_types and selected_types <= PERSON_MATCH_TYPES:
            selected_family = resolve_person_family(selected_types)
            if selected_family != "PERSON":
                family = selected_family
        if family == "COMPLAINANT_ACCUSED":
            role_type = EntityType.COMPLAINANT_ACCUSED_NAME
        elif family != "PERSON":
            from app.transforms.tag_taxonomy import ROLE_SPECIFIC_TYPES

            role_type = next(
                (
                    item.type
                    for item in members
                    if item.type in ROLE_SPECIFIC_TYPES
                    and family_for_type(item.type) == family
                ),
                None,
            )
    elif types <= {EntityType.ADDRESS}:
        family = family_for_type(EntityType.ADDRESS)
    else:
        return restamp_analysis(job)

    winner_id = _winner_canonical(members, job.resolution_state)
    loser_ids = {_canonical(item) for item in members if _canonical(item) != winner_id}
    _apply_merge_order(job.resolution_state, winner_id, loser_ids, family)
    for item in members:
        job.resolution_state.canonical_by_entity_id[item.id] = winner_id

    updated: list[EntityCandidate] = []
    member_ids = {item.id for item in members}
    for item in job.analysis.entities:
        if item.id not in member_ids:
            updated.append(item)
            continue
        changes: dict = {"resolved_entity_id": winner_id}
        if role_type is not None and item.type in PERSON_MATCH_TYPES:
            changes["type"] = role_type
        updated.append(item.model_copy(update=changes))
    job.analysis = job.analysis.model_copy(update={"entities": updated})
    return restamp_analysis(job)


def _identity_key(entity: EntityCandidate) -> tuple[str, str]:
    return matching_bucket(entity.type), normalize_identity_value(entity)


def reclassify_entities(job: Job, entity_ids: list[str], entity_type: EntityType):
    if not job.analysis:
        raise ValueError("ANALYSIS_REQUIRED")
    by_id = {item.id: item for item in job.analysis.entities}
    target_ids: set[str] = set()
    for entity_id in entity_ids:
        entity = by_id.get(entity_id)
        if entity is None:
            continue
        canonical = _canonical(entity)
        for item in job.analysis.entities:
            if item.id == entity_id or _canonical(item) == canonical:
                target_ids.add(item.id)
    if not target_ids:
        return restamp_analysis(job)

    # Same surface is one tag. Move every copy with the selected word, otherwise
    # a leftover span keeps the old family and the label never changes.
    identity_keys = {
        key
        for item in job.analysis.entities
        if item.id in target_ids
        for key in [_identity_key(item)]
        if key[1] and not key[1].startswith("occ|")
    }
    if identity_keys:
        for item in job.analysis.entities:
            if _identity_key(item) in identity_keys:
                target_ids.add(item.id)

    strategy = recommended_strategy(entity_type)
    role = TYPE_TO_ROLE.get(entity_type)
    if entity_type in {EntityType.COMPANY_NAME, EntityType.ORGANISATION}:
        strategy = TransformationStrategy.PLACEHOLDER
    recommended = strategy != TransformationStrategy.KEEP
    updated: list[EntityCandidate] = []
    for item in job.analysis.entities:
        if item.id not in target_ids:
            updated.append(item)
            continue
        attributes = dict(item.attributes or {})
        attributes["reclassified"] = True
        updated.append(
            item.model_copy(
                update={
                    "type": entity_type,
                    "role": role,
                    "role_confident": bool(role),
                    "recommended": recommended,
                    "recommended_strategy": strategy,
                    "attributes": attributes,
                }
            )
        )
    job.analysis = job.analysis.model_copy(update={"entities": updated})
    return restamp_analysis(job)


def _release_overlap(item: EntityCandidate, start: int, end: int, text: str) -> EntityCandidate | None:
    """Pull a neighbour off the range the user just claimed.

    A finding immediately to the left used to block the drag. The dragged
    span keeps the characters, and the neighbour stops at its edge.
    """
    if item.end <= start or item.start >= end:
        return item
    if item.start >= start and item.end <= end:
        return None
    if item.start < start and item.end > end:
        keep_left = (start - item.start) >= (item.end - end)
        if keep_left:
            start_at, end_at = item.start, start
        else:
            start_at, end_at = end, item.end
    elif item.start < start:
        start_at, end_at = item.start, start
    else:
        start_at, end_at = end, item.end
    surface = text[start_at:end_at]
    if start_at == item.start:
        trimmed = surface.rstrip()
        end_at -= len(surface) - len(trimmed)
        surface = trimmed
    else:
        trimmed = surface.lstrip()
        start_at += len(surface) - len(trimmed)
        surface = trimmed
    if not surface or start_at >= end_at:
        return None
    return item.model_copy(update={"text": surface, "start": start_at, "end": end_at})


def edit_entity_span(job: Job, entity_id: str, start: int, end: int):
    """Move one finding onto a user-corrected range of the unchanged analysis text."""
    if not job.analysis:
        raise ValueError("ANALYSIS_REQUIRED")
    text = job.analysis.text
    if start < 0 or end > len(text) or start >= end:
        raise ValueError("ENTITY_SPAN_INVALID")
    surface = text[start:end]
    if not surface.strip():
        raise ValueError("ENTITY_SPAN_INVALID")
    target = next((item for item in job.analysis.entities if item.id == entity_id), None)
    if target is None:
        raise ValueError("ENTITY_NOT_FOUND")
    page = 0
    offset = 0
    for index, page_text in enumerate(job.page_texts or [text]):
        if offset <= start < offset + len(page_text):
            page = index
            break
        offset += len(page_text)
    attributes = dict(target.attributes or {})
    attributes["edited"] = True
    updated = []
    for item in job.analysis.entities:
        if item.id == entity_id:
            updated.append(
                item.model_copy(
                    update={
                        "text": surface,
                        "start": start,
                        "end": end,
                        "page": page,
                        "needs_review": False,
                        "attributes": attributes,
                    }
                )
            )
            continue
        released = _release_overlap(item, start, end, text)
        if released is not None:
            updated.append(released)
    job.analysis = job.analysis.model_copy(update={"entities": updated})
    return restamp_analysis(job)


def reject_entity_match(job: Job, entity_ids: list[str]):
    if not job.analysis:
        raise ValueError("ANALYSIS_REQUIRED")
    by_id = {item.id: item for item in job.analysis.entities}
    canonicals: list[str] = []
    for entity_id in entity_ids:
        entity = by_id.get(entity_id)
        if entity is None:
            continue
        canonicals.append(_canonical(entity))
    unique = list(dict.fromkeys(canonicals))
    if len(unique) >= 2:
        pair = _pair(unique[0], unique[1])
        if pair not in job.resolution_state.rejected_pairs:
            job.resolution_state.rejected_pairs.append(pair)
    return restamp_analysis(job)
