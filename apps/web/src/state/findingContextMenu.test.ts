import { describe, expect, it } from 'vitest'
import type { Analysis, Entity, TransformCatalog } from './types'
import {
  analysisWithoutRemovedFindings,
  contextMenuShowsEdit,
  contextMenuShowsKeep,
  contextMenuStrategies,
  findingContextMenuItems,
  isPersonMergeType,
  selectFindingOnContextClick,
  shouldCloseFindingContextMenu,
  shouldOpenDocumentContextMenu,
  withoutRemovedFindings,
} from './findingContextMenu'

const catalog: TransformCatalog = {
  strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'PARTIAL_MASK', 'KEEP'],
  categories: [
    {
      category: 'CASE_NUMBER',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: false,
    },
    {
      category: 'PERSON_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: true,
    },
    {
      category: 'NATIONAL_ID',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'REDACT',
      generalization_options: [],
      supports_role_replacement: false,
    },
  ],
  role_labels: { tr: {}, en: {} },
  secure_pdf_strategies: ['REDACT'],
}

function entity(partial: Partial<Entity> & Pick<Entity, 'id' | 'type'>): Entity {
  return {
    text: partial.text ?? partial.id,
    start: partial.start ?? 0,
    end: partial.end ?? 8,
    page: partial.page ?? 0,
    detector: partial.detector ?? 'TEST',
    method: partial.method ?? 'DETERMINISTIC',
    validated: true,
    recommended: true,
    ...partial,
  }
}

describe('finding context menu actions', () => {
  it('shows supported methods and remove for CASE_NUMBER, without merge or KEEP', () => {
    const items = findingContextMenuItems(entity({ id: 'c1', type: 'CASE_NUMBER', text: '2025/446' }), catalog)
    expect(items.map((item) => (item.kind === 'strategy' ? item.strategy : item.kind))).toEqual([
      'REDACT',
      'PLACEHOLDER',
      'remove',
    ])
    expect(items.some((item) => item.kind === 'merge')).toBe(false)
    expect(contextMenuShowsKeep(items)).toBe(false)
    expect(contextMenuShowsEdit(items)).toBe(false)
  })

  it('shows merge for PERSON_NAME and still excludes KEEP and edit', () => {
    const items = findingContextMenuItems(entity({ id: 'p1', type: 'PERSON_NAME', text: 'Mehmet' }), catalog)
    expect(items.map((item) => (item.kind === 'strategy' ? item.strategy : item.kind))).toEqual([
      'REDACT',
      'PLACEHOLDER',
      'INITIALS',
      'merge',
      'remove',
    ])
    expect(contextMenuShowsKeep(items)).toBe(false)
    expect(contextMenuShowsEdit(items)).toBe(false)
  })

  it('does not hardcode strategies: NATIONAL_ID follows the catalog', () => {
    expect(contextMenuStrategies('NATIONAL_ID', catalog)).toEqual(['REDACT', 'PLACEHOLDER'])
  })

  it('does not offer merge for identifiers or companies', () => {
    for (const type of ['NATIONAL_ID', 'IBAN', 'EMAIL', 'PHONE_NUMBER', 'COMPANY_NAME', 'CASE_NUMBER']) {
      expect(isPersonMergeType(type)).toBe(false)
      expect(
        findingContextMenuItems(entity({ id: type, type, text: type }), catalog).some(
          (item) => item.kind === 'merge',
        ),
      ).toBe(false)
    }
  })

  it('offers merge for duplicate addresses', () => {
    expect(isPersonMergeType('ADDRESS')).toBe(false)
    expect(
      findingContextMenuItems(entity({ id: 'a1', type: 'ADDRESS', text: 'Cadde 1' }), catalog).some(
        (item) => item.kind === 'merge',
      ),
    ).toBe(true)
  })

  it('offers merge for person and legal-role types, including custom findings of those types', () => {
    for (const type of [
      'PERSON_NAME',
      'FIRST_NAME',
      'LAST_NAME',
      'ALIAS',
      'CLAIMANT_NAME',
      'DEFENDANT_NAME',
      'LAWYER_NAME',
      'JUDGE_NAME',
      'WITNESS_NAME',
      'EXPERT_NAME',
    ]) {
      expect(isPersonMergeType(type)).toBe(true)
    }
    const custom = entity({
      id: 'custom',
      type: 'PERSON_NAME',
      text: 'Mehmet',
      method: 'MANUAL',
      detector: 'USER_DEFINED_TERM',
    })
    expect(findingContextMenuItems(custom, catalog).some((item) => item.kind === 'merge')).toBe(true)
  })

  it('selects the right-clicked finding even when another was active', () => {
    expect(selectFindingOnContextClick('other', 'clicked')).toBe('clicked')
    expect(selectFindingOnContextClick(null, 'clicked')).toBe('clicked')
  })

  it('closes on Escape and outside pointerdown', () => {
    expect(shouldCloseFindingContextMenu({ key: 'Escape' })).toBe(true)
    expect(shouldCloseFindingContextMenu({ type: 'pointerdown', insideMenu: false })).toBe(true)
    expect(shouldCloseFindingContextMenu({ type: 'pointerdown', insideMenu: true })).toBe(false)
    expect(shouldCloseFindingContextMenu({ key: 'Enter' })).toBe(false)
  })

  it('opens only on the document preview canvas, not detections view', () => {
    expect(shouldOpenDocumentContextMenu('preview', 'select')).toBe(true)
    expect(shouldOpenDocumentContextMenu('detections', 'select')).toBe(false)
    expect(shouldOpenDocumentContextMenu('preview', 'redact-area')).toBe(false)
  })
})

