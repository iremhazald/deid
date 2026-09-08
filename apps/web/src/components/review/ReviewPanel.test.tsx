import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { ComponentProps } from 'react'
import { ReviewPanel } from './ReviewPanel'
import type { Analysis, TransformCatalog } from '../../state/types'
import tr from '../../locales/tr.json'
import en from '../../locales/en.json'

const lookup = (
  locale: typeof tr,
  key: string,
  options?: Record<string, unknown>,
) => {
  const parts = key.split('.')
  let current: unknown = locale
  for (const part of parts) {
    if (typeof current !== 'object' || current === null || !(part in current)) {
      if (options?.count != null && key.includes('detectionsFound')) {
        return String(locale.detectionsFound).replace('{{count}}', String(options.count))
      }
      return key
    }
    current = (current as Record<string, unknown>)[part]
  }
  if (typeof current !== 'string') return key
  return current.replace(/\{\{(\w+)\}\}/g, (_, name: string) => String(options?.[name] ?? ''))
}

const t = (key: string, options?: Record<string, unknown>) => lookup(tr, key, options)
const tEn = (key: string, options?: Record<string, unknown>) => lookup(en, key, options)

const catalog: TransformCatalog = {
  strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
  categories: [
    {
      category: 'EMAIL',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'REDACT',
      generalization_options: [],
      supports_role_replacement: false,
    },
    {
      category: 'PERSON_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: true,
    },
  ],
  role_labels: { tr: {}, en: {} },
  secure_pdf_strategies: ['REDACT'],
}

function analysis(partial: Partial<Analysis> = {}): Analysis {
  return {
    job_id: 'job',
    file_name: 'letter.txt',
    document_kind: 'TEXT',
    page_count: 1,
    text: 'Ayşe Demir, ayse.demir@example.test',
    entities: [],
    warnings: [],
    profile: 'GENERAL',
    analysis_status: 'COMPLETE',
    ai_status: 'SUCCESS',
    ...partial,
  }
}

const noop = () => undefined

function renderPanel(overrides: Partial<ComponentProps<typeof ReviewPanel>> = {}) {
  return renderToStaticMarkup(
    <ReviewPanel
      analysis={analysis()}
      decisions={{}}
      categoryDefaults={{}}
      entityStrategies={{}}
      catalog={catalog}
      activeId={null}
      profile="GENERAL"
      outputFormat="TXT"
      manual={[]}
      busy={false}
      language="tr"
      t={t}
      onSelect={noop}
      onDecision={noop}
      onBulk={noop}
      onProfileChange={noop}
      onCategoryDefault={noop}
      onEntityStrategy={noop}
      onOutputFormatChange={noop}
      onManualChange={noop}
      {...overrides}
    />,
  )
}

