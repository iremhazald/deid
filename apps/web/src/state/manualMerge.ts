import { relatedEntityIds } from './helpers'
import { isAddressMergeType, isPersonMergeType, PERSON_MERGE_TYPES } from './findingContextMenu'
import type { Entity, PossibleMatch } from './types'

const ROLE_FAMILIES: Record<string, string> = {
  CLAIMANT_NAME: 'CLAIMANT',
  DEFENDANT_NAME: 'DEFENDANT',
  LAWYER_NAME: 'LAWYER',
  JUDGE_NAME: 'JUDGE',
  WITNESS_NAME: 'WITNESS',
  EXPERT_NAME: 'EXPERT',
}

export type ManualMergeTarget = {
  canonicalId: string
  representativeId: string
  entityIds: string[]
  displayName: string
  placeholderToken: string | null
  occurrenceCount: number
  types: string[]
  surfaceForms: string[]
  possibleMatch: boolean
}

export function canonicalKey(entity: Entity): string {
  return entity.resolved_entity_id ?? entity.id
}

function foldSearch(value: string): string {
  return value
    .normalize('NFKC')
    .replace(/İ/g, 'i')
    .replace(/I/g, 'ı')
    .toLocaleLowerCase('tr-TR')
}

function longestText(members: Entity[]): string {
  return [...members].sort((left, right) => right.text.length - left.text.length || left.start - right.start)[0]
    ?.text ?? members[0]?.text ?? ''
}

export function personCanonicalGroups(
  entities: Entity[],
  allow: (type: string) => boolean = isPersonMergeType,
): ManualMergeTarget[] {
  const people = entities.filter((entity) => allow(entity.type))
  const seen = new Set<string>()
  const groups: ManualMergeTarget[] = []
  for (const entity of people) {
    if (seen.has(entity.id)) continue
    const ids = relatedEntityIds(entity.id, people)
    for (const id of ids) seen.add(id)
    const members = ids
      .map((id) => people.find((item) => item.id === id))
      .filter((item): item is Entity => Boolean(item))
    if (members.length === 0) continue
    const representative = [...members].sort(
      (left, right) => left.page - right.page || left.start - right.start || left.id.localeCompare(right.id),
    )[0]
    groups.push({
      canonicalId: canonicalKey(representative),
      representativeId: representative.id,
      entityIds: members.map((item) => item.id),
      displayName: longestText(members),
      placeholderToken: representative.placeholder_token ?? members.find((item) => item.placeholder_token)?.placeholder_token ?? null,
      occurrenceCount: members.length,
      types: [...new Set(members.map((item) => item.type))],
      surfaceForms: [...new Set(members.map((item) => item.text))],
      possibleMatch: false,
    })
  }
  return groups
}

function memberMatchesGroup(member: { canonical_id: string; entity_ids: string[] }, group: ManualMergeTarget): boolean {
  if (member.canonical_id === group.canonicalId) return true
  return member.entity_ids.some((id) => group.entityIds.includes(id))
}

function isPossibleMatchPair(
  source: ManualMergeTarget,
  target: ManualMergeTarget,
  matches: PossibleMatch[],
): boolean {
  return matches.some((match) => {
    const sourceIn = match.members.some((member) => memberMatchesGroup(member, source))
    const targetIn = match.members.some((member) => memberMatchesGroup(member, target))
    return sourceIn && targetIn
  })
}

export function targetSearchHaystack(target: ManualMergeTarget): string {
  const families = target.types.map((type) => ROLE_FAMILIES[type] ?? 'PERSON')
  return foldSearch(
    [
      target.displayName,
      ...target.surfaceForms,
      target.placeholderToken ?? '',
      ...target.types,
      ...families,
    ].join(' '),
  )
}

export function targetMatchesQuery(target: ManualMergeTarget, query: string): boolean {
  const needle = foldSearch(query.trim())
  if (!needle) return true
  return targetSearchHaystack(target).includes(needle)
}

export function buildManualMergeTargets(
  sourceEntity: Entity,
  entities: Entity[],
  possibleMatches: PossibleMatch[] = [],
  query = '',
): { source: ManualMergeTarget | null; possible: ManualMergeTarget[]; others: ManualMergeTarget[] } {
  if (!isPersonMergeType(sourceEntity.type) && !isAddressMergeType(sourceEntity.type)) {
    return { source: null, possible: [], others: [] }
  }
  const groups = personCanonicalGroups(
    entities,
    isAddressMergeType(sourceEntity.type) ? isAddressMergeType : isPersonMergeType,
  )
  const sourceKey = canonicalKey(sourceEntity)
  const source =
    groups.find((group) => group.entityIds.includes(sourceEntity.id) || group.canonicalId === sourceKey) ?? null
  const candidates = groups.filter((group) => group.canonicalId !== source?.canonicalId)
  const ranked = candidates.map((group) => ({
    ...group,
    possibleMatch: source ? isPossibleMatchPair(source, group, possibleMatches) : false,
  }))
  const filtered = ranked.filter((group) => targetMatchesQuery(group, query))
  return {
    source: source
      ? {
          ...source,
          displayName: sourceEntity.text,
          placeholderToken: sourceEntity.placeholder_token ?? source.placeholderToken,
        }
      : null,
    possible: filtered.filter((group) => group.possibleMatch),
    others: filtered.filter((group) => !group.possibleMatch),
  }
}

export function explicitRoleFamilies(types: Iterable<string>): string[] {
  return [...new Set([...types].map((type) => ROLE_FAMILIES[type]).filter((family): family is string => Boolean(family)))]
}

/** Mirrors backend resolve_person_family: two distinct explicit roles conflict. */
export function personMergeRoleConflict(sourceTypes: Iterable<string>, targetTypes: Iterable<string>): boolean {
  const roles = new Set([...explicitRoleFamilies(sourceTypes), ...explicitRoleFamilies(targetTypes)])
  return roles.size > 1
}

export function mergeEntityIdsForEngine(source: Entity, target: ManualMergeTarget): string[] {
  return [source.id, target.representativeId]
}

export { PERSON_MERGE_TYPES }
