import { describe, expect, it } from 'vitest'
import {
  analysisStatusOf,
  canApplyRedactions,
  catalogStrategyFor,
  detectionSource,
  effectiveStrategy,
  isActionableFinding,
  isReviewRecommended,
  partitionFindingsByAction,
  showDetectionOverlay,
  tallyActionableFindings,
  mergePresetCategoryDefaults,
  mergePresetDecisions,
  mergeProfileDecisions,
  previewEntityValue,
  strategyResultExample,
  placeholderSamplesForTypes,
  placeholderTokensByEntityId,
  previewTransformLocal,
  restoreStrategyFor,
  seedCategoryDefaults,
  seedDecisions,
  seedEntityStrategies,
  sourceLabelKey,
  usesPaperRedaction,
  relatedEntityIds,
  expandRelatedIds,
  splitRecommendedGroups,
  groupEntities,
  groupCollapsedByFamily,
  listRowId,
  userOutputStrategiesFor,
  validationCounts,
  manualItemId,
  manualKindKey,
  findManualById,
  exportRectanglesForEntity,
  detectedFontSize,
  needsInitialsSizeControl,
  findDocumentPhraseHits,
  customTermTargetIds,
} from './helpers'
import type { Analysis, Entity, TransformCatalog } from './types'

const catalog: TransformCatalog = {
  strategies: ['REDACT', 'PLACEHOLDER', 'PARTIAL_MASK', 'KEEP'],
  categories: [
    {
      category: 'PHONE_NUMBER',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'PARTIAL_MASK', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: false,
    },
    {
      category: 'EMAIL',
      allowed_strategies: ['REDACT', 'PARTIAL_MASK', 'KEEP'],
      recommended_strategy: 'PARTIAL_MASK',
      generalization_options: [],
      supports_role_replacement: false,
    },
    {
      category: 'NATIONAL_ID',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'REDACT',
      generalization_options: [],
      supports_role_replacement: false,
    },
    {
      category: 'COMPANY_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: false,
    },
    {
      category: 'ADDRESS',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'PARTIAL_MASK', 'KEEP'],
      recommended_strategy: 'REDACT',
      generalization_options: [],
      supports_role_replacement: false,
    },
  ],
  role_labels: { tr: {}, en: {} },
  secure_pdf_strategies: ['REDACT'],
}

function entity(partial: Partial<Entity> & Pick<Entity, 'id' | 'type' | 'recommended'>): Entity {
  return {
    text: partial.text ?? partial.id,
    start: partial.start ?? 0,
    end: partial.end ?? 1,
    page: partial.page ?? 0,
    detector: partial.detector ?? 'TEST',
    method: partial.method ?? 'DETERMINISTIC',
    validated: partial.validated ?? true,
    ...partial,
  }
}

describe('seedDecisions', () => {
  it('maps recommended entities to REDACT', () => {
    const decisions = seedDecisions([
      entity({ id: 'a', type: 'EMAIL', recommended: true }),
      entity({ id: 'b', type: 'DATE', recommended: false }),
    ])
    expect(decisions).toEqual({ a: 'REDACT', b: 'KEEP' })
  })

  it('keeps needs_review findings until the user confirms them', () => {
    const decisions = seedDecisions([
      entity({ id: 'a', type: 'PERSON_NAME', recommended: true, needs_review: true }),
    ])
    expect(decisions.a).toBe('KEEP')
    expect(isReviewRecommended(entity({ id: 'a', type: 'PERSON_NAME', recommended: true, needs_review: true }))).toBe(true)
    expect(isReviewRecommended(entity({ id: 'a', type: 'PERSON_NAME', recommended: true, method: 'AI' }))).toBe(false)
  })

  it('keeps every finding in detect-only', () => {
    expect(seedDecisions([
      entity({ id: 'a', type: 'EMAIL', recommended: true }),
    ], 'DETECT_ONLY')).toEqual({ a: 'KEEP' })
  })
})

describe('usesPaperRedaction', () => {
  it('uses the page background for QR codes, UYAP access, and sicil numbers', () => {
    expect(usesPaperRedaction('QR_CODE')).toBe(true)
    expect(usesPaperRedaction('UYAP_ACCESS')).toBe(true)
    expect(usesPaperRedaction('PROFESSIONAL_ID')).toBe(true)
    expect(usesPaperRedaction('NATIONAL_ID')).toBe(false)
    expect(usesPaperRedaction('SIGNATURE')).toBe(false)
    expect(usesPaperRedaction('COURT_NAME')).toBe(false)
    expect(usesPaperRedaction('COURT_NAME', { mask_scope: 'header_line' })).toBe(true)
  })
})

describe('effectiveStrategy', () => {
  it('prefers entity override over category default', () => {
    const item = entity({ id: 'a', type: 'EMAIL', recommended: true })
    expect(
      effectiveStrategy(item, { a: 'REDACT' }, { EMAIL: 'REDACT' }, { a: 'PARTIAL_MASK' }),
    ).toBe('PARTIAL_MASK')
  })

  it('returns KEEP when decision is KEEP', () => {
    const item = entity({ id: 'a', type: 'EMAIL', recommended: true })
    expect(
      effectiveStrategy(item, { a: 'KEEP' }, { EMAIL: 'REDACT' }, {}),
    ).toBe('KEEP')
  })
})

