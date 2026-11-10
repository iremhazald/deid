import { describe, expect, it } from 'vitest'
import en from '../locales/en.json'
import tr from '../locales/tr.json'
import { withoutRemovedFindings, isPersonMergeType } from './findingContextMenu'
import {
  groupCollapsedByFamily,
  placeholderTagPreview,
  placeholderTokensByEntityId,
  previewEntityValue,
  previewTransformLocal,
  userOutputStrategiesFor,
} from './helpers'
import { personMergeRoleConflict } from './manualMerge'
import { presentationGroupForEntityType, presentationTypeOptions } from './presentationTaxonomy'
import type { Entity, TransformCatalog } from './types'

const CLERK_TAG = 'KAT\u0130P'

const catalog: TransformCatalog = {
  strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'PARTIAL_MASK', 'KEEP'],
  categories: [
    {
      category: 'PROSECUTOR_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: true,
    },
    {
      category: 'COURT_CLERK_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: true,
    },
    {
      category: 'JUDGE_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: true,
    },
  ],
  role_labels: { tr: {}, en: {} },
  secure_pdf_strategies: ['REDACT', 'INITIALS', 'PLACEHOLDER', 'PARTIAL_MASK'],
}

function entity(partial: Partial<Entity> & Pick<Entity, 'id' | 'type' | 'text'>): Entity {
  return {
    start: partial.start ?? 0,
    end: partial.end ?? partial.text.length,
    page: partial.page ?? 0,
    detector: 'TEST',
    method: partial.method ?? 'DETERMINISTIC',
    validated: true,
    recommended: true,
    ...partial,
  }
}

