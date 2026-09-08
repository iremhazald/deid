import { describe, expect, it } from 'vitest'
import {
  groupCollapsedByFamily,
  placeholderTagPreview,
} from './helpers'
import {
  backendTypesForSubcategory,
  presentationGroupForEntityType,
  presentationGroupOrder,
  shouldFlattenPresentationGroup,
  subcategoryForEntityType,
  subcategoryOrder,
} from './presentationTaxonomy'
import type { Entity } from './types'

function entity(partial: Partial<Entity> & Pick<Entity, 'id' | 'type'>): Entity {
  return {
    text: partial.text ?? partial.id,
    start: partial.start ?? 0,
    end: partial.end ?? (partial.text ?? partial.id).length,
    page: partial.page ?? 0,
    detector: 'TEST',
    method: 'DETERMINISTIC',
    validated: true,
    recommended: true,
    ...partial,
  }
}

describe('presentation taxonomy mapping', () => {
  it('maps legal-role names to the person group, not court', () => {
    expect(presentationGroupForEntityType('PERSON_NAME')).toBe('person')
    expect(presentationGroupForEntityType('LAWYER_NAME')).toBe('person')
    expect(presentationGroupForEntityType('JUDGE_NAME')).toBe('person')
    expect(presentationGroupForEntityType('CLAIMANT_NAME')).toBe('person')
    expect(presentationGroupForEntityType('COURT_NAME')).toBe('court')
    expect(presentationGroupForEntityType('PROFESSIONAL_ID')).toBe('court')
  })

  it('collapses first/last/alias into the generic person subcategory', () => {
    expect(subcategoryForEntityType('PERSON_NAME')).toBe('PERSON_NAME')
    expect(subcategoryForEntityType('FIRST_NAME')).toBe('PERSON_NAME')
    expect(subcategoryForEntityType('LAST_NAME')).toBe('PERSON_NAME')
    expect(subcategoryForEntityType('ALIAS')).toBe('PERSON_NAME')
    expect(backendTypesForSubcategory('PERSON_NAME')).toEqual([
      'PERSON_NAME',
      'FIRST_NAME',
      'LAST_NAME',
      'ALIAS',
    ])
  })

  it('keeps a stable semantic group order', () => {
    expect(
      ['cyber', 'person', 'court', 'identity'].sort(
        (a, b) => presentationGroupOrder(a) - presentationGroupOrder(b),
      ),
    ).toEqual(['person', 'identity', 'court', 'cyber'])
  })

  it('orders person roles generically first, then legal roles', () => {
    expect(subcategoryOrder('PERSON_NAME')).toBeLessThan(subcategoryOrder('CLAIMANT_NAME'))
    expect(subcategoryOrder('CLAIMANT_NAME')).toBeLessThan(subcategoryOrder('LAWYER_NAME'))
    expect(subcategoryOrder('LAWYER_NAME')).toBeLessThan(subcategoryOrder('JUDGE_NAME'))
    expect(subcategoryOrder('WITNESS_NAME')).toBeLessThan(subcategoryOrder('EXPERT_NAME'))
  })

  it('flattens structurally single court and a lone generic person subtype', () => {
    expect(shouldFlattenPresentationGroup('court', ['COURT_NAME'])).toBe(true)
    expect(shouldFlattenPresentationGroup('person', ['PERSON_NAME'])).toBe(true)
    expect(shouldFlattenPresentationGroup('identity', ['NATIONAL_ID'])).toBe(true)
  })

  it('keeps a lone person-role subcategory nested so its label stays visible', () => {
    expect(shouldFlattenPresentationGroup('person', ['LAWYER_NAME'])).toBe(false)
    expect(
      shouldFlattenPresentationGroup('person', ['PERSON_NAME', 'LAWYER_NAME']),
    ).toBe(false)
  })
})