describe('ReviewPanel safety and review UX', () => {
  it('shows a failed empty state and does not treat zero detections as safe', () => {
    const html = renderPanel({
      analysis: analysis({
        analysis_status: 'FAILED',
        warnings: [],
        entities: [],
      }),
    })
    expect(html).toContain(tr.emptyDetections)
    expect(html).toContain(tr.emptyPartialHint)
    expect(html).not.toContain(tr.emptyCompleteHint)
  })

  it('keeps the category list visible when a finding is selected', () => {
    const person = {
      id: 'e1',
      text: 'Ayşe Demir',
      type: 'PERSON_NAME',
      start: 0,
      end: 10,
      page: 0,
      detector: 'AI_CONTEXTUAL',
      method: 'AI' as const,
      validated: true,
      recommended: true,
      role: 'Davacı',
    }
    const html = renderPanel({
      analysis: analysis({ entities: [person] }),
      activeId: 'e1',
      decisions: { e1: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER' },
    })
    expect(html).not.toContain(tr.workspace.benchTitle)
    expect(html).toContain(t('workspace.actionableCount', { count: 1 }))
    expect(html).toContain('Ayşe Demir')
    expect(html).toContain('finding-row on')
    expect(html).toContain('finding-method-panel')
    expect(html).toContain(tr.workspace.paneDetections)
    expect(html).not.toContain(tr.howToAppear)
  })

  it('splits the workbench into detections, unmasked, and custom panes', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [{
          id: 'e1',
          text: 'Ayşe Demir',
          type: 'PERSON_NAME',
          start: 0,
          end: 10,
          page: 0,
          detector: 'AI_CONTEXTUAL',
          method: 'AI',
          validated: true,
          recommended: true,
        }],
      }),
      decisions: { e1: 'REDACT' },
      onAddCustomTerm: () => undefined,
    })
    expect(html).toContain(tr.workspace.paneDetections)
    expect(html).toContain(tr.workspace.paneKept)
    expect(html).toContain(tr.workspace.paneCustom)
    expect(html).not.toContain(t('workspace.showPreserved', { count: 0 }))
  })

  it('does not mark custom detection as unavailable when a callback is wired', () => {
    const html = renderPanel({
      onAddCustomTerm: () => undefined,
    })
    expect(html).toContain(tr.workspace.paneCustom)
    expect(html).not.toContain(tr.workspace.customSearchUnavailable)
    expect(html).not.toContain(tr.manual)
  })

  it('renders categories as a compact index rather than stacked accordion cards', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          {
            id: 'e1',
            text: 'Ayşe Demir',
            type: 'PERSON_NAME',
            start: 0,
            end: 10,
            page: 0,
            detector: 'AI_CONTEXTUAL',
            method: 'AI',
            validated: true,
            recommended: true,
          },
          {
            id: 'n1',
            text: '12345678901',
            type: 'NATIONAL_ID',
            start: 12,
            end: 23,
            page: 0,
            detector: 'TCKN',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { e1: 'REDACT', n1: 'REDACT' },
    })
    expect(html).toContain('category-item')
    expect(html).toContain('category-glyph')
    expect(html).toContain('accent-person')
    expect(html).toContain('accent-id')
    expect(html).toContain('review-pane-count')
    expect(html).toContain(tr.workspace.paneDetections)
    expect(html).toContain(tr.workspace.paneKept)
    expect(html).toContain(tr.workspace.paneCustom)
    expect(html).not.toContain(tr.workspace.moreOptions)
  })

  it('keeps category dropdowns closed on the all filter', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          {
            id: 'e1',
            text: 'Ayşe Demir',
            type: 'PERSON_NAME',
            start: 0,
            end: 10,
            page: 0,
            detector: 'AI_CONTEXTUAL',
            method: 'AI',
            validated: true,
            recommended: true,
          },
          {
            id: 'n1',
            text: '12345678901',
            type: 'NATIONAL_ID',
            start: 12,
            end: 23,
            page: 0,
            detector: 'TCKN',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { e1: 'REDACT', n1: 'REDACT' },
    })
    expect(html).toContain('aria-expanded="false"')
    expect(html).not.toContain('aria-expanded="true"')
    expect(html).toContain(tr.categories.PERSON_NAME)
    expect(html).toContain(tr.presentation.groups.identity)
    expect(html).toContain('Ayşe Demir')
    expect(html).toContain('12345678901')
  })

  it('keeps hide totals in the action bar instead of the panel header', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [{
          id: 'e1',
          text: 'Ayşe Demir',
          type: 'PERSON_NAME',
          start: 0,
          end: 10,
          page: 0,
          detector: 'AI_CONTEXTUAL',
          method: 'AI',
          validated: true,
          recommended: true,
        }],
      }),
      decisions: { e1: 'REDACT' },
    })
    expect(html).not.toContain(t('detectionsFound', { count: 1 }))
    expect(html).not.toContain(t('workspace.reviewedCount', { count: 0 }))
    expect(html).not.toContain(t('workspace.pendingCount', { count: 1 }))
    expect(html).not.toContain(tr.workspace.validatedGroup)
    expect(html).not.toContain(tr.workspace.reviewGroup)
  })

  it('treats a checked finding as information that will be hidden', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [{
          id: 'e1',
          text: 'Ayşe Demir',
          type: 'PERSON_NAME',
          start: 0,
          end: 10,
          page: 0,
          detector: 'AI_CONTEXTUAL',
          method: 'AI',
          validated: true,
          recommended: true,
        }],
      }),
      decisions: { e1: 'REDACT' },
    })
    expect(html).toContain('type="checkbox"')
    expect(html).toContain('checked')
    expect(html).toContain(t('workspace.hideCheckbox', { name: 'Ayşe Demir' }))
    expect(html).not.toContain('>REDACT<')
  })

  it('does not show a manual-add or more-options block in the detections pane', () => {
    const html = renderPanel()
    expect(html).not.toContain(tr.manual)
    expect(html).not.toContain(tr.workspace.moreOptions)
    expect(html).not.toContain('type="number"')
  })

  it('shows drawn masks and added text in the detections list', () => {
    const html = renderPanel({
      analysis: analysis({
        document_kind: 'PDF',
        entities: [],
      }),
      manual: [
        {
          id: 'm-mask',
          text: '[AREA 1-10-20]',
          page: 1,
          rectangles: [{ x0: 10, y0: 20, x1: 120, y1: 48 }],
          category: 'ADDRESS',
        },
        {
          id: 'm-text',
          text: '[AREA 1-90-90]',
          page: 2,
          replacement: '[GİZLİ]',
          rectangles: [{ x0: 90, y0: 90, x1: 180, y1: 130 }],
        },
      ],
    })
    expect(html).toContain(tr.workspace.family.manual)
    expect(html).toContain(tr.workspace.manualMaskLabel)
    expect(html).toContain('[GİZLİ]')
    expect(html).toContain(tr.categories.ADDRESS)
    expect(html).toContain(tr.workspace.toolAddText)
    expect(html).not.toContain(t('detectionsFound', { count: 2 }))
    expect(html).not.toContain(tr.emptyDetections)
  })

  it('does not mix deep-scan or purpose controls into a standard review', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [{
          id: 'e1',
          text: 'Ayşe Demir',
          type: 'PERSON_NAME',
          start: 0,
          end: 10,
          page: 0,
          detector: 'LEGAL_PARTY',
          method: 'DETERMINISTIC',
          validated: true,
          recommended: true,
        }],
      }),
      decisions: { e1: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER' },
    })
    expect(html).toContain(t('workspace.actionableCount', { count: 1 }))
    expect(html).toContain(tr.workspace.paneDetections)
    expect(html).toContain(tr.categories.PERSON_NAME)
    expect(html).not.toContain(tr.preset.label)
    expect(html).not.toContain(tr.preset.ANONYMIZED)
    expect(html).not.toContain('Derin tarama')
    expect(html).not.toContain('Deep scan')
    expect(html).not.toContain('KVKK')
    expect(html).not.toContain('GDPR Review')
    expect(html).not.toContain('Takma ad')
    expect(html).not.toContain('PSEUDONYM')
  })

  it('keeps a local-context review free of KVKK/GDPR review actions', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'LOCAL_CONTEXT',
        entities: [{
          id: 'e1',
          text: 'Ayşe Demir',
          type: 'PERSON_NAME',
          start: 0,
          end: 10,
          page: 0,
          detector: 'LEGAL_PARTY',
          method: 'DETERMINISTIC',
          validated: true,
          recommended: true,
        }],
      }),
      decisions: { e1: 'REDACT' },
    })
    expect(html).toContain(t('workspace.actionableCount', { count: 1 }))
    expect(html).not.toContain('Derinlemesine Tarama')
    expect(html).not.toContain('Deep Scan')
  })

  it('lists first and last names with person names in the detection panel', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'f1',
            text: 'Ayşe',
            type: 'FIRST_NAME',
            start: 0,
            end: 4,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
          {
            id: 'l1',
            text: 'Demir',
            type: 'LAST_NAME',
            start: 5,
            end: 10,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { f1: 'REDACT', l1: 'REDACT' },
    })
    expect(html).toContain(tr.categories.PERSON_NAME)
    expect(html).toContain('Ayşe')
    expect(html).toContain('Demir')
    expect(html).not.toContain(tr.categories.FIRST_NAME)
    expect(html).not.toContain(tr.categories.LAST_NAME)
  })

  it('lists locations with addresses in the detection panel', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'a1',
            text: 'Atatürk Cad. 12',
            type: 'ADDRESS',
            start: 0,
            end: 15,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
          {
            id: 'l1',
            text: 'Kadıköy',
            type: 'LOCATION',
            start: 16,
            end: 23,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { a1: 'REDACT', l1: 'REDACT' },
    })
    expect(html).toContain(tr.categories.ADDRESS)
    expect(html).toContain(tr.categories.LOCATION)
    expect(html).toContain('Atatürk Cad. 12')
    expect(html).toContain('Kadıköy')
    expect(html).toContain(tr.presentation.groups.address)
  })

  it('lists case and decision numbers with file numbers in the detection panel', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'c1',
            text: '2024/12',
            type: 'CASE_NUMBER',
            start: 0,
            end: 7,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
          {
            id: 'd1',
            text: '2024/301',
            type: 'DECISION_NUMBER',
            start: 8,
            end: 16,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { c1: 'REDACT', d1: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.file)
    expect(html).toContain(tr.categories.CASE_NUMBER)
    expect(html).toContain(tr.categories.DECISION_NUMBER)
    expect(html).toContain('2024/12')
    expect(html).toContain('2024/301')
  })

  it('lists companies and organisations under organisations in the detection panel', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'co1',
            text: 'Acme A.Ş.',
            type: 'COMPANY_NAME',
            start: 0,
            end: 9,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
          {
            id: 'or1',
            text: 'SGK',
            type: 'ORGANISATION',
            start: 10,
            end: 13,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { co1: 'REDACT', or1: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.organisation)
    expect(html).toContain(tr.categories.COMPANY_NAME)
    expect(html).toContain(tr.categories.ORGANISATION)
    expect(html).toContain('Acme A.Ş.')
    expect(html).toContain('SGK')
  })

  it('lists network findings under cyber information in the detection panel', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'ip1',
            text: '1.1.1.1',
            type: 'IP_ADDRESS',
            start: 0,
            end: 7,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
          {
            id: 'u1',
            text: 'https://example.test',
            type: 'URL',
            start: 8,
            end: 28,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { ip1: 'REDACT', u1: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.cyber)
    expect(html).toContain(tr.categories.IP_ADDRESS)
    expect(html).toContain(tr.categories.URL)
    expect(html).toContain('1.1.1.1')
    expect(html).toContain('https://example.test')
  })

  it('lists bank, card, and account numbers under banking information', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'b1',
            text: 'TR00',
            type: 'IBAN',
            start: 0,
            end: 4,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
          {
            id: 'c1',
            text: '4111111111111111',
            type: 'CREDIT_CARD',
            start: 5,
            end: 21,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { b1: 'REDACT', c1: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.banking)
    expect(html).toContain(tr.categories.IBAN)
    expect(html).toContain(tr.categories.CREDIT_CARD)
    expect(html).toContain('TR00')
    expect(html).toContain('4111111111111111')
  })

  it('lists postal codes with addresses in the detection panel', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'p1',
            text: '34710',
            type: 'POSTAL_CODE',
            start: 0,
            end: 5,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { p1: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.address)
    expect(html).toContain('34710')
    expect(html).not.toContain('subcategory-toggle')
  })

  it('lists identity, passport, birth, and signature findings under identity information', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'n1',
            text: '12345678901',
            type: 'NATIONAL_ID',
            start: 0,
            end: 11,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
          {
            id: 's1',
            text: 'imza',
            type: 'SIGNATURE',
            start: 12,
            end: 16,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { n1: 'REDACT', s1: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.identity)
    expect(html).toContain(tr.categories.NATIONAL_ID)
    expect(html).toContain(tr.categories.SIGNATURE)
    expect(html).toContain('12345678901')
    expect(html).toContain('imza')
  })

  it('lists lawyer names under personal names in the detection panel', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'w1',
            text: 'Hasan Koç',
            type: 'LAWYER_NAME',
            start: 0,
            end: 9,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { w1: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.person)
    expect(html).toContain(tr.categories.LAWYER_NAME)
    expect(html).toContain('Hasan Koç')
    expect(html).not.toContain(tr.presentation.groups.court)
  })

  it('lists judge names under personal names instead of court information', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'j1',
            text: 'Ayşe Yılmaz',
            type: 'JUDGE_NAME',
            start: 0,
            end: 11,
            page: 0,
            detector: 'TR_JUDICIAL_ROSTER',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { j1: 'REDACT' },
    })
    expect(html).toContain(tr.workspace.paneDetections)
    expect(html).toContain(tr.presentation.groups.person)
    expect(html).toContain(tr.categories.JUDGE_NAME)
    expect(html).toContain('Ayşe Yılmaz')
    expect(html).not.toContain(tr.presentation.groups.court)
  })

  it('nests type groups under a family and uses output method labels', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [
          {
            id: 'e1',
            text: '12345678901',
            type: 'NATIONAL_ID',
            start: 0,
            end: 11,
            page: 0,
            detector: 'TCKN',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { e1: 'REDACT' },
      categoryDefaults: { NATIONAL_ID: 'REDACT' },
    })
    expect(html).toContain(tr.workspace.paneDetections)
    expect(html).toContain(tr.presentation.groups.identity)
    expect(html).toContain(tr.workspace.strategyRedact)
    expect(html).not.toContain('>REDACT<')
  })

  it('shows a punto control when person names use initials without a detected size', () => {
    const html = renderPanel({
      analysis: analysis({
        document_kind: 'PDF',
        text: 'Ayşe Demir',
        entities: [
          {
            id: 'p1',
            text: 'Ayşe Demir',
            type: 'PERSON_NAME',
            start: 0,
            end: 10,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
          },
        ],
      }),
      decisions: { p1: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'INITIALS' },
      initialsFontSize: 11,
      onInitialsFontSizeChange: noop,
    })
    expect(html).toContain(tr.workspace.initialsFontSize)
    expect(html).toContain(tr.workspace.initialsFontSizeHelp)
  })

  it('hides the punto control when the document font size is known', () => {
    const html = renderPanel({
      analysis: analysis({
        document_kind: 'PDF',
        text: 'Ayşe Demir',
        entities: [
          {
            id: 'p1',
            text: 'Ayşe Demir',
            type: 'PERSON_NAME',
            start: 0,
            end: 10,
            page: 0,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
            attributes: { font_size: 12 },
          },
        ],
      }),
      decisions: { p1: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'INITIALS' },
      initialsFontSize: 11,
      onInitialsFontSizeChange: noop,
    })
    expect(html).not.toContain(tr.workspace.initialsFontSize)
  })

  it('does not ask for document layout or output preview on the review panel', () => {
    const html = renderPanel({
      analysis: analysis({ document_kind: 'PDF', file_name: 'letter.pdf' }),
    })
    expect(html).not.toContain('Belge düzeni')
    expect(html).not.toContain('Temiz belge oluştur')
    expect(html).not.toContain(tr.workspace.previewOutput)
    expect(html).not.toContain(tr.apply)
  })

  it('keeps KEEP findings visible in Findings while still listing them in the unmasked audit view', () => {
    const entities = [
      {
        id: 'court',
        text: 'EMPLOYMENT TRIBUNALS',
        type: 'COURT_NAME',
        start: 0,
        end: 21,
        page: 0,
        detector: 'EN_COURT',
        method: 'DETERMINISTIC' as const,
        validated: true,
        recommended: false,
        recommended_strategy: 'KEEP' as const,
      },
      {
        id: 'co',
        text: 'Wechseln Limited',
        type: 'COMPANY_NAME',
        start: 22,
        end: 38,
        page: 0,
        detector: 'EN_COMPANY',
        method: 'DETERMINISTIC' as const,
        validated: true,
        recommended: false,
        recommended_strategy: 'KEEP' as const,
      },
      {
        id: 'salon',
        text: 'Andrew Hill Salon',
        type: 'COMPANY_NAME',
        start: 39,
        end: 56,
        page: 0,
        detector: 'EN_COMPANY',
        method: 'DETERMINISTIC' as const,
        validated: true,
        recommended: false,
        recommended_strategy: 'KEEP' as const,
      },
      {
        id: 'lauren',
        text: 'Lauren De Lacey',
        type: 'PERSON_NAME',
        start: 57,
        end: 72,
        page: 0,
        detector: 'EN_PARTY',
        method: 'DETERMINISTIC' as const,
        validated: true,
        recommended: true,
        recommended_strategy: 'REDACT' as const,
      },
      {
        id: 'leach',
        text: 'D Leach',
        type: 'PERSON_NAME',
        start: 73,
        end: 80,
        page: 0,
        detector: 'EN_PARTY',
        method: 'DETERMINISTIC' as const,
        validated: true,
        recommended: true,
        recommended_strategy: 'REDACT' as const,
      },
      {
        id: 'osborne',
        text: 'J Osborne',
        type: 'PERSON_NAME',
        start: 81,
        end: 90,
        page: 0,
        detector: 'EN_PARTY',
        method: 'DETERMINISTIC' as const,
        validated: true,
        recommended: true,
        recommended_strategy: 'REDACT' as const,
      },
      {
        id: 'case',
        text: '1400945/2017',
        type: 'CASE_NUMBER',
        start: 91,
        end: 103,
        page: 0,
        detector: 'EN_CASE',
        method: 'DETERMINISTIC' as const,
        validated: true,
        recommended: true,
        recommended_strategy: 'REDACT' as const,
      },
    ]
    const decisions = {
      court: 'KEEP' as const,
      co: 'KEEP' as const,
      salon: 'KEEP' as const,
      lauren: 'REDACT' as const,
      leach: 'REDACT' as const,
      osborne: 'REDACT' as const,
      case: 'REDACT' as const,
    }
    const findings = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities,
      }),
      decisions,
      categoryDefaults: {
        COURT_NAME: 'KEEP',
        COMPANY_NAME: 'KEEP',
        PERSON_NAME: 'REDACT',
        CASE_NUMBER: 'REDACT',
      },
    })
    expect(findings).toContain(t('workspace.actionableCount', { count: 4 }))
    expect(findings).toContain(tr.workspace.paneKept)
    expect(findings).toContain('Lauren De Lacey')
    expect(findings).toContain('D Leach')
    expect(findings).toContain('J Osborne')
    expect(findings).toContain('1400945/2017')
    expect(findings).toContain('EMPLOYMENT TRIBUNALS')
    expect(findings).toContain('Wechseln Limited')
    expect(findings).toContain('Andrew Hill Salon')
    expect(findings).toContain(tr.workspace.strategyKeep)
    expect(findings).not.toContain(t('detectionsFound', { count: 7 }))

    const unmasked = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities,
      }),
      decisions,
      categoryDefaults: {
        COURT_NAME: 'KEEP',
        COMPANY_NAME: 'KEEP',
        PERSON_NAME: 'REDACT',
        CASE_NUMBER: 'REDACT',
      },
      showPreserved: true,
    })
    expect(unmasked).toContain('EMPLOYMENT TRIBUNALS')
    expect(unmasked).toContain('Wechseln Limited')
    expect(unmasked).toContain('Andrew Hill Salon')
    expect(unmasked).toContain('is-preserved')
    expect(unmasked).toContain(t('workspace.actionableCount', { count: 4 }))
  })

  it('moves an overridden KEEP finding into the actionable set', () => {
    const html = renderPanel({
      analysis: analysis({
        detection_mode: 'RULES_ONLY',
        entities: [{
          id: 'court',
          text: 'EMPLOYMENT TRIBUNALS',
          type: 'COURT_NAME',
          start: 0,
          end: 21,
          page: 0,
          detector: 'EN_COURT',
          method: 'DETERMINISTIC',
          validated: true,
          recommended: false,
          recommended_strategy: 'KEEP',
        }],
      }),
      decisions: { court: 'REDACT' },
      categoryDefaults: { COURT_NAME: 'KEEP' },
      entityStrategies: { court: 'REDACT' },
    })
    expect(html).toContain('EMPLOYMENT TRIBUNALS')
    expect(html).toContain(t('workspace.actionableCount', { count: 1 }))
    expect(html).toContain(tr.workspace.paneKept)
    expect(html).toContain(tr.categories.COURT_NAME)
  })

  it('shows a compact possible-match card with merge and keep-separate actions', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          {
            id: 'e1',
            text: 'John Brown',
            type: 'PERSON_NAME',
            start: 0,
            end: 10,
            page: 1,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
            placeholder_token: '[KİŞİ_1]',
          },
          {
            id: 'e2',
            text: 'Mr Brown',
            type: 'PERSON_NAME',
            start: 20,
            end: 28,
            page: 6,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
            placeholder_token: '[KİŞİ_2]',
          },
        ],
        possible_matches: [
          {
            id: 'pm_1',
            members: [
              {
                canonical_id: 'c1',
                entity_ids: ['e1'],
                text: 'John Brown',
                pages: [1],
                placeholder_token: '[KİŞİ_1]',
              },
              {
                canonical_id: 'c2',
                entity_ids: ['e2'],
                text: 'Mr Brown',
                pages: [6, 10],
                placeholder_token: '[KİŞİ_2]',
              },
            ],
          },
        ],
      }),
      decisions: { e1: 'REDACT', e2: 'REDACT' },
    })
    expect(html).toContain(tr.workspace.possibleMatchTitle)
    expect(html).toContain(tr.workspace.possibleMatchHint)
    expect(html).toContain(tr.workspace.possibleMatchMerge)
    expect(html).toContain(tr.workspace.possibleMatchKeepSeparate)
    expect(html).toContain('John Brown')
    expect(html).toContain('Mr Brown')
  })

  it('renders Turkish possible-match copy for honorific surname pairs', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          {
            id: 'e1',
            text: 'Mehmet Yılmaz',
            type: 'PERSON_NAME',
            start: 0,
            end: 13,
            page: 1,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
            placeholder_token: '[KİŞİ_1]',
          },
          {
            id: 'e2',
            text: 'Bay Yılmaz',
            type: 'PERSON_NAME',
            start: 20,
            end: 30,
            page: 6,
            detector: 'TEST',
            method: 'DETERMINISTIC',
            validated: true,
            recommended: true,
            placeholder_token: '[KİŞİ_2]',
          },
        ],
        possible_matches: [
          {
            id: 'pm_tr',
            members: [
              {
                canonical_id: 'c1',
                entity_ids: ['e1'],
                text: 'Mehmet Yılmaz',
                pages: [1],
                placeholder_token: '[KİŞİ_1]',
              },
              {
                canonical_id: 'c2',
                entity_ids: ['e2'],
                text: 'Bay Yılmaz',
                pages: [6, 10],
                placeholder_token: '[KİŞİ_2]',
              },
            ],
          },
        ],
      }),
      decisions: { e1: 'REDACT', e2: 'REDACT' },
    })
    expect(html).toContain(tr.workspace.possibleMatchTitle)
    expect(html).toContain(tr.workspace.possibleMatchHint)
    expect(html).toContain(tr.workspace.possibleMatchMerge)
    expect(html).toContain(tr.workspace.possibleMatchKeepSeparate)
    expect(html).toContain('Mehmet Yılmaz')
    expect(html).toContain('Bay Yılmaz')
    expect(html).toContain(t('workspace.possibleMatchPages', { pages: '7, 11' }))
  })
})

