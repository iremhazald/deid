import { describe, expect, it } from 'vitest'
import en from '../../locales/en.json'
import tr from '../../locales/tr.json'
import {
  DEMO_SCRIPTS,
  DEMO_STATIC_ELAPSED,
  DEMO_TOTAL,
  demoEntityMethod,
  demoEntityReplacement,
  demoIsComplete,
  demoIsTransforming,
  demoMethodSet,
  demoScrollAnchor,
  demoStage,
  demoTextState,
} from './demoScript'
import { EN_DEMO_DETECTIONS } from './demoScript.en.ts'
import { TR_DEMO_DETECTIONS } from './demoScript.tr.ts'

const MASKING_METHODS = ['redact', 'placeholder', 'initials', 'partial'] as const

describe('landing demo sequence', () => {
  it('separates detection from transformation', () => {
    expect(demoIsTransforming(1200)).toBe(false)
    expect(demoStage(1200)).toEqual({ kind: 'detection' })
    expect(demoIsTransforming(1900)).toBe(true)
    expect(demoStage(1900)).toEqual({ kind: 'capability' })
  })

  it('introduces exactly four transformation methods in order', () => {
    expect(demoStage(2200)).toMatchObject({ kind: 'method', method: 'redact', index: 1 })
    expect(demoStage(3400)).toMatchObject({ kind: 'method', method: 'placeholder', index: 2 })
    expect(demoStage(4700)).toMatchObject({ kind: 'method', method: 'initials', index: 3 })
    expect(demoStage(6000)).toMatchObject({ kind: 'method', method: 'partial', index: 4 })
  })

  it('does not treat keep, role, or generalization as demo methods', () => {
    expect(demoStage(3100)).toMatchObject({ kind: 'method', method: 'redact' })
    expect(demoStage(4000)).toMatchObject({ kind: 'method', method: 'placeholder' })
    expect(demoStage(6600)).toEqual({ kind: 'complete' })
    expect(demoEntityMethod('tr', 'bodyAccusedOne')).toBeUndefined()
    expect(demoEntityMethod('tr', 'partyAddress')).toBeUndefined()
  })

  it('keeps completed transformations visible in the final state', () => {
    expect(demoIsComplete(DEMO_STATIC_ELAPSED)).toBe(true)
    expect(demoStage(DEMO_STATIC_ELAPSED)).toEqual({ kind: 'complete' })
    expect(demoTextState('tr', 'partyId', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('tr', 'bodyWitnessOne', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('tr', 'bodyCounselTwo', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('tr', 'partyPhone', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('tr', 'bodyAccusedOne', DEMO_STATIC_ELAPSED)).toBe('idle')
    expect(demoTextState('tr', 'partyAddress', DEMO_STATIC_ELAPSED)).toBe('idle')
  })

  it('uses the intended synthetic replacements', () => {
    expect(demoEntityReplacement('tr', 'partyId')).toBe('███████████')
    expect(demoEntityReplacement('tr', 'bodyWitnessOne')).toBe('[TANIK_1]')
    expect(demoEntityReplacement('tr', 'bodyCounselTwo')).toBe('Av. Ö.A.')
    expect(demoEntityReplacement('tr', 'partyPhone')).toBe('0532 *** ** 67')
    expect(demoEntityReplacement('tr', 'partyAddress')).toBeUndefined()
    expect(demoEntityReplacement('tr', 'bodyAccusedOne')).toBeUndefined()
  })

  it('scrolls to the transforming examples without leaving a gap after the last method', () => {
    expect(demoScrollAnchor('tr', 2200)).toBe('parties')
    expect(demoScrollAnchor('tr', 3400)).toBe('witness')
    expect(demoScrollAnchor('tr', 4700)).toBe('ruling')
    expect(demoScrollAnchor('tr', 6000)).toBe('parties')
    expect(demoIsComplete(6280)).toBe(true)
    expect(demoStage(6479)).toMatchObject({ kind: 'method', method: 'partial', index: 4 })
    expect(demoStage(6480)).toEqual({ kind: 'complete' })
    expect(DEMO_TOTAL).toBe(7200)
  })
})

describe('English contract demo script', () => {
  it('uses a four-method set with no keep, role, or generalize', () => {
    expect(demoMethodSet('en')).toEqual([...MASKING_METHODS])
    expect(demoMethodSet('tr')).toEqual([...MASKING_METHODS])
    for (const entity of Object.values(EN_DEMO_DETECTIONS)) {
      expect(entity).not.toHaveProperty('keep')
      if ('method' in entity && entity.method) expect(MASKING_METHODS).toContain(entity.method)
    }
  })

  it('uses English placeholder labels and the intended replacements', () => {
    expect(demoEntityReplacement('en', 'emilyName')).toBe('[PERSON_1]')
    expect(demoEntityReplacement('en', 'noticeEmilyName')).toBe('[PERSON_1]')
    expect(demoEntityReplacement('en', 'signatureEmily')).toBe('[PERSON_1]')
    expect(demoEntityReplacement('en', 'danielName')).toBe('D.B.')
    expect(demoEntityReplacement('en', 'signatureDaniel')).toBe('D.B.')
    expect(demoEntityReplacement('en', 'iban')).toBe('████████████████████████')
    expect(demoEntityReplacement('en', 'emilyEmail')).toBe('e***@example.com')
    expect(demoEntityReplacement('en', 'noticeEmail')).toBe('e***@example.com')
    expect(demoEntityReplacement('en', 'emilyName')).not.toBe('[KİŞİ_1]')
    expect(demoEntityMethod('en', 'iban')).toBe('redact')
    expect(demoEntityMethod('en', 'emilyName')).toBe('placeholder')
    expect(demoEntityMethod('en', 'danielName')).toBe('initials')
    expect(demoEntityMethod('en', 'emilyEmail')).toBe('partial')
  })

  it('keeps English transformations visible in the reduced-motion state', () => {
    expect(demoTextState('en', 'iban', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('en', 'emilyName', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('en', 'noticeEmilyName', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('en', 'signatureEmily', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('en', 'danielName', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('en', 'emilyEmail', DEMO_STATIC_ELAPSED)).toBe('transformed')
    expect(demoTextState('en', 'companyNorthstar', DEMO_STATIC_ELAPSED)).toBe('idle')
    expect(demoTextState('en', 'partyId', DEMO_STATIC_ELAPSED)).toBe('idle')
  })

  it('scrolls through contract anchors rather than court sections', () => {
    expect(demoScrollAnchor('en', 800)).toBe('top')
    expect(demoScrollAnchor('en', 2200)).toBe('payment')
    expect(demoScrollAnchor('en', 3400)).toBe('contacts')
    expect(demoScrollAnchor('en', 4700)).toBe('signatures')
    expect(demoScrollAnchor('en', 6000)).toBe('notices')
    expect(demoScrollAnchor('en', 2200)).not.toBe('witness')
    expect(demoScrollAnchor('en', 4700)).not.toBe('ruling')
  })

  it('keeps Turkish and English entity IDs in separate scripts', () => {
    expect('partyId' in TR_DEMO_DETECTIONS).toBe(true)
    expect('iban' in EN_DEMO_DETECTIONS).toBe(true)
    expect('iban' in TR_DEMO_DETECTIONS).toBe(false)
    expect('partyId' in EN_DEMO_DETECTIONS).toBe(false)
    expect(DEMO_SCRIPTS.en.categories).toEqual([
      'person',
      'identifier',
      'address',
      'contact',
      'financial',
      'company',
    ])
    expect(DEMO_SCRIPTS.tr.categories).toEqual([
      'person',
      'identifier',
      'address',
      'case',
      'court',
    ])
  })
})

describe('landing demo copy', () => {
  it('describes four masking methods in Turkish and English', () => {
    expect(tr.demo.methodsTitle).toBe('4 farklı maskeleme yöntemi')
    expect(tr.demo.methodsSummary).toBe(
      'Tamamen gizle · Etiketle değiştir · Baş harflerle göster · Kısmen gizle',
    )
    expect(tr.demo.methods).toEqual({
      redact: 'Tamamen gizle',
      placeholder: 'Etiketle değiştir',
      initials: 'Baş harflerle göster',
      partial: 'Kısmen gizle',
    })
    expect(tr.heroBody).toContain('4 farklı maskeleme yöntemi')

    expect(en.demo.methodsTitle).toBe('4 masking methods')
    expect(en.demo.methodsSummary).toBe(
      'Hide completely · Replace with label · Show initials · Mask partially',
    )
    expect(en.demo.methods).toEqual({
      redact: 'Hide completely',
      placeholder: 'Replace with label',
      initials: 'Show initials',
      partial: 'Mask partially',
    })
    expect(en.heroBody).toContain('4 different masking methods')
  })

  it('does not present keep, role, or generalization as landing demo methods', () => {
    expect(tr.demo.methods).not.toHaveProperty('keep')
    expect(tr.demo.methods).not.toHaveProperty('role')
    expect(tr.demo.methods).not.toHaveProperty('label')
    expect(tr.demo.methods).not.toHaveProperty('generalize')
    expect(tr.demo.methodsSummary).not.toMatch(/Rol|Genelleştirme|Belgede bırak/i)
    expect(en.demo.methodsSummary).not.toMatch(/Role|Generaliz|Keep in document/i)
  })

  it('uses English meter categories for the contract demo', () => {
    expect(en.demo.short.person).toBe('People')
    expect(en.demo.short.identifier).toBe('Identifiers')
    expect(en.demo.short.address).toBe('Addresses')
    expect(en.demo.short.contact).toBe('Contact')
    expect(en.demo.short.financial).toBe('Financial')
    expect(en.demo.short.company).toBe('Companies')
  })
})
