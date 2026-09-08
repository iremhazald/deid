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
    stamp_placeholder_tokens,
    tag_locale_for_job,
)
from app.transforms.catalog import recommended_strategy
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
    role_type: EntityType | None = None
    if types <= PERSON_MATCH_TYPES:
        family = resolve_person_family(types)
        if family != "PERSON":
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

    strategy = recommended_strategy(entity_type)
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
                    "recommended": recommended,
                    "recommended_strategy": strategy,
                    "attributes": attributes,
                }
            )
        )
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