function personEntity(
  id: string,
  text: string,
  extra: Record<string, unknown> = {},
) {
  return {
    id,
    text,
    type: 'PERSON_NAME',
    start: 0,
    end: text.length,
    page: 0,
    detector: 'TEST',
    method: 'DETERMINISTIC' as const,
    validated: true,
    recommended: true,
    ...extra,
  }
}

describe('transformation method UX', () => {
  it('uses result-oriented TR method labels', () => {
    expect(tr.workspace.strategyRedact).toBe('Tamamen gizle')
    expect(tr.workspace.strategyInitials).toBe('Baş harflerle göster')
    expect(tr.workspace.strategyPlaceholder).toBe('Etiketle değiştir')
    expect(tr.workspace.strategyKeep).toBe('Belgede bırak')
    expect(tr.workspace.strategyPartial).toBe('Kısmen gizle')
    expect(tr.workspace.howFindingsAppear).toBe('Bu tespitler nasıl gösterilsin?')
    expect(tr.workspace.strategyPlaceholder).not.toContain('Sıralı')
  })

  it('uses result-oriented EN method labels', () => {
    expect(en.workspace.strategyRedact).toBe('Hide completely')
    expect(en.workspace.strategyInitials).toBe('Show initials')
    expect(en.workspace.strategyPlaceholder).toBe('Replace with label')
    expect(en.workspace.strategyKeep).toBe('Keep in document')
    expect(en.workspace.strategyPartial).toBe('Mask partially')
    expect(en.workspace.howFindingsAppear).toBe('How should these findings appear?')
  })

  it('shows TR labels and a document-language English placeholder example', () => {
    const html = renderPanel({
      language: 'en',
      catalog: {
        ...catalog,
        strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
        categories: catalog.categories.map((item) =>
          item.category === 'PERSON_NAME'
            ? {
                ...item,
                allowed_strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
              }
            : item,
        ),
      },
      analysis: analysis({
        entities: [personEntity('p1', 'John Brown')],
      }),
      decisions: { p1: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER' },
    })
    expect(html).toContain(tr.workspace.howFindingsAppear)
    expect(html).toContain(tr.workspace.strategyPlaceholder)
    expect(html).toContain(tr.workspace.strategyRedact)
    expect(html).toContain(tr.workspace.strategyInitials)
    expect(html).toContain(tr.workspace.strategyKeep)
    expect(html).toContain('John Brown → [PERSON_1]')
    expect(html).toContain('John Brown → J.B.')
    expect(html).not.toContain('[KİŞİ_1]')
    expect(html).not.toContain('Sıralı etiketle değiştir')
  })

  it('shows EN labels and a document-language Turkish placeholder example', () => {
    const html = renderPanel({
      t: tEn,
      language: 'tr',
      catalog: {
        ...catalog,
        strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
        categories: catalog.categories.map((item) =>
          item.category === 'PERSON_NAME'
            ? {
                ...item,
                allowed_strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
              }
            : item,
        ),
      },
      analysis: analysis({
        entities: [personEntity('p1', 'Mehmet Yılmaz')],
      }),
      decisions: { p1: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER' },
    })
    expect(html).toContain(en.workspace.howFindingsAppear)
    expect(html).toContain(en.workspace.strategyPlaceholder)
    expect(html).toContain(en.workspace.strategyRedact)
    expect(html).toContain(en.workspace.strategyInitials)
    expect(html).toContain(en.workspace.strategyKeep)
    expect(html).toContain('Mehmet Yılmaz → [KİŞİ_1]')
    expect(html).toContain('Mehmet Yılmaz → M.Y.')
    expect(html).not.toContain('[PERSON_1]')
  })

  it('keeps a KEEP category visible and editable in the current Findings view', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          personEntity('p1', 'John Brown', { start: 0, end: 10 }),
          personEntity('p2', 'Jane Smith', { start: 12, end: 22 }),
        ],
      }),
      decisions: { p1: 'KEEP', p2: 'KEEP' },
      categoryDefaults: { PERSON_NAME: 'KEEP' },
    })
    expect(html).toContain(tr.categories.PERSON_NAME)
    expect(html).toContain('John Brown')
    expect(html).toContain('Jane Smith')
    expect(html).toContain(tr.workspace.strategyKeep)
    expect(html).toContain(tr.workspace.strategyPlaceholder)
    expect(html).toContain(tr.workspace.howFindingsAppear)
    expect(html).toContain('category-toggle-count">2<')
    expect(html).toContain('John Brown → John Brown')
    expect(html).toContain(tr.workspace.paneDetections)
    expect(html).not.toContain(tr.workspace.keptEmpty)
  })

  it('hides unsupported strategies for a category', () => {
    const html = renderPanel({
      catalog: {
        ...catalog,
        categories: [
          {
            category: 'EMAIL',
            allowed_strategies: ['REDACT', 'KEEP'],
            recommended_strategy: 'REDACT',
            generalization_options: [],
            supports_role_replacement: false,
          },
          {
            category: 'SIGNATURE',
            allowed_strategies: ['REDACT', 'KEEP'],
            recommended_strategy: 'REDACT',
            generalization_options: [],
            supports_role_replacement: false,
          },
        ],
      },
      analysis: analysis({
        entities: [{
          id: 'e1',
          text: 'ayse@example.test',
          type: 'EMAIL',
          start: 0,
          end: 17,
          page: 0,
          detector: 'TEST',
          method: 'DETERMINISTIC',
          validated: true,
          recommended: true,
        }],
      }),
      decisions: { e1: 'REDACT' },
      categoryDefaults: { EMAIL: 'REDACT' },
    })
    expect(html).toContain(tr.workspace.strategyRedact)
    expect(html).toContain(tr.workspace.strategyKeep)
    expect(html).not.toContain(tr.workspace.strategyPlaceholder)
    expect(html).not.toContain(tr.workspace.strategyInitials)
    expect(html).not.toContain(tr.workspace.strategyPartial)
  })

  it('preserves entity and occurrence override controls', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          personEntity('p1', 'John Brown', {
            start: 0,
            end: 10,
            resolved_entity_id: 'person-1',
          }),
          personEntity('p2', 'John Brown', {
            start: 20,
            end: 30,
            page: 1,
            resolved_entity_id: 'person-1',
          }),
        ],
      }),
      decisions: { p1: 'REDACT', p2: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER' },
      activeId: 'p1',
    })
    expect(html).toContain(tr.workspace.moreActions)
    expect(html).toContain(t('workspace.occurrenceCount', { count: 2 }))
    expect(html).toContain('finding-method-panel')
    expect(html).toContain('occurrence-list')
    expect(html).toContain(tr.workspace.applyAllOccurrences)
    expect(html).toContain(tr.workspace.thisOccurrenceOnly)
    expect(html).not.toContain('finding-more')
    expect(html).not.toContain('Sözlüğe ekle')
    expect(html).not.toContain('Add to dictionary')
  })

  it('hides occurrence pages unless that finding is selected', () => {
    const entities = [
      personEntity('p1', 'Nursu Karakan', {
        start: 0,
        end: 13,
        resolved_entity_id: 'person-nursu',
      }),
      personEntity('p2', 'Nursu Karakan', {
        start: 20,
        end: 33,
        page: 1,
        resolved_entity_id: 'person-nursu',
      }),
    ]
    const idle = renderPanel({
      analysis: analysis({ entities }),
      decisions: { p1: 'REDACT', p2: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER' },
      activeId: null,
    })
    expect(idle).toContain('Nursu Karakan')
    expect(idle).toContain(t('workspace.occurrenceCount', { count: 2 }))
    expect(idle).not.toContain('occurrence-list')

    const selected = renderPanel({
      analysis: analysis({ entities }),
      decisions: { p1: 'REDACT', p2: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER' },
      activeId: 'p1',
    })
    expect(selected).toContain('occurrence-list')
  })
})