describe('showDetectionOverlay', () => {
  it('hides KEEP overlays by default, including courts and companies', () => {
    const court = entity({
      id: 'a',
      type: 'COURT_NAME',
      recommended: false,
      recommended_strategy: 'KEEP',
    })
    const company = entity({
      id: 'b',
      type: 'COMPANY_NAME',
      recommended: false,
      recommended_strategy: 'KEEP',
    })
    const bank = entity({
      id: 'c',
      type: 'ORGANISATION',
      recommended: false,
      attributes: { org_kind: 'BANK' },
    })
    expect(showDetectionOverlay(court, 'KEEP', 'detections')).toBe(false)
    expect(showDetectionOverlay(company, 'KEEP', 'detections')).toBe(false)
    expect(showDetectionOverlay(bank, 'KEEP', 'detections')).toBe(false)
    expect(showDetectionOverlay(court, 'KEEP', 'preview')).toBe(false)
  })

  it('shows KEEP overlays only when preserved visibility is on', () => {
    const court = entity({
      id: 'a',
      type: 'COURT_NAME',
      recommended: false,
      recommended_strategy: 'KEEP',
    })
    expect(showDetectionOverlay(court, 'KEEP', 'detections', true)).toBe(true)
    expect(showDetectionOverlay(court, 'KEEP', 'preview', true)).toBe(false)
  })

  it('does not infer KEEP from category names', () => {
    const court = entity({
      id: 'a',
      type: 'COURT_NAME',
      recommended: true,
      recommended_strategy: 'PARTIAL_MASK',
    })
    expect(showDetectionOverlay(court, 'PARTIAL_MASK', 'detections')).toBe(true)
  })

  it('keeps QR redaction overlays independent of KEEP cleanup', () => {
    const qr = entity({
      id: 'q',
      type: 'QR_CODE',
      recommended: true,
      recommended_strategy: 'REDACT',
      detector: 'QR_CODE_VISUAL',
    })
    expect(showDetectionOverlay(qr, 'REDACT', 'detections')).toBe(true)
    expect(showDetectionOverlay(qr, 'REDACT', 'preview')).toBe(true)
    expect(showDetectionOverlay(qr, 'KEEP', 'detections')).toBe(false)
  })

  it('hides a kept person name in detections', () => {
    const item = entity({ id: 'a', type: 'PERSON_NAME', recommended: true })
    expect(showDetectionOverlay(item, 'KEEP', 'detections')).toBe(false)
  })

  it('hides a kept IBAN until preserved visibility is on', () => {
    const item = entity({ id: 'a', type: 'IBAN', recommended: true })
    expect(showDetectionOverlay(item, 'KEEP', 'detections')).toBe(false)
    expect(showDetectionOverlay(item, 'KEEP', 'detections', true)).toBe(true)
    expect(showDetectionOverlay(item, 'KEEP', 'preview')).toBe(false)
  })

  it('hides legal glue and GSM prose overlays', () => {
    expect(
      showDetectionOverlay(entity({ id: 'a', type: 'LOCATION', text: 'nezdinde', recommended: false }), 'REDACT', 'detections'),
    ).toBe(false)
    expect(
      showDetectionOverlay(
        entity({ id: 'a', type: 'FINANCIAL_IDENTIFIER', text: "İbana anlaştıkları 6.198 TL'yi", recommended: false }),
        'REDACT',
        'detections',
      ),
    ).toBe(false)
  })

  it('ignores a KEEP entity override when the decision is REDACT', () => {
    const item = entity({
      id: 'a',
      type: 'PERSON_NAME',
      recommended: true,
      recommended_strategy: 'INITIALS',
    })
    expect(
      effectiveStrategy(
        item,
        { a: 'REDACT' },
        { PERSON_NAME: 'INITIALS' },
        { a: 'KEEP' },
      ),
    ).toBe('INITIALS')
  })

  it('lets Av. titles follow the kişi adları category default', () => {
    const item = entity({
      id: 'a',
      type: 'PERSON_NAME',
      text: 'Av. İrem Hazal Deveci',
      recommended: true,
      recommended_strategy: 'PLACEHOLDER',
    })
    expect(
      effectiveStrategy(item, {}, { PERSON_NAME: 'PLACEHOLDER' }, {}),
    ).toBe('PLACEHOLDER')
  })
})

describe('partitionFindingsByAction', () => {
  const tribunal = entity({
    id: 'court',
    type: 'COURT_NAME',
    text: 'EMPLOYMENT TRIBUNALS',
    recommended: false,
    recommended_strategy: 'KEEP',
  })
  const company = entity({
    id: 'co',
    type: 'COMPANY_NAME',
    text: 'Wechseln Limited',
    recommended: false,
    recommended_strategy: 'KEEP',
  })
  const salon = entity({
    id: 'salon',
    type: 'COMPANY_NAME',
    text: 'Andrew Hill Salon',
    recommended: false,
    recommended_strategy: 'KEEP',
  })
  const lauren = entity({
    id: 'lauren',
    type: 'PERSON_NAME',
    text: 'Lauren De Lacey',
    recommended: true,
    recommended_strategy: 'REDACT',
  })
  const leach = entity({
    id: 'leach',
    type: 'PERSON_NAME',
    text: 'D Leach',
    recommended: true,
    recommended_strategy: 'REDACT',
  })
  const osborne = entity({
    id: 'osborne',
    type: 'PERSON_NAME',
    text: 'J Osborne',
    recommended: true,
    recommended_strategy: 'REDACT',
  })
  const caseNo = entity({
    id: 'case',
    type: 'CASE_NUMBER',
    text: '1400945/2017',
    recommended: true,
    recommended_strategy: 'REDACT',
  })
  const entities = [tribunal, company, salon, lauren, leach, osborne, caseNo]
  const decisions = seedDecisions(entities)
  const defaults = {
    COURT_NAME: 'KEEP' as const,
    COMPANY_NAME: 'KEEP' as const,
    PERSON_NAME: 'REDACT' as const,
    CASE_NUMBER: 'REDACT' as const,
  }

  it('splits KEEP courts and companies from actionable people and case numbers', () => {
    const { actionable, preserved } = partitionFindingsByAction(
      entities,
      decisions,
      defaults,
      {},
    )
    expect(preserved.map((item) => item.text)).toEqual([
      'EMPLOYMENT TRIBUNALS',
      'Wechseln Limited',
      'Andrew Hill Salon',
    ])
    expect(actionable.map((item) => item.text)).toEqual([
      'Lauren De Lacey',
      'D Leach',
      'J Osborne',
      '1400945/2017',
    ])
    expect(tallyActionableFindings(entities, decisions, defaults, {})).toEqual({
      actionable: 4,
      preserved: 3,
    })
  })

  it('uses effective strategy, not COURT_NAME or COMPANY_NAME', () => {
    expect(isActionableFinding(tribunal, decisions, defaults, {})).toBe(false)
    expect(
      isActionableFinding(
        tribunal,
        { ...decisions, court: 'REDACT' },
        defaults,
        { court: 'REDACT' },
      ),
    ).toBe(true)
    expect(
      isActionableFinding(
        lauren,
        { ...decisions, lauren: 'KEEP' },
        defaults,
        { lauren: 'KEEP' },
      ),
    ).toBe(false)
  })

  it('does not select KEEP findings for transformation by default', () => {
    expect(decisions.court).toBe('KEEP')
    expect(decisions.co).toBe('KEEP')
    expect(decisions.salon).toBe('KEEP')
    expect(decisions.lauren).toBe('REDACT')
    expect(decisions.case).toBe('REDACT')
  })
})

