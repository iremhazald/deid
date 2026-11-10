import { describe, expect, it } from 'vitest'
import en from '../locales/en.json'
import tr from '../locales/tr.json'
import { isPersonMergeType } from './findingContextMenu'
import { placeholderTagPreview, previewEntityValue, userOutputStrategiesFor } from './helpers'
import { personMergeRoleConflict } from './manualMerge'
import { presentationGroupForEntityType, presentationTypeOptions } from './presentationTaxonomy'
import type { TransformCatalog } from './types'

const LABELS = [
  ['VICTIM_NAME', 'Mağdur', 'Victim', 'MAGDUR', 'VICTIM'],
  ['COMPLAINANT_NAME', 'Müşteki', 'Complainant', 'MÜŞTEKİ', 'COMPLAINANT'],
  ['SUSPECT_NAME', 'Şüpheli', 'Suspect', 'SUPHELI', 'SUSPECT'],
  ['ACCUSED_NAME', 'Sanık', 'Accused', 'SANIK', 'ACCUSED'],
  ['COMPLAINANT_ACCUSED_NAME', 'Müşteki/Sanık', 'Complainant/Accused', 'MÜŞTEKİ_SANIK', 'COMPLAINANT_ACCUSED'],
  ['INTERVENOR_NAME', 'Katılan', 'Intervening Party', 'KATILAN', 'INTERVENOR'],
  [
    'LEGAL_REPRESENTATIVE_NAME',
    'Kanuni Temsilci / Vasi',
    'Legal Representative / Guardian',
    'KANUNI_TEMSILCI',
    'LEGAL_REPRESENTATIVE',
  ],
  ['MEDIATOR_NAME', 'Arabulucu', 'Mediator', 'ARABULUCU', 'MEDIATOR'],
  ['INTERPRETER_NAME', 'Tercüman', 'Interpreter', 'TERCUMAN', 'INTERPRETER'],
  [
    'ENFORCEMENT_OFFICER_NAME',
    'İcra Müdürü / İcra Görevlisi',
    'Enforcement Officer',
    'ICRA_MEMURU',
    'ENFORCEMENT_OFFICER',
  ],
  ['NOTARY_NAME', 'Noter', 'Notary', 'NOTER', 'NOTARY'],
  ['ARBITRATOR_NAME', 'Hakem', 'Arbitrator', 'HAKEM', 'ARBITRATOR'],
] as const

const catalog: TransformCatalog = {
  strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'PARTIAL_MASK', 'KEEP'],
  categories: LABELS.map(([category]) => ({
    category,
    allowed_strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
    recommended_strategy: 'PLACEHOLDER',
    generalization_options: [],
    supports_role_replacement: true,
  })),
  role_labels: { tr: {}, en: {} },
  secure_pdf_strategies: ['REDACT', 'INITIALS', 'PLACEHOLDER', 'PARTIAL_MASK'],
}

describe('eleven legal role labels', () => {
  it('localizes display names from the locale files', () => {
    const options = presentationTypeOptions()
    for (const [type, turkish, english, trTag, enTag] of LABELS) {
      expect(tr.categories[type]).toBe(turkish)
      expect(en.categories[type]).toBe(english)
      expect(options).toContain(type)
      expect(presentationGroupForEntityType(type)).toBe('person')
      expect(placeholderTagPreview(type, 'tr')).toBe(`[${trTag}_1]`)
      expect(placeholderTagPreview(type, 'en')).toBe(`[${enTag}_1]`)
      expect(isPersonMergeType(type)).toBe(true)
      expect(userOutputStrategiesFor(type, catalog)).not.toContain('PARTIAL_MASK')
      expect(previewEntityValue('Ayşe Yılmaz', type, 'INITIALS', 'tr')).toBe('A.Y.')
      expect(previewEntityValue('Ayşe Yılmaz', type, 'KEEP', 'tr')).toBe('Ayşe Yılmaz')
    }
  })

  it('treats two explicit roles as a merge conflict and a generic person as compatible', () => {
    expect(personMergeRoleConflict(['VICTIM_NAME'], ['COMPLAINANT_NAME'])).toBe(true)
    expect(personMergeRoleConflict(['COMPLAINANT_NAME'], ['ACCUSED_NAME'])).toBe(false)
    expect(personMergeRoleConflict(['COMPLAINANT_ACCUSED_NAME'], ['ACCUSED_NAME'])).toBe(false)
    expect(personMergeRoleConflict(['SUSPECT_NAME'], ['ACCUSED_NAME'])).toBe(true)
    expect(personMergeRoleConflict(['LAWYER_NAME'], ['LEGAL_REPRESENTATIVE_NAME'])).toBe(true)
    expect(personMergeRoleConflict(['EXPERT_NAME'], ['ARBITRATOR_NAME'])).toBe(true)
    expect(personMergeRoleConflict(['PERSON_NAME'], ['VICTIM_NAME'])).toBe(false)
    expect(personMergeRoleConflict(['ACCUSED_NAME'], ['ACCUSED_NAME'])).toBe(false)
  })
})