function finding(
  id: string,
  type: string,
  text: string,
  extra: Record<string, unknown> = {},
) {
  return {
    id,
    text,
    type,
    start: 0,
    end: text.length,
    page: 0,
    detector: 'TEST',
    method: 'DETERMINISTIC' as const,
    validated: true,
    recommended: true,
    ...extra,
  }
}

const roleCatalog: TransformCatalog = {
  ...catalog,
  strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
  categories: [
    ...catalog.categories,
    {
      category: 'LAWYER_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: true,
    },
    {
      category: 'JUDGE_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'REDACT',
      generalization_options: [],
      supports_role_replacement: true,
    },
    {
      category: 'CLAIMANT_NAME',
      allowed_strategies: ['REDACT', 'PLACEHOLDER', 'KEEP'],
      recommended_strategy: 'PLACEHOLDER',
      generalization_options: [],
      supports_role_replacement: true,
    },
  ],
}

describe('detected subcategory presentation', () => {
  it('A. shows person roles as detected subcategories under personal names', () => {
    const html = renderPanel({
      catalog: roleCatalog,
      analysis: analysis({
        entities: [
          finding('p', 'PERSON_NAME', 'Ali Kaya', { start: 0, end: 8 }),
          finding('c', 'CLAIMANT_NAME', 'Ayşe Demir', { start: 10, end: 20 }),
          finding('l', 'LAWYER_NAME', 'Hasan Koç', { start: 22, end: 31 }),
          finding('j', 'JUDGE_NAME', 'Fatma Yılmaz', { start: 33, end: 45 }),
        ],
      }),
      decisions: { p: 'REDACT', c: 'REDACT', l: 'REDACT', j: 'REDACT' },
      categoryDefaults: {
        PERSON_NAME: 'PLACEHOLDER',
        CLAIMANT_NAME: 'PLACEHOLDER',
        LAWYER_NAME: 'PLACEHOLDER',
        JUDGE_NAME: 'REDACT',
      },
    })
    expect(html).toContain(tr.presentation.groups.person)
    expect(html).toContain(tr.categories.CLAIMANT_NAME)
    expect(html).toContain(tr.categories.LAWYER_NAME)
    expect(html).toContain(tr.categories.JUDGE_NAME)
    expect(html).toContain('subcategory-toggle')
    expect(html).not.toContain(tr.categories.DEFENDANT_NAME)
    expect(html).not.toContain(tr.categories.WITNESS_NAME)
    expect(html).not.toContain(tr.categories.EXPERT_NAME)
  })

  it('B. does not expose first name, last name, or alias as separate subcategories', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          finding('p', 'PERSON_NAME', 'Ali Kaya', { start: 0, end: 8 }),
          finding('f', 'FIRST_NAME', 'Ayşe', { start: 10, end: 14 }),
          finding('l', 'LAST_NAME', 'Demir', { start: 16, end: 21 }),
          finding('a', 'ALIAS', 'A. Demir', { start: 23, end: 31 }),
        ],
      }),
      decisions: { p: 'REDACT', f: 'REDACT', l: 'REDACT', a: 'REDACT' },
    })
    expect(html).toContain(tr.categories.PERSON_NAME)
    expect(html).toContain('Ayşe')
    expect(html).toContain('Demir')
    expect(html).toContain('A. Demir')
    expect(html).not.toContain(tr.categories.FIRST_NAME)
    expect(html).not.toContain(tr.categories.LAST_NAME)
    expect(html).not.toContain(tr.categories.ALIAS)
    expect(html).not.toContain('subcategory-toggle')
  })

  it('C/J. keeps lawyer tags in document language while the panel follows UI language', () => {
    const html = renderPanel({
      catalog: roleCatalog,
      language: 'en',
      analysis: analysis({
        entities: [
          finding('p', 'PERSON_NAME', 'John Brown', { start: 0, end: 10 }),
          finding('l', 'LAWYER_NAME', 'Rebecca Mills', {
            start: 12,
            end: 25,
            placeholder_token: '[LAWYER_1]',
          }),
        ],
      }),
      decisions: { p: 'REDACT', l: 'REDACT' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER', LAWYER_NAME: 'PLACEHOLDER' },
    })
    expect(html).toContain(tr.categories.LAWYER_NAME)
    expect(html).toContain('Rebecca Mills → [LAWYER_1]')
    expect(html).not.toContain('[AVUKAT_1]')
  })

  it('D. renders court information without a nested duplicate heading', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [finding('c', 'COURT_NAME', 'Ankara 1. Asliye')],
      }),
      decisions: { c: 'REDACT' },
      categoryDefaults: { COURT_NAME: 'PLACEHOLDER' },
    })
    expect(html).toContain(tr.presentation.groups.court)
    expect(html).not.toContain('subcategory-toggle')
  })

  it('E. shows separate detected identity subcategories', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          finding('n', 'NATIONAL_ID', '12345678901', { start: 0, end: 11 }),
          finding('p', 'PASSPORT_NUMBER', 'U12345678', { start: 13, end: 22 }),
          finding('d', 'DATE_OF_BIRTH', '01.01.1990', { start: 24, end: 34 }),
        ],
      }),
      decisions: { n: 'REDACT', p: 'REDACT', d: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.identity)
    expect(html).toContain(tr.categories.NATIONAL_ID)
    expect(html).toContain(tr.categories.PASSPORT_NUMBER)
    expect(html).toContain(tr.categories.DATE_OF_BIRTH)
  })

  it('G. keeps a KEEP lawyer subcategory visible and editable in Findings', () => {
    const html = renderPanel({
      catalog: roleCatalog,
      analysis: analysis({
        entities: [
          finding('p', 'PERSON_NAME', 'John Brown', { start: 0, end: 10 }),
          finding('l', 'LAWYER_NAME', 'Rebecca Mills', { start: 12, end: 25 }),
        ],
      }),
      decisions: { p: 'REDACT', l: 'KEEP' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER', LAWYER_NAME: 'KEEP' },
    })
    expect(html).toContain(tr.categories.LAWYER_NAME)
    expect(html).toContain('Rebecca Mills')
    expect(html).toContain(tr.workspace.strategyKeep)
    expect(html).toContain(tr.workspace.howFindingsAppear)
    expect(html).toContain(tr.workspace.paneDetections)
  })

  it('H. renders independent methods for person, lawyer, and judge subcategories', () => {
    const html = renderPanel({
      catalog: roleCatalog,
      analysis: analysis({
        entities: [
          finding('p', 'PERSON_NAME', 'John Brown', { start: 0, end: 10 }),
          finding('l', 'LAWYER_NAME', 'Rebecca Mills', { start: 12, end: 25 }),
          finding('j', 'JUDGE_NAME', 'Judge Hart', { start: 27, end: 37 }),
        ],
      }),
      decisions: { p: 'REDACT', l: 'KEEP', j: 'REDACT' },
      categoryDefaults: {
        PERSON_NAME: 'PLACEHOLDER',
        LAWYER_NAME: 'KEEP',
        JUDGE_NAME: 'REDACT',
      },
    })
    expect(html).toContain(tr.categories.PERSON_NAME)
    expect(html).toContain(tr.categories.LAWYER_NAME)
    expect(html).toContain(tr.categories.JUDGE_NAME)
    expect(html).toContain(tr.workspace.strategyPlaceholder)
    expect(html).toContain(tr.workspace.strategyKeep)
    expect(html).toContain(tr.workspace.strategyRedact)
  })

  it('I. uses English subcategory labels when the UI is English', () => {
    const html = renderPanel({
      t: tEn,
      catalog: roleCatalog,
      analysis: analysis({
        entities: [
          finding('p', 'PERSON_NAME', 'John Brown', { start: 0, end: 10 }),
          finding('l', 'LAWYER_NAME', 'Rebecca Mills', { start: 12, end: 25 }),
        ],
      }),
      decisions: { p: 'REDACT', l: 'REDACT' },
    })
    expect(html).toContain(en.presentation.groups.person)
    expect(html).toContain(en.categories.LAWYER_NAME)
    expect(html).not.toContain(tr.categories.LAWYER_NAME)
  })

  it('K. still renders possible-match merge UI under the person group', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          finding('e1', 'PERSON_NAME', 'John Brown', {
            start: 0,
            end: 10,
            page: 1,
            placeholder_token: '[KİŞİ_1]',
          }),
          finding('e2', 'LAWYER_NAME', 'Mr Brown', {
            start: 20,
            end: 28,
            page: 6,
            placeholder_token: '[AVUKAT_1]',
          }),
        ],
        possible_matches: [
          {
            id: 'pm_1',
            members: [
              {
                canonical_id: 'c1',
                entity_ids: ['e1'],
                text: 'John Brown',
                pages: [1],
                placeholder_token: '[KİŞİ_1]',
              },
              {
                canonical_id: 'c2',
                entity_ids: ['e2'],
                text: 'Mr Brown',
                pages: [6],
                placeholder_token: '[AVUKAT_1]',
              },
            ],
          },
        ],
      }),
      decisions: { e1: 'REDACT', e2: 'REDACT' },
    })
    expect(html).toContain(tr.presentation.groups.person)
    expect(html).toContain(tr.categories.LAWYER_NAME)
    expect(html).toContain(tr.workspace.possibleMatchTitle)
    expect(html).toContain(tr.workspace.possibleMatchMerge)
    expect(html).toContain('John Brown')
    expect(html).toContain('Mr Brown')
  })

  it('M. keeps KEEP subtypes in Findings and lists them in the unmasked audit view', () => {
    const entities = [
      finding('p', 'PERSON_NAME', 'John Brown', { start: 0, end: 10 }),
      finding('l', 'LAWYER_NAME', 'Rebecca Mills', { start: 12, end: 25 }),
    ]
    const findings = renderPanel({
      catalog: roleCatalog,
      analysis: analysis({ entities }),
      decisions: { p: 'REDACT', l: 'KEEP' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER', LAWYER_NAME: 'KEEP' },
    })
    expect(findings).toContain(tr.categories.LAWYER_NAME)
    expect(findings).toContain('Rebecca Mills')
    expect(findings).toContain(tr.workspace.paneDetections)

    const unmasked = renderPanel({
      catalog: roleCatalog,
      analysis: analysis({ entities }),
      decisions: { p: 'REDACT', l: 'KEEP' },
      categoryDefaults: { PERSON_NAME: 'PLACEHOLDER', LAWYER_NAME: 'KEEP' },
      showPreserved: true,
    })
    expect(unmasked).toContain('Rebecca Mills')
    expect(unmasked).toContain('is-preserved')
  })
})