describe('restoreStrategyFor', () => {
  it('reuses a stored masking method', () => {
    const item = entity({ id: 'a', type: 'PERSON_NAME', recommended: true })
    expect(
      restoreStrategyFor(item, { PERSON_NAME: 'REDACT' }, { a: 'INITIALS' }),
    ).toBe('INITIALS')
  })

  it('falls back to the category default when the stored method is KEEP', () => {
    const item = entity({
      id: 'a',
      type: 'COURT_NAME',
      recommended: true,
      recommended_strategy: 'PARTIAL_MASK',
    })
    expect(
      restoreStrategyFor(item, { COURT_NAME: 'PARTIAL_MASK' }, { a: 'KEEP' }),
    ).toBe('PARTIAL_MASK')
  })

  it('falls back to the recommended strategy', () => {
    const item = entity({
      id: 'a',
      type: 'EMAIL',
      recommended: true,
      recommended_strategy: 'PLACEHOLDER',
    })
    expect(restoreStrategyFor(item, {}, {})).toBe('PLACEHOLDER')
  })
})

describe('seedCategoryDefaults', () => {
  it('uses catalog recommended strategy for anonymized preset', () => {
    const defaults = seedCategoryDefaults([
      entity({
        id: 'a',
        type: 'PHONE_NUMBER',
        recommended: true,
        recommended_strategy: 'PLACEHOLDER',
      }),
    ], catalog, 'ANONYMIZED')
    expect(defaults.PHONE_NUMBER).toBe('PLACEHOLDER')
  })

  it('uses catalog placeholder for companies even if a notice-recipient sample is redact', () => {
    const defaults = seedCategoryDefaults(
      [
        entity({
          id: 'a',
          type: 'COMPANY_NAME',
          recommended: true,
          recommended_strategy: 'REDACT',
        }),
      ],
      catalog,
      'ANONYMIZED',
    )
    expect(defaults.COMPANY_NAME).toBe('PLACEHOLDER')
  })

  it('falls back to entity recommended_strategy when catalog is missing', () => {
    const defaults = seedCategoryDefaults([
      entity({
        id: 'a',
        type: 'PHONE_NUMBER',
        recommended: true,
        recommended_strategy: 'PARTIAL_MASK',
      }),
    ], null, 'ANONYMIZED')
    expect(defaults.PHONE_NUMBER).toBe('PARTIAL_MASK')
  })

  it('uses permanent redaction for strict production on recommended types', () => {
    const defaults = seedCategoryDefaults([
      entity({ id: 'a', type: 'NATIONAL_ID', recommended: true }),
    ], catalog, 'STRICT_PRODUCTION')
    expect(defaults.NATIONAL_ID).toBe('REDACT')
  })

  it('defaults allowed categories to a label in the text workspace', () => {
    const entities = [
      entity({
        id: 'p',
        type: 'PERSON_NAME',
        recommended: true,
        recommended_strategy: 'PARTIAL_MASK',
      }),
      entity({
        id: 'a',
        type: 'ADDRESS',
        recommended: true,
        recommended_strategy: 'REDACT',
      }),
      entity({
        id: 'e',
        type: 'EMAIL',
        recommended: true,
        recommended_strategy: 'PARTIAL_MASK',
      }),
    ]
    const defaults = seedCategoryDefaults(entities, catalog, 'ANONYMIZED', { workspaceMode: 'TEXT' })
    expect(defaults.PERSON_NAME).toBe('PLACEHOLDER')
    expect(defaults.ADDRESS).toBe('PLACEHOLDER')
    expect(defaults.EMAIL).toBe('PARTIAL_MASK')
    expect(seedEntityStrategies(entities, catalog, 'ANONYMIZED', { workspaceMode: 'TEXT' })).toEqual({})
    expect(seedCategoryDefaults(entities, catalog, 'ANONYMIZED').ADDRESS).toBe('REDACT')
  })

  it('keeps every category in detect-only preset', () => {
    const defaults = seedCategoryDefaults([
      entity({ id: 'a', type: 'EMAIL', recommended: true }),
    ], catalog, 'DETECT_ONLY')
    expect(defaults.EMAIL).toBe('KEEP')
  })
})

describe('seedEntityStrategies', () => {
  it('does not default AI findings to permanent redaction', () => {
    const strategies = seedEntityStrategies([
      entity({
        id: 'a',
        type: 'PERSON_NAME',
        recommended: true,
        method: 'AI',
        recommended_strategy: 'PLACEHOLDER',
      }),
    ], catalog, 'ANONYMIZED')
    expect(strategies.a).toBe('PLACEHOLDER')
  })

  it('lets lawyer names follow recommended strategy instead of pinning redaction', () => {
    const strategies = seedEntityStrategies(
      [
        entity({
          id: 'a',
          type: 'LAWYER_NAME',
          recommended: true,
          recommended_strategy: 'PLACEHOLDER',
        }),
        entity({
          id: 'b',
          type: 'PERSON_NAME',
          recommended: true,
          role: 'COUNSEL',
          recommended_strategy: 'PLACEHOLDER',
        }),
        entity({
          id: 'c',
          type: 'PERSON_NAME',
          recommended: true,
          text: 'Av. İrem Hazal Deveci',
          recommended_strategy: 'PLACEHOLDER',
        }),
      ],
      catalog,
      'ANONYMIZED',
    )
    expect(strategies.a).toBe('PLACEHOLDER')
    expect(strategies.b).toBe('PLACEHOLDER')
    expect(strategies.c).toBe('PLACEHOLDER')
  })
})

describe('preset merge', () => {
  it('updates untouched category defaults when the preset changes', () => {
    const entities = [entity({ id: 'a', type: 'PHONE_NUMBER', recommended: true })]
    const previous = seedCategoryDefaults(entities, catalog, 'ANONYMIZED')
    const next = mergePresetCategoryDefaults(entities, previous, 'ANONYMIZED', 'STRICT_PRODUCTION', catalog)
    expect(next.PHONE_NUMBER).toBe('REDACT')
  })

  it('preserves a user category override across preset changes', () => {
    const entities = [entity({ id: 'a', type: 'PHONE_NUMBER', recommended: true })]
    const previous = { PHONE_NUMBER: 'PARTIAL_MASK' as const }
    const next = mergePresetCategoryDefaults(entities, previous, 'ANONYMIZED', 'STRICT_PRODUCTION', catalog)
    expect(next.PHONE_NUMBER).toBe('PARTIAL_MASK')
  })

  it('reseeds untouched entity decisions when the preset changes', () => {
    const entities = [entity({ id: 'a', type: 'EMAIL', recommended: true })]
    expect(mergePresetDecisions(entities, { a: 'REDACT' }, 'ANONYMIZED', 'DETECT_ONLY')).toEqual({
      a: 'KEEP',
    })
  })
})

