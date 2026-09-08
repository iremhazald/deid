import { describe, expect, it } from 'vitest'
import type { Entity, PossibleMatch } from './types'
import {
  buildManualMergeTargets,
  mergeEntityIdsForEngine,
  personMergeRoleConflict,
  targetMatchesQuery,
} from './manualMerge'

function entity(partial: Partial<Entity> & Pick<Entity, 'id' | 'type' | 'text'>): Entity {
  return {
    start: partial.start ?? 0,
    end: partial.end ?? partial.text.length,
    page: partial.page ?? 0,
    detector: partial.detector ?? 'TEST',
    method: partial.method ?? 'DETERMINISTIC',
    validated: true,
    recommended: true,
    ...partial,
  }
}

const mehmet = entity({
  id: 'p4a',
  type: 'PERSON_NAME',
  text: 'Mehmet',
  resolved_entity_id: 'kisi-4',
  placeholder_token: '[KİŞİ_4]',
  page: 3,
  start: 10,
})
const mehmetPage2 = entity({
  id: 'p4b',
  type: 'PERSON_NAME',
  text: 'Mehmet',
  resolved_entity_id: 'kisi-4',
  placeholder_token: '[KİŞİ_4]',
  page: 1,
  start: 4,
})
const yilmaz = entity({
  id: 'p1a',
  type: 'PERSON_NAME',
  text: 'Mehmet Yılmaz',
  resolved_entity_id: 'kisi-1',
  placeholder_token: '[KİŞİ_1]',
  start: 0,
})
const yilmazAgain = entity({
  id: 'p1b',
  type: 'PERSON_NAME',
  text: 'Mehmet Yılmaz',
  resolved_entity_id: 'kisi-1',
  placeholder_token: '[KİŞİ_1]',
  start: 80,
  page: 1,
})
const ayse = entity({
  id: 'p2',
  type: 'PERSON_NAME',
  text: 'Ayşe Demir',
  resolved_entity_id: 'kisi-2',
  placeholder_token: '[KİŞİ_2]',
  start: 40,
})
const selin = entity({
  id: 'l1',
  type: 'LAWYER_NAME',
  text: 'Selin Arslan',
  resolved_entity_id: 'lawyer-1',
  placeholder_token: '[AVUKAT_1]',
  start: 60,
})
const ahmet = entity({
  id: 'c1',
  type: 'CLAIMANT_NAME',
  text: 'Ahmet Kaya',
  resolved_entity_id: 'claimant-1',
  placeholder_token: '[DAVACI_1]',
  start: 100,
})
const defendant = entity({
  id: 'd1',
  type: 'DEFENDANT_NAME',
  text: 'Mehmet Yılmaz',
  resolved_entity_id: 'defendant-1',
  placeholder_token: '[DAVALI_1]',
  start: 120,
})
const customMehmet = entity({
  id: 'custom',
  type: 'PERSON_NAME',
  text: 'Mehmet',
  resolved_entity_id: 'kisi-4',
  placeholder_token: '[KİŞİ_4]',
  method: 'MANUAL',
  detector: 'USER_DEFINED_TERM',
  start: 200,
})

const people = [yilmaz, yilmazAgain, ayse, selin, mehmetPage2, mehmet, ahmet]

const matches: PossibleMatch[] = [
  {
    id: 'm1',
    members: [
      {
        canonical_id: 'kisi-4',
        entity_ids: ['p4a', 'p4b'],
        text: 'Mehmet',
        pages: [1, 3],
        placeholder_token: '[KİŞİ_4]',
      },
      {
        canonical_id: 'kisi-1',
        entity_ids: ['p1a', 'p1b'],
        text: 'Mehmet Yılmaz',
        pages: [0, 1],
        placeholder_token: '[KİŞİ_1]',
      },
    ],
  },
]

describe('manual merge targets', () => {
  it('shows the clicked source name and token, not the target list source', () => {
    const { source, others, possible } = buildManualMergeTargets(mehmet, people, matches)
    expect(source?.displayName).toBe('Mehmet')
    expect(source?.placeholderToken).toBe('[KİŞİ_4]')
    expect([...possible, ...others].some((item) => item.canonicalId === 'kisi-4')).toBe(false)
  })

  it('lists each canonical person once, with occurrence counts', () => {
    const { possible } = buildManualMergeTargets(mehmet, people, matches)
    const row = possible.find((item) => item.canonicalId === 'kisi-1')
    expect(row?.displayName).toBe('Mehmet Yılmaz')
    expect(row?.occurrenceCount).toBe(2)
    expect(possible.filter((item) => item.canonicalId === 'kisi-1')).toHaveLength(1)
  })

  it('ranks possible-match candidates before other people', () => {
    const { possible, others } = buildManualMergeTargets(mehmet, people, matches)
    expect(possible.map((item) => item.canonicalId)).toEqual(['kisi-1'])
    expect(others.map((item) => item.canonicalId)).toEqual(['kisi-2', 'lawyer-1', 'claimant-1'])
  })

  it('keeps people who were not suggested searchable and selectable', () => {
    const { others } = buildManualMergeTargets(mehmet, people, matches)
    expect(others.some((item) => item.displayName === 'Ayşe Demir')).toBe(true)
    const filtered = buildManualMergeTargets(mehmet, people, matches, 'ayşe')
    expect(filtered.possible).toEqual([])
    expect(filtered.others.map((item) => item.displayName)).toEqual(['Ayşe Demir'])
  })

  it('filters by surface form, token, and backend role type rather than translated UI copy', () => {
    const lawyer = buildManualMergeTargets(mehmet, people, matches).others.find(
      (item) => item.canonicalId === 'lawyer-1',
    )!
    expect(targetMatchesQuery(lawyer, 'LAWYER')).toBe(true)
    expect(targetMatchesQuery(lawyer, 'avukat')).toBe(true)
    const byYear = buildManualMergeTargets(mehmet, people, matches, 'yıl')
    expect(byYear.possible.map((item) => item.displayName)).toEqual(['Mehmet Yılmaz'])
  })

  it('passes one id from each canonical group to the existing merge engine', () => {
    const { possible } = buildManualMergeTargets(mehmet, people, matches)
    expect(mergeEntityIdsForEngine(mehmet, possible[0])).toEqual(['p4a', 'p1a'])
  })

  it('allows a custom-finding person to be the merge source', () => {
    const { source, possible } = buildManualMergeTargets(customMehmet, [...people, customMehmet], matches)
    expect(source?.entityIds).toContain('custom')
    expect(possible[0]?.canonicalId).toBe('kisi-1')
  })

  it('detects explicit role conflicts without inventing a winner', () => {
    expect(personMergeRoleConflict(['PERSON_NAME'], ['CLAIMANT_NAME'])).toBe(false)
    expect(personMergeRoleConflict(['PERSON_NAME'], ['LAWYER_NAME'])).toBe(false)
    expect(personMergeRoleConflict(['CLAIMANT_NAME'], ['DEFENDANT_NAME'])).toBe(true)
    expect(personMergeRoleConflict([ahmet.type], [defendant.type])).toBe(true)
  })
})