describe('ReviewPanel manual merge mode', () => {
  it('opens merge workspace in the right panel for the source person', () => {
    const html = renderPanel({
      analysis: analysis({
        entities: [
          finding('p4', 'PERSON_NAME', 'Mehmet', {
            start: 20,
            end: 26,
            resolved_entity_id: 'kisi-4',
            placeholder_token: '[KİŞİ_4]',
          }),
          finding('p1', 'PERSON_NAME', 'Mehmet Yılmaz', {
            start: 0,
            end: 13,
            resolved_entity_id: 'kisi-1',
            placeholder_token: '[KİŞİ_1]',
          }),
          finding('p2', 'PERSON_NAME', 'Ayşe Demir', {
            start: 40,
            end: 50,
            resolved_entity_id: 'kisi-2',
            placeholder_token: '[KİŞİ_2]',
          }),
        ],
        possible_matches: [
          {
            id: 'pm',
            members: [
              {
                canonical_id: 'kisi-4',
                entity_ids: ['p4'],
                text: 'Mehmet',
                pages: [0],
                placeholder_token: '[KİŞİ_4]',
              },
              {
                canonical_id: 'kisi-1',
                entity_ids: ['p1'],
                text: 'Mehmet Yılmaz',
                pages: [0],
                placeholder_token: '[KİŞİ_1]',
              },
            ],
          },
        ],
      }),
      decisions: { p4: 'REDACT', p1: 'REDACT', p2: 'REDACT' },
      manualMergeSourceId: 'p4',
      onManualMerge: () => undefined,
      onCancelManualMerge: () => undefined,
    })
    expect(html).toContain(tr.workspace.manualMergeTitle)
    expect(html).toContain(tr.workspace.manualMergeSelect)
    expect(html).toContain(tr.workspace.manualMergeSearch)
    expect(html).toContain('[KİŞİ_4]')
    expect(html).toContain('Mehmet Yılmaz')
    expect(html).toContain(tr.workspace.manualMergePossible)
    expect(html).toContain(tr.workspace.manualMergeOthers)
    expect(html).toContain('Ayşe Demir')
    expect(html).toContain(tr.workspace.manualMergeCancel)
    expect(html).not.toContain('possible-match-merge')
    expect(html).not.toContain(tr.workspace.possibleMatchKeepSeparate)
  })
})