describe('catalogStrategyFor', () => {
  it('prefers the entity recommendation over the catalog', () => {
    expect(
      catalogStrategyFor(
        'PHONE_NUMBER',
        catalog,
        entity({ id: 'a', type: 'PHONE_NUMBER', recommended: true, recommended_strategy: 'PLACEHOLDER' }),
      ),
    ).toBe('PLACEHOLDER')
  })
})

describe('mergeProfileDecisions', () => {
  it('updates untouched decisions when recommendations change', () => {
    const previousEntities = [
      entity({ id: 'a', type: 'EMAIL', recommended: true }),
      entity({ id: 'b', type: 'DATE', recommended: false }),
    ]
    const previous = { a: 'REDACT' as const, b: 'KEEP' as const }
    const nextEntities = [
      entity({ id: 'a', type: 'EMAIL', recommended: false }),
      entity({ id: 'b', type: 'DATE', recommended: false }),
    ]
    expect(mergeProfileDecisions(nextEntities, previous, previousEntities)).toEqual({
      a: 'KEEP',
      b: 'KEEP',
    })
  })

  it('preserves user overrides', () => {
    const previousEntities = [
      entity({ id: 'a', type: 'EMAIL', recommended: true }),
    ]
    const previous = { a: 'KEEP' as const }
    const nextEntities = [
      entity({ id: 'a', type: 'EMAIL', recommended: true }),
    ]
    expect(mergeProfileDecisions(nextEntities, previous, previousEntities)).toEqual({
      a: 'KEEP',
    })
  })
})

describe('splitRecommendedGroups', () => {
  it('buckets recommended categories separately', () => {
    const groups = groupEntities([
      entity({ id: '1', type: 'EMAIL', recommended: true, start: 0, end: 1 }),
      entity({ id: '2', type: 'COURT_NAME', recommended: false, start: 2, end: 3 }),
    ])
    const split = splitRecommendedGroups(groups)
    expect(split.recommended.map(([type]) => type)).toContain('EMAIL')
    expect(split.other.map(([type]) => type)).toContain('COURT_NAME')
  })
})

describe('validationCounts', () => {
  it('prefers explicit failed and warning counts', () => {
    expect(
      validationCounts({
        validation: { status: 'WARNING', messages: [], failed_count: 0, warning_count: 2, verified_count: 3 },
        download_url: '/x',
        audit_url: '/y',
      }),
    ).toEqual({ failed: 0, warnings: 2, verified: 3 })
  })

  it('treats FAILED without counts as one error', () => {
    expect(
      validationCounts({
        validation: { status: 'FAILED', messages: [] },
        download_url: null,
        audit_url: '/y',
      }),
    ).toEqual({ failed: 1, warnings: 0, verified: 0 })
  })
})

describe('apply safety', () => {
  it('disables apply when no transformations are selected', () => {
    expect(canApplyRedactions({ a: 'KEEP', b: 'KEEP' }, [])).toBe(false)
    expect(canApplyRedactions({ a: 'REDACT' }, [])).toBe(true)
    expect(canApplyRedactions({}, [{ text: 'Ayşe', page: 1 }])).toBe(true)
  })
})

describe('analysis completeness', () => {
  const base: Analysis = {
    job_id: 'job',
    file_name: 'letter.txt',
    document_kind: 'TEXT',
    page_count: 1,
    text: 'x',
    entities: [],
    warnings: [],
    profile: 'GENERAL',
  }

  it('does not treat missing analysis_status as AI failure', () => {
    expect(analysisStatusOf({ ...base, warnings: ['AI_DETECTION_FAILED'] })).toBe('COMPLETE')
  })

  it('does not treat intentional deterministic-only mode as failure', () => {
    expect(analysisStatusOf({ ...base, analysis_status: 'COMPLETE', ai_status: 'DISABLED' })).toBe('COMPLETE')
  })
})

describe('detectionSource', () => {
  it('labels detection methods for the review UI', () => {
    expect(detectionSource(entity({ id: 'a', type: 'EMAIL', recommended: true, method: 'DETERMINISTIC' }))).toBe('verified')
    expect(detectionSource(entity({ id: 'b', type: 'PERSON_NAME', recommended: true, method: 'AI' }))).toBe('contextual')
    expect(detectionSource(entity({ id: 'c', type: 'CUSTOMER_ID', recommended: true, method: 'STRUCTURAL' }))).toBe('structural')
    expect(detectionSource(entity({ id: 'd', type: 'ADDRESS', recommended: true, method: 'MANUAL' }))).toBe('manual')
  })

  it('maps sources to lawyer-facing label keys', () => {
    expect(sourceLabelKey('verified')).toBe('sourceLocal')
    expect(sourceLabelKey('structural')).toBe('sourceStructural')
    expect(sourceLabelKey('contextual')).toBe('sourceAi')
    expect(sourceLabelKey('manual')).toBe('sourceManual')
  })
})

describe('relatedEntityIds', () => {
  it('expands collapsed decisions to every occurrence', () => {
    const entities = [
      entity({ id: '1', type: 'PERSON_NAME', recommended: true, resolved_entity_id: 'r1' }),
      entity({ id: '2', type: 'PERSON_NAME', recommended: true, resolved_entity_id: 'r1' }),
      entity({ id: '3', type: 'EMAIL', recommended: true, resolved_entity_id: 'r2' }),
    ]
    expect(relatedEntityIds('1', entities).sort()).toEqual(['1', '2'])
    expect(expandRelatedIds(['1', '3'], entities).sort()).toEqual(['1', '2', '3'])
  })

  it('groups the same type and spelling when no resolved id exists', () => {
    const entities = [
      entity({ id: '1', type: 'PERSON_NAME', recommended: true, text: 'Mehmet Yılmaz' }),
      entity({ id: '2', type: 'PERSON_NAME', recommended: true, text: 'Mehmet Yılmaz' }),
      entity({ id: '3', type: 'PERSON_NAME', recommended: true, text: 'Ayşe Demir' }),
    ]
    expect(relatedEntityIds('1', entities).sort()).toEqual(['1', '2'])
    expect(groupCollapsedByFamily(entities)[0].rows).toHaveLength(2)
  })
})