describe('presentation taxonomy grouping', () => {
  it('A. shows detected person roles as subcategories and hides zero-count roles', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: 'p', type: 'PERSON_NAME', text: 'Ali Kaya' }),
      entity({ id: 'c', type: 'CLAIMANT_NAME', text: 'Ayşe Demir' }),
      entity({ id: 'l', type: 'LAWYER_NAME', text: 'Hasan Koç' }),
      entity({ id: 'j', type: 'JUDGE_NAME', text: 'Ayşe Yılmaz' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('person')
    expect(groups[0].flattened).toBe(false)
    expect(groups[0].types.map((item) => item.type)).toEqual([
      'PERSON_NAME',
      'CLAIMANT_NAME',
      'LAWYER_NAME',
      'JUDGE_NAME',
    ])
    expect(groups[0].types.map((item) => item.type)).not.toContain('DEFENDANT_NAME')
    expect(groups[0].types.map((item) => item.type)).not.toContain('WITNESS_NAME')
    expect(groups[0].types.map((item) => item.type)).not.toContain('EXPERT_NAME')
  })

  it('B. folds FIRST_NAME / LAST_NAME / ALIAS into generic person names', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'PERSON_NAME', text: 'Ali Kaya' }),
      entity({ id: '2', type: 'FIRST_NAME', text: 'Ayşe' }),
      entity({ id: '3', type: 'LAST_NAME', text: 'Demir' }),
      entity({ id: '4', type: 'ALIAS', text: 'A. Demir' }),
    ])
    expect(groups[0].types.map((item) => item.type)).toEqual(['PERSON_NAME'])
    expect(groups[0].types[0].backendTypes.sort()).toEqual([
      'ALIAS',
      'FIRST_NAME',
      'LAST_NAME',
      'PERSON_NAME',
    ])
  })

  it('C. keeps lawyer placeholder families independent of the person presentation group', () => {
    expect(presentationGroupForEntityType('LAWYER_NAME')).toBe('person')
    expect(placeholderTagPreview('LAWYER_NAME', 'tr')).toBe('[AVUKAT_1]')
    expect(placeholderTagPreview('LAWYER_NAME', 'en')).toBe('[LAWYER_1]')
  })

  it('D. renders court information without a nested duplicate subtype', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'COURT_NAME', text: 'Ankara 1. Asliye' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('court')
    expect(groups[0].flattened).toBe(true)
    expect(groups[0].types).toHaveLength(1)
    expect(groups[0].types[0].type).toBe('COURT_NAME')
  })

  it('nests registry numbers under court information with court names', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'COURT_NAME', text: 'Ankara 1. Asliye' }),
      entity({ id: '2', type: 'PROFESSIONAL_ID', text: '37690' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('court')
    expect(groups[0].flattened).toBe(false)
    expect(groups[0].types.map((item) => item.type)).toEqual([
      'COURT_NAME',
      'PROFESSIONAL_ID',
    ])
  })

  it('E. splits detected identity subtypes', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'NATIONAL_ID', text: '12345678901' }),
      entity({ id: '2', type: 'PASSPORT_NUMBER', text: 'U12345678' }),
      entity({ id: '3', type: 'DATE_OF_BIRTH', text: '01.01.1990' }),
    ])
    expect(groups[0].id).toBe('identity')
    expect(groups[0].flattened).toBe(false)
    expect(groups[0].types.map((item) => item.type)).toEqual([
      'NATIONAL_ID',
      'PASSPORT_NUMBER',
      'DATE_OF_BIRTH',
    ])
  })

  it('F. does not render absent subtypes', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'PERSON_NAME', text: 'Ali' }),
      entity({ id: '2', type: 'LAWYER_NAME', text: 'Hasan' }),
    ])
    const types = groups[0].types.map((item) => item.type)
    expect(types).toEqual(['PERSON_NAME', 'LAWYER_NAME'])
    expect(types).not.toContain('WITNESS_NAME')
    expect(types).not.toContain('EXPERT_NAME')
  })

  it('L. counts parent as the sum of subcategory mentions without double-counting a finding', () => {
    const groups = groupCollapsedByFamily([
      entity({
        id: '1',
        type: 'PERSON_NAME',
        text: 'John Brown',
        resolved_entity_id: 'p',
        start: 0,
        end: 10,
      }),
      entity({
        id: '2',
        type: 'PERSON_NAME',
        text: 'John Brown',
        resolved_entity_id: 'p',
        start: 20,
        end: 30,
      }),
      entity({ id: '3', type: 'LAWYER_NAME', text: 'Hasan Koç' }),
    ])
    expect(groups[0].types[0].mentionCount).toBe(2)
    expect(groups[0].types[1].mentionCount).toBe(1)
    expect(groups[0].mentionCount).toBe(3)
  })
})