describe('prosecutor and court clerk labels', () => {
  it('localizes display names and keeps them out of component code', () => {
    expect(tr.categories.PROSECUTOR_NAME).toBe('Cumhuriyet Savcısı')
    expect(tr.categories.COURT_CLERK_NAME).toBe('Zabıt Kâtibi')
    expect(en.categories.PROSECUTOR_NAME).toBe('Public Prosecutor')
    expect(en.categories.COURT_CLERK_NAME).toBe('Court Clerk')
    expect(presentationTypeOptions()).toEqual(
      expect.arrayContaining(['PROSECUTOR_NAME', 'COURT_CLERK_NAME', 'JUDGE_NAME']),
    )
    expect(presentationGroupForEntityType('PROSECUTOR_NAME')).toBe('person')
    expect(presentationGroupForEntityType('COURT_CLERK_NAME')).toBe('person')
  })

  it('previews role-specific placeholders in the document language', () => {
    expect(placeholderTagPreview('PROSECUTOR_NAME', 'tr')).toBe('[SAVCI_1]')
    expect(placeholderTagPreview('COURT_CLERK_NAME', 'tr')).toBe(`[${CLERK_TAG}_1]`)
    expect(placeholderTagPreview('PROSECUTOR_NAME', 'en')).toBe('[PROSECUTOR_1]')
    expect(placeholderTagPreview('COURT_CLERK_NAME', 'en')).toBe('[COURT_CLERK_1]')
    expect(placeholderTagPreview('JUDGE_NAME', 'tr')).toBe('[HÂKİM_1]')
  })

  it('numbers repeated people and does not merge different people who share a role', () => {
    const entities = [
      entity({ id: 'p1', type: 'PROSECUTOR_NAME', text: 'Enes Demir', start: 0, end: 10 }),
      entity({ id: 'p2', type: 'PERSON_NAME', text: 'Enes Demir', start: 20, end: 30 }),
      entity({ id: 'p3', type: 'PROSECUTOR_NAME', text: 'Kerem Aslan', start: 40, end: 51 }),
      entity({ id: 'c1', type: 'COURT_CLERK_NAME', text: 'Nilay Güleç', start: 60, end: 71 }),
    ]
    const tokens = placeholderTokensByEntityId(entities, 'tr')
    expect(tokens.get('p1')).toBe('[SAVCI_1]')
    expect(tokens.get('p2')).toBe('[SAVCI_1]')
    expect(tokens.get('p3')).toBe('[SAVCI_2]')
    expect(tokens.get('c1')).toBe(`[${CLERK_TAG}_1]`)
    expect(placeholderTokensByEntityId(entities, 'en').get('p1')).toBe('[PROSECUTOR_1]')
    expect(placeholderTokensByEntityId(entities, 'en').get('c1')).toBe('[COURT_CLERK_1]')
  })

  it('falls back when two explicit roles conflict and keeps manual merge available', () => {
    expect(personMergeRoleConflict(['PROSECUTOR_NAME'], ['COURT_CLERK_NAME'])).toBe(true)
    expect(personMergeRoleConflict(['PROSECUTOR_NAME'], ['JUDGE_NAME'])).toBe(true)
    expect(personMergeRoleConflict(['PERSON_NAME'], ['PROSECUTOR_NAME'])).toBe(false)
    expect(personMergeRoleConflict(['CLAIMANT_NAME'], ['DEFENDANT_NAME'])).toBe(true)
    expect(isPersonMergeType('PROSECUTOR_NAME')).toBe(true)
    expect(isPersonMergeType('COURT_CLERK_NAME')).toBe(true)
    const conflicted = [
      entity({ id: 'a', type: 'JUDGE_NAME', text: 'Hasan Işık', start: 0, end: 10 }),
      entity({ id: 'b', type: 'PROSECUTOR_NAME', text: 'Hasan Işık', start: 20, end: 30 }),
    ]
    const tokens = placeholderTokensByEntityId(conflicted, 'tr')
    expect(tokens.get('a')).toBe('[KİŞİ_1]')
    expect(tokens.get('b')).toBe('[KİŞİ_1]')
  })

  it('offers person transformations and previews them for text output', () => {
    for (const type of ['PROSECUTOR_NAME', 'COURT_CLERK_NAME', 'JUDGE_NAME'] as const) {
      expect(userOutputStrategiesFor(type, catalog)).toEqual([
        'REDACT',
        'PLACEHOLDER',
        'INITIALS',
        'KEEP',
      ])
    }
    const text = 'Savcı Enes Demir hazır bulundu.'
    const finding = entity({
      id: 'p1',
      type: 'PROSECUTOR_NAME',
      text: 'Enes Demir',
      start: 6,
      end: 16,
      method: 'MANUAL',
    })
    expect(previewEntityValue('Enes Demir', 'PROSECUTOR_NAME', 'PLACEHOLDER', 'tr')).toBe('[SAVCI_1]')
    expect(previewEntityValue('Nilay Güleç', 'COURT_CLERK_NAME', 'PLACEHOLDER', 'en')).toBe(
      '[COURT_CLERK_1]',
    )
    expect(previewEntityValue('Enes Demir', 'PROSECUTOR_NAME', 'INITIALS', 'tr')).toBe('E.D.')
    expect(previewEntityValue('Enes Demir', 'PROSECUTOR_NAME', 'KEEP', 'tr')).toBe('Enes Demir')
    expect(previewEntityValue('Enes Demir', 'PROSECUTOR_NAME', 'REDACT', 'tr')).toContain('█')
    const replaced = previewTransformLocal(text, [finding], {}, { PROSECUTOR_NAME: 'PLACEHOLDER' }, {}, 'tr')
    expect(replaced).toBe('Savcı [SAVCI_1] hazır bulundu.')
    const redacted = previewTransformLocal(text, [finding], {}, { PROSECUTOR_NAME: 'REDACT' }, {}, 'tr')
    expect(redacted).not.toContain('Enes Demir')
    expect(redacted.startsWith('Savcı ')).toBe(true)
  })

  it('lists the role in review and restores a removed occurrence on undo', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: 'j', type: 'JUDGE_NAME', text: 'Hasan Işık' }),
      entity({ id: 'p', type: 'PROSECUTOR_NAME', text: 'Enes Demir' }),
      entity({ id: 'c', type: 'COURT_CLERK_NAME', text: 'Nilay Güleç' }),
    ])
    expect(groups[0].types.map((item) => item.type)).toEqual([
      'JUDGE_NAME',
      'PROSECUTOR_NAME',
      'COURT_CLERK_NAME',
    ])
    const rows = [
      entity({ id: 'p', type: 'PROSECUTOR_NAME', text: 'Enes Demir', start: 0, end: 10 }),
      entity({ id: 'c', type: 'COURT_CLERK_NAME', text: 'Nilay Güleç', start: 20, end: 31 }),
    ]
    expect(withoutRemovedFindings(rows, ['p']).map((item) => item.id)).toEqual(['c'])
    expect(withoutRemovedFindings(rows, []).map((item) => item.id)).toEqual(['p', 'c'])
  })
})