describe('groupEntities', () => {
  it('collapses entities sharing resolved_entity_id into one row', () => {
    const entities = [
      entity({ id: '1', type: 'PERSON_NAME', recommended: true, text: 'Mehmet Yilmaz', resolved_entity_id: 'abc', start: 0, end: 13 }),
      entity({ id: '2', type: 'PERSON_NAME', recommended: true, text: 'Mehmet Yilmaz', resolved_entity_id: 'abc', start: 100, end: 113 }),
      entity({ id: '3', type: 'PERSON_NAME', recommended: true, text: 'Mehmet Yilmaz', resolved_entity_id: 'abc', start: 200, end: 213 }),
      entity({ id: '4', type: 'EMAIL', recommended: true, text: 'test@example.test', start: 50, end: 67 }),
    ]
    const groups = groupEntities(entities)
    const personGroup = groups.find(([type]) => type === 'PERSON_NAME')
    expect(personGroup).toBeDefined()
    expect(personGroup![1].length).toBe(1)
    expect(personGroup![1][0].occurrence_count).toBe(3)
    
    const emailGroup = groups.find(([type]) => type === 'EMAIL')
    expect(emailGroup![1].length).toBe(1)
    expect(emailGroup![1][0].occurrence_count).toBeUndefined()
  })
})