describe('remove finding is occurrence-scoped', () => {
  const cases = [
    entity({ id: 'a', type: 'CASE_NUMBER', text: '2025/446', start: 0, end: 8, page: 0 }),
    entity({ id: 'b', type: 'CASE_NUMBER', text: '2025/446', start: 20, end: 28, page: 0 }),
    entity({ id: 'c', type: 'CASE_NUMBER', text: '2025/446', start: 40, end: 48, page: 1 }),
    entity({ id: 'd', type: 'CASE_NUMBER', text: '2025/446', start: 60, end: 68, page: 2 }),
  ]

  it('removes only the selected occurrence', () => {
    const next = withoutRemovedFindings(cases, ['b'])
    expect(next.map((item) => item.id)).toEqual(['a', 'c', 'd'])
    expect(next.every((item) => item.text === '2025/446')).toBe(true)
  })

  it('does not delete the remaining entity or identical text', () => {
    const next = withoutRemovedFindings(cases, ['b'])
    expect(next).toHaveLength(3)
    expect(next.find((item) => item.id === 'a')).toEqual(cases[0])
  })

  it('undo restores the removed occurrence by clearing the id', () => {
    const removed = ['b']
    expect(withoutRemovedFindings(cases, removed)).toHaveLength(3)
    expect(withoutRemovedFindings(cases, [])).toEqual(cases)
  })

  it('prunes possible-match cards that lose a member after occurrence removal', () => {
    const analysis: Analysis = {
      job_id: 'job',
      file_name: 't.pdf',
      document_kind: 'PDF',
      page_count: 1,
      text: 'Mehmet Mehmet Yılmaz',
      entities: [
        entity({ id: 'p4', type: 'PERSON_NAME', text: 'Mehmet', resolved_entity_id: 'kisi-4' }),
        entity({ id: 'p1', type: 'PERSON_NAME', text: 'Mehmet Yılmaz', resolved_entity_id: 'kisi-1' }),
      ],
      warnings: [],
      profile: 'GENERAL',
      possible_matches: [
        {
          id: 'm1',
          members: [
            { canonical_id: 'kisi-4', entity_ids: ['p4'], text: 'Mehmet', pages: [0] },
            { canonical_id: 'kisi-1', entity_ids: ['p1'], text: 'Mehmet Yılmaz', pages: [0] },
          ],
        },
      ],
    }
    const next = analysisWithoutRemovedFindings(analysis, ['p4'])
    expect(next.entities.map((item) => item.id)).toEqual(['p1'])
    expect(next.possible_matches).toEqual([])
    expect(analysis.text).toBe('Mehmet Mehmet Yılmaz')
  })
})