describe('groupCollapsedByFamily', () => {
  it('groups collapsed findings in the user-facing family order', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'PERSON_NAME', recommended: true, resolved_entity_id: 'p', text: 'Ayşe' }),
      entity({ id: '2', type: 'PERSON_NAME', recommended: true, resolved_entity_id: 'p', text: 'Ayşe' }),
      entity({ id: '3', type: 'EMAIL', recommended: true, text: 'a@b.test' }),
      entity({ id: '4', type: 'IBAN', recommended: true, text: 'TR00' }),
    ])
    expect(groups.map((group) => group.id)).toEqual(['person', 'contact', 'banking'])
    expect(groups[0].rows).toHaveLength(1)
    expect(groups[0].mentionCount).toBe(2)
    expect(groups[0].types).toHaveLength(1)
    expect(groups[0].types[0].type).toBe('PERSON_NAME')
    expect(groups[0].flattened).toBe(true)
  })

  it('lists first and last names under one person-name group', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'FIRST_NAME', recommended: true, text: 'Ayşe' }),
      entity({ id: '2', type: 'LAST_NAME', recommended: true, text: 'Demir' }),
      entity({ id: '3', type: 'PERSON_NAME', recommended: true, text: 'Ali Kaya' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('person')
    expect(groups[0].types.map((item) => item.type)).toEqual(['PERSON_NAME'])
    expect(groups[0].types[0].rows).toHaveLength(3)
    expect(groups[0].flattened).toBe(true)
  })

  it('lists court roles under the person group and court names on their own', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'JUDGE_NAME', recommended: true, text: 'Ayşe Yılmaz' }),
      entity({ id: '2', type: 'LAWYER_NAME', recommended: true, text: 'Hasan Koç' }),
      entity({ id: '3', type: 'CLAIMANT_NAME', recommended: true, text: 'Ali Kaya' }),
      entity({ id: '4', type: 'COURT_NAME', recommended: true, text: 'Ankara 1. Asliye' }),
      entity({ id: '5', type: 'PROFESSIONAL_ID', recommended: true, text: '12345' }),
    ])
    expect(groups.map((group) => group.id)).toEqual(['person', 'court'])
    expect(groups[0].types.map((item) => item.type)).toEqual([
      'CLAIMANT_NAME',
      'LAWYER_NAME',
      'JUDGE_NAME',
    ])
    expect(groups[0].flattened).toBe(false)
    expect(groups[1].id).toBe('court')
    expect(groups[1].types.map((item) => item.type)).toEqual([
      'COURT_NAME',
      'PROFESSIONAL_ID',
    ])
    expect(groups[1].flattened).toBe(false)
  })

  it('keeps ordinary person names and lawyer names under person, not court', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'LAWYER_NAME', recommended: true, text: 'Hasan Koç' }),
      entity({ id: '2', type: 'PERSON_NAME', recommended: true, text: 'Ali Kaya' }),
    ])
    expect(groups.map((group) => group.id)).toEqual(['person'])
    expect(groups[0].types.map((item) => item.type)).toEqual(['PERSON_NAME', 'LAWYER_NAME'])
    expect(groups[0].flattened).toBe(false)
  })

  it('lists locations as a detected address subcategory', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'ADDRESS', recommended: true, text: 'Atatürk Cad. 12' }),
      entity({ id: '2', type: 'LOCATION', recommended: true, text: 'Kadıköy' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('address')
    expect(groups[0].types.map((item) => item.type)).toEqual(['ADDRESS', 'LOCATION'])
    expect(groups[0].flattened).toBe(false)
  })

  it('lists postal codes under the address group', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'ADDRESS', recommended: true, text: 'Atatürk Cad. 12' }),
      entity({ id: '2', type: 'POSTAL_CODE', recommended: true, text: '34710' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('address')
    expect(groups[0].types.map((item) => item.type)).toEqual(['ADDRESS', 'POSTAL_CODE'])
  })

  it('lists case and decision numbers as file-number subcategories', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'CASE_NUMBER', recommended: true, text: '2024/12' }),
      entity({ id: '2', type: 'FILE_NUMBER', recommended: true, text: '2024/88' }),
      entity({ id: '3', type: 'DECISION_NUMBER', recommended: true, text: '2024/301' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('file')
    expect(groups[0].types.map((item) => item.type)).toEqual([
      'CASE_NUMBER',
      'FILE_NUMBER',
      'DECISION_NUMBER',
    ])
    expect(groups[0].flattened).toBe(false)
  })

  it('lists companies and organisations under the organisation group', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'COMPANY_NAME', recommended: true, text: 'Acme A.Ş.' }),
      entity({ id: '2', type: 'ORGANISATION', recommended: true, text: 'SGK' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('organisation')
    expect(groups[0].types.map((item) => item.type)).toEqual(['COMPANY_NAME', 'ORGANISATION'])
  })

  it('lists network findings under technical information, separate from contact', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'IP_ADDRESS', recommended: true, text: '1.1.1.1' }),
      entity({ id: '2', type: 'URL', recommended: true, text: 'https://example.test' }),
      entity({ id: '3', type: 'SYSTEM_URL', recommended: true, text: 'uyap.gov.tr' }),
      entity({ id: '4', type: 'PORT_NUMBER', recommended: true, text: '443' }),
      entity({ id: '5', type: 'EMAIL', recommended: true, text: 'a@b.test' }),
    ])
    expect(groups.map((group) => group.id)).toEqual(['contact', 'cyber'])
    expect(groups[0].types.map((item) => item.type)).toEqual(['EMAIL'])
    expect(groups[0].flattened).toBe(true)
    expect(groups[1].types.map((item) => item.type)).toEqual([
      'IP_ADDRESS',
      'URL',
      'SYSTEM_URL',
      'PORT_NUMBER',
    ])
  })

  it('lists bank, card, and account numbers under the banking group', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'IBAN', recommended: true, text: 'TR00' }),
      entity({ id: '2', type: 'CREDIT_CARD', recommended: true, text: '4111111111111111' }),
      entity({ id: '3', type: 'BANK_ACCOUNT', recommended: true, text: '12345678' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('banking')
    expect(groups[0].types.map((item) => item.type)).toEqual([
      'IBAN',
      'BANK_ACCOUNT',
      'CREDIT_CARD',
    ])
  })

  it('lists identity documents as detected identity subcategories', () => {
    const groups = groupCollapsedByFamily([
      entity({ id: '1', type: 'NATIONAL_ID', recommended: true, text: '12345678901' }),
      entity({ id: '2', type: 'PASSPORT_NUMBER', recommended: true, text: 'U12345678' }),
      entity({ id: '3', type: 'DATE_OF_BIRTH', recommended: true, text: '01.01.1990' }),
      entity({ id: '4', type: 'BIRTH_PLACE', recommended: true, text: 'Ankara' }),
      entity({ id: '5', type: 'SIGNATURE', recommended: true, text: 'imza' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe('identity')
    expect(groups[0].types.map((item) => item.type)).toEqual([
      'NATIONAL_ID',
      'PASSPORT_NUMBER',
      'DATE_OF_BIRTH',
      'BIRTH_PLACE',
      'SIGNATURE',
    ])
    expect(groups[0].flattened).toBe(false)
  })
})

describe('listRowId', () => {
  it('returns the collapsed representative for a related occurrence', () => {
    const entities = [
      entity({ id: '1', type: 'PERSON_NAME', recommended: true, resolved_entity_id: 'p' }),
      entity({ id: '2', type: 'PERSON_NAME', recommended: true, resolved_entity_id: 'p' }),
    ]
    expect(listRowId('2', entities)).toBe('1')
  })
})

describe('previewEntityValue', () => {
  it('renders category-aware live previews', () => {
    expect(previewEntityValue('Av. İrem Hazal Deveci', 'LAWYER_NAME', 'INITIALS', 'tr')).toBe('A.İ.H.D.')
    expect(previewEntityValue('Av. İrem Hazal Deveci', 'LAWYER_NAME', 'PLACEHOLDER', 'tr')).toBe('[AVUKAT_1]')
    expect(previewEntityValue('Mehmet Yılmaz', 'CLAIMANT_NAME', 'PLACEHOLDER', 'tr')).toBe('[DAVACI_1]')
    expect(previewEntityValue('Mehmet Yılmaz', 'PERSON_NAME', 'PLACEHOLDER', 'tr')).toBe('[KİŞİ_1]')
    expect(previewEntityValue('12345678901', 'NATIONAL_ID', 'PARTIAL_MASK', 'tr')).toBe('*******8901')
    expect(previewEntityValue('Mehmet', 'PERSON_NAME', 'KEEP', 'tr')).toBe('Mehmet')
    expect(previewEntityValue('12345678901', 'NATIONAL_ID', 'REDACT', 'tr')).toMatch(/^█+$/)
    expect(previewEntityValue('12345678901', 'NATIONAL_ID', 'REDACT', 'tr')).not.toContain('TCKN')
    expect(previewEntityValue('Mehmet Yılmaz', 'PERSON_NAME', 'INITIALS', 'tr')).toBe('M.Y.')
    expect(strategyResultExample('John Brown', 'PERSON_NAME', 'PLACEHOLDER', 'en')).toBe(
      'John Brown → [PERSON_1]',
    )
    expect(strategyResultExample('Mehmet Yılmaz', 'PERSON_NAME', 'PLACEHOLDER', 'tr')).toBe(
      'Mehmet Yılmaz → [KİŞİ_1]',
    )
    expect(strategyResultExample('John Brown', 'PERSON_NAME', 'REDACT', 'en')).toBe(
      `John Brown → ${'█'.repeat(10)}`,
    )
    expect(strategyResultExample('John Brown', 'PERSON_NAME', 'INITIALS', 'en')).toBe(
      'John Brown → J.B.',
    )
    expect(strategyResultExample('John Brown', 'PERSON_NAME', 'KEEP', 'en')).toBe(
      'John Brown → John Brown',
    )
    expect(strategyResultExample('0532 123 45 67', 'PHONE_NUMBER', 'PARTIAL_MASK', 'tr')).toBe(
      '0532 123 45 67 → 0532 *** ** 67',
    )
    expect(previewEntityValue('0532 555 44 11', 'PHONE_NUMBER', 'PARTIAL_MASK', 'tr')).toBe('0532 *** ** 11')
    expect(previewEntityValue('Gül Sokak No:18', 'ADDRESS', 'PLACEHOLDER', 'tr')).toBe('[ADRES_1]')
    expect(placeholderSamplesForTypes(['CLAIMANT_NAME', 'PERSON_NAME'], 'tr')).toEqual([
      '[DAVACI_1]',
      '[KİŞİ_1]',
    ])
    expect(previewEntityValue('14.03.2024', 'DATE', 'PLACEHOLDER', 'tr')).toBe('[TARİH]')
    expect(previewEntityValue('50.000 TL', 'MONEY_AMOUNT', 'PLACEHOLDER', 'tr')).toBe('[TUTAR]')
    expect(previewEntityValue('33110', 'POSTAL_CODE', 'PLACEHOLDER', 'tr')).toBe('[POSTA_KODU]')
    expect(previewEntityValue('Ankara 1. Asliye Hukuk Mahkemesi', 'COURT_NAME', 'PLACEHOLDER', 'tr')).toBe(
      'Ankara X Asliye Hukuk Mahkemesi',
    )
    expect(previewEntityValue('Seydişehir Asliye Hukuk Mahkemesi', 'COURT_NAME', 'PLACEHOLDER', 'tr')).toBe(
      '[MAHKEME_1]',
    )
    expect(previewEntityValue('Adana Nöbetçi Sulh Hukuk Mahkemesi', 'COURT_NAME', 'PLACEHOLDER', 'tr')).toBe(
      'Adana Nöbetçi Sulh Hukuk Mahkemesi',
    )
    expect(previewEntityValue('Kadıköy', 'LOCATION', 'PLACEHOLDER', 'tr')).toBe('[KONUM_1]')
    expect(previewEntityValue('19.05.1992', 'DATE_OF_BIRTH', 'PLACEHOLDER', 'tr')).toBe('[DOĞUM_TARİHİ_1]')
    expect(previewEntityValue('26/03/2009', 'DATE_OF_BIRTH', 'PARTIAL_MASK', 'tr')).toBe('**/**/2009')
    expect(previewEntityValue('26.03.2009', 'DATE_OF_BIRTH', 'PARTIAL_MASK', 'tr')).toBe('**.**.2009')
    expect(previewEntityValue('12 March 1985', 'DATE_OF_BIRTH', 'PARTIAL_MASK', 'en')).toBe('** March 1985')
    expect(previewEntityValue('Mersin 9. Asliye Ceza Mahkemesi', 'COURT_NAME', 'PARTIAL_MASK', 'tr')).toBe(
      'Mersin █. Asliye Ceza Mahkemesi',
    )
  })

  it('numbers distinct people separately and reuses the same person', () => {
    const mehmet = entity({
      id: 'm1',
      type: 'PERSON_NAME',
      recommended: true,
      text: 'Mehmet Yılmaz',
      start: 0,
      end: 13,
    })
    const ayse = entity({
      id: 'a1',
      type: 'PERSON_NAME',
      recommended: true,
      text: 'Ayşe Demir',
      start: 20,
      end: 30,
    })
    const mehmetAgain = entity({
      id: 'm2',
      type: 'PERSON_NAME',
      recommended: true,
      text: 'Mehmet Yılmaz',
      start: 40,
      end: 53,
    })
    const tokens = placeholderTokensByEntityId([mehmet, ayse, mehmetAgain], 'tr')
    expect(tokens.get('m1')).toBe('[KİŞİ_1]')
    expect(tokens.get('a1')).toBe('[KİŞİ_2]')
    expect(tokens.get('m2')).toBe('[KİŞİ_1]')
  })

  it('uses English tags from document language, not UI language', () => {
    const john = entity({
      id: 'j1',
      type: 'PERSON_NAME',
      recommended: true,
      text: 'John Smith',
      start: 0,
      end: 10,
    })
    expect(previewEntityValue('John Smith', 'PERSON_NAME', 'PLACEHOLDER', 'en', {
      entity: john,
      entities: [john],
    })).toBe('[PERSON_1]')
    expect(previewEntityValue('John Smith', 'PERSON_NAME', 'PLACEHOLDER', 'en')).toBe('[PERSON_1]')
    expect(placeholderSamplesForTypes(['CLAIMANT_NAME', 'CASE_NUMBER', 'DATE'], 'en')).toEqual([
      '[CLAIMANT_1]',
      '[CASE_NO_1]',
      '[DATE]',
    ])
  })

  it('prefers the authoritative backend placeholder token', () => {
    expect(
      previewEntityValue('Mehmet Yılmaz', 'PERSON_NAME', 'PLACEHOLDER', 'en', {
        placeholderToken: '[KİŞİ_1]',
      }),
    ).toBe('[KİŞİ_1]')
  })

  it('keeps family-local counters in local preview text', () => {
    const text = 'Mehmet Yılmaz ve Ayşe Demir'
    const people = [
      entity({
        id: 'm1',
        type: 'PERSON_NAME',
        recommended: true,
        recommended_strategy: 'PLACEHOLDER',
        text: 'Mehmet Yılmaz',
        start: 0,
        end: 13,
      }),
      entity({
        id: 'a1',
        type: 'PERSON_NAME',
        recommended: true,
        recommended_strategy: 'PLACEHOLDER',
        text: 'Ayşe Demir',
        start: 17,
        end: 27,
      }),
    ]
    const output = previewTransformLocal(
      text,
      people,
      {},
      { PERSON_NAME: 'PLACEHOLDER' },
      {},
      'tr',
    )
    expect(output).toContain('[KİŞİ_1]')
    expect(output).toContain('[KİŞİ_2]')
  })
})

describe('userOutputStrategiesFor', () => {
  it('does not expose removed model-assisted strategies', () => {
    const allowed = userOutputStrategiesFor('PERSON_NAME', catalog)
    expect(allowed).not.toContain('CONTEXTUAL_REWRITE')
    expect(allowed).not.toContain('ROLE_REPLACEMENT')
    expect(allowed).not.toContain('GENERALIZE')
  })

  it('does not offer a pseudonym method for person names', () => {
    const personCatalog: TransformCatalog = {
      ...catalog,
      strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'PARTIAL_MASK', 'KEEP'],
      categories: [
        ...catalog.categories,
        {
          category: 'PERSON_NAME',
          allowed_strategies: ['REDACT', 'INITIALS', 'PLACEHOLDER', 'KEEP'],
          recommended_strategy: 'PLACEHOLDER',
          generalization_options: [],
          supports_role_replacement: false,
        },
      ],
    }
    expect(userOutputStrategiesFor('PERSON_NAME', personCatalog)).toEqual([
      'REDACT',
      'INITIALS',
      'PLACEHOLDER',
      'KEEP',
    ])
  })
})

describe('manual redaction helpers', () => {
  it('identifies mask vs added text vs phrase items', () => {
    const mask = {
      id: 'm1',
      text: '[AREA 1-0-0]',
      page: 1,
      rectangles: [{ x0: 0, y0: 0, x1: 10, y1: 10 }],
    }
    const added = {
      id: 'm2',
      text: '[AREA 1-0-0]',
      page: 1,
      replacement: '[GİZLİ]',
      rectangles: [{ x0: 0, y0: 0, x1: 10, y1: 10 }],
    }
    const phrase = { text: 'Ayşe', page: 1 }
    expect(manualKindKey(mask)).toBe('mask')
    expect(manualKindKey(added)).toBe('text')
    expect(manualKindKey(phrase)).toBe('phrase')
    expect(manualItemId(phrase, 3)).toBe('manual:3')
    expect(findManualById([mask, added], 'm2')).toEqual(added)
  })
})

describe('exportRectanglesForEntity', () => {
  const item = entity({ id: 'n1', type: 'PERSON_NAME', recommended: true, page: 17 })
  const analysis: Analysis = {
    job_id: 'j',
    file_name: 'd.pdf',
    document_kind: 'PDF',
    page_count: 18,
    text: '',
    entities: [item],
    warnings: [],
    profile: 'GENERAL',
    page_spans: [
      {
        page: 17,
        width: 595,
        height: 842,
        spans: [
          {
            entity_id: 'n1',
            text: 'n1',
            type: 'PERSON_NAME',
            rectangles: [{ x0: 80, y0: 200, x1: 180, y1: 214 }],
          },
        ],
      },
    ],
  }

  it('uses reviewer overlay boxes when the entity has no stored rectangles', () => {
    expect(exportRectanglesForEntity(item, analysis, {})).toEqual([
      { x0: 80, y0: 200, x1: 180, y1: 214 },
    ])
  })

  it('prefers a user-resized box over overlay and entity rectangles', () => {
    const resized = [{ x0: 10, y0: 10, x1: 40, y1: 24 }]
    expect(
      exportRectanglesForEntity(
        { ...item, rectangles: [{ x0: 1, y0: 1, x1: 8, y1: 8 }] },
        analysis,
        { n1: resized },
      ),
    ).toEqual(resized)
  })
})

describe('initials font size', () => {
  it('reads a detected font size from entity attributes', () => {
    expect(
      detectedFontSize(
        entity({ id: '1', type: 'PERSON_NAME', recommended: true, attributes: { font_size: 12 } }),
      ),
    ).toBe(12)
    expect(detectedFontSize(entity({ id: '1', type: 'PERSON_NAME', recommended: true }))).toBeUndefined()
    expect(
      detectedFontSize(
        entity({ id: '1', type: 'PERSON_NAME', recommended: true, attributes: { font_size: 2 } }),
      ),
    ).toBeUndefined()
  })

  it('asks for a size control only when initials have no detected size', () => {
    const unnamed = entity({ id: '1', type: 'PERSON_NAME', recommended: true })
    const sized = entity({
      id: '2',
      type: 'PERSON_NAME',
      recommended: true,
      attributes: { font_size: 11 },
    })
    const phone = entity({ id: '3', type: 'PHONE_NUMBER', recommended: true })
    expect(
      needsInitialsSizeControl([unnamed], { '1': 'REDACT' }, { PERSON_NAME: 'INITIALS' }, {}),
    ).toBe(true)
    expect(
      needsInitialsSizeControl([sized], { '2': 'REDACT' }, { PERSON_NAME: 'INITIALS' }, {}),
    ).toBe(false)
    expect(
      needsInitialsSizeControl([phone], { '3': 'REDACT' }, { PHONE_NUMBER: 'REDACT' }, {}),
    ).toBe(false)
    expect(
      needsInitialsSizeControl([unnamed], { '1': 'KEEP' }, { PERSON_NAME: 'INITIALS' }, {}),
    ).toBe(false)
  })
})

describe('findDocumentPhraseHits', () => {
  it('returns every line that contains the phrase with page and offset', () => {
    const pages = [
      'Birinci sayfada Ahmet geçer.\nBaşka bir satır.',
      'İkinci sayfada ahmet tekrar geçer ve Ahmet de var.',
    ]
    const hits = findDocumentPhraseHits(pages, 'Ahmet')
    expect(hits.length).toBe(3)
    expect(hits[0]?.page).toBe(0)
    expect(hits[0]?.line).toContain('Ahmet')
    expect(hits[1]?.page).toBe(1)
    expect(hits[2]?.page).toBe(1)
    expect(hits.map((hit) => hit.start).length).toBe(new Set(hits.map((hit) => hit.start)).size)
  })

  it('keeps original offsets when a line has Turkish dotted I before the hit', () => {
    const line = 'İtiraz: Keşif harcı ödendi.'
    const hits = findDocumentPhraseHits([line], 'keşif harcı')
    expect(hits).toHaveLength(1)
    expect(line.slice(hits[0]?.start ?? 0, hits[0]?.end ?? 0).toLocaleLowerCase('tr')).toBe(
      'keşif harcı',
    )
  })
})

describe('customTermTargetIds', () => {
  it('prefers newly added user terms and inflected text', () => {
    const prior = entity({
      id: 'old',
      type: 'PERSON_NAME',
      detector: 'TR_NAME',
      text: 'Ayşe Demir',
      start: 0,
      recommended: true,
    })
    const added = entity({
      id: 'new',
      type: 'OTHER_IDENTIFIER',
      detector: 'USER_DEFINED_TERM',
      text: "Ayşe Demir'in",
      start: 20,
      recommended: false,
      attributes: { term: 'Ayşe Demir' },
    })
    expect(
      customTermTargetIds(
        [prior, added],
        { value: 'Ayşe Demir', category: 'OTHER_IDENTIFIER' },
        ['old'],
      ),
    ).toEqual(['new'])
  })

  it('masks an existing finding of the selected type when starts match', () => {
    const person = entity({
      id: 'p1',
      type: 'PERSON_NAME',
      detector: 'TR_NAME',
      text: 'Ayşe Demir',
      start: 4,
      recommended: false,
    })
    expect(
      customTermTargetIds(
        [person],
        { value: 'Ayşe Demir', category: 'PERSON_NAME', starts: [4] },
        ['p1'],
      ),
    ).toEqual(['p1'])
  })

  it('does not overlay a longer existing span that merely contains the search start', () => {
    const lawyer = entity({
      id: 'lawyer',
      type: 'LAWYER_NAME',
      detector: 'TR_LEGAL_PARTY',
      text: 'Av. İREM HAZAL DEVECİ',
      start: 0,
      recommended: true,
    })
    expect(
      customTermTargetIds(
        [lawyer],
        { value: 'İrem Hazal Deveci', category: 'PERSON_NAME', starts: [4] },
        ['lawyer'],
      ),
    ).toEqual([])
  })
})

