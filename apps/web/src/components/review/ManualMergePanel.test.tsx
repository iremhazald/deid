import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ManualMergePanel } from './ManualMergePanel'
import type { Entity, PossibleMatch } from '../../state/types'
import tr from '../../locales/tr.json'
import en from '../../locales/en.json'

const lookup = (
  locale: typeof tr | typeof en,
  key: string,
  options?: Record<string, unknown>,
) => {
  const parts = key.split('.')
  let current: unknown = locale
  for (const part of parts) {
    if (typeof current !== 'object' || current === null || !(part in current)) return key
    current = (current as Record<string, unknown>)[part]
  }
  if (typeof current !== 'string') return key
  return current.replace(/\{\{(\w+)\}\}/g, (_, name: string) => String(options?.[name] ?? ''))
}

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

const source = entity({
  id: 'p4',
  type: 'PERSON_NAME',
  text: 'Mehmet',
  resolved_entity_id: 'kisi-4',
  placeholder_token: '[KİŞİ_4]',
})
const yilmaz = entity({
  id: 'p1',
  type: 'PERSON_NAME',
  text: 'Mehmet Yılmaz',
  resolved_entity_id: 'kisi-1',
  placeholder_token: '[KİŞİ_1]',
})
const ayse = entity({
  id: 'p2',
  type: 'PERSON_NAME',
  text: 'Ayşe Demir',
  resolved_entity_id: 'kisi-2',
  placeholder_token: '[KİŞİ_2]',
})
const lawyer = entity({
  id: 'l1',
  type: 'LAWYER_NAME',
  text: 'Selin Arslan',
  resolved_entity_id: 'lawyer-1',
  placeholder_token: '[AVUKAT_1]',
})
const claimant = entity({
  id: 'c1',
  type: 'CLAIMANT_NAME',
  text: 'Ahmet Kaya',
  resolved_entity_id: 'claimant-1',
  placeholder_token: '[DAVACI_1]',
})
const matches: PossibleMatch[] = [
  {
    id: 'm1',
    members: [
      { canonical_id: 'kisi-4', entity_ids: ['p4'], text: 'Mehmet', pages: [0], placeholder_token: '[KİŞİ_4]' },
      { canonical_id: 'kisi-1', entity_ids: ['p1'], text: 'Mehmet Yılmaz', pages: [0], placeholder_token: '[KİŞİ_1]' },
    ],
  },
]

describe('ManualMergePanel', () => {
  it('enters panel merge mode with the source person and searchable targets', () => {
    const html = renderToStaticMarkup(
      <ManualMergePanel
        sourceEntity={source}
        entities={[source, yilmaz, ayse, lawyer, claimant]}
        possibleMatches={matches}
        t={(key, options) => lookup(tr, key, options)}
        onMerge={() => undefined}
        onCancel={() => undefined}
      />,
    )
    expect(html).toContain('manual-merge-panel')
    expect(html).toContain(tr.workspace.manualMergeTitle)
    expect(html).toContain('Mehmet')
    expect(html).toContain('[KİŞİ_4]')
    expect(html).toContain(tr.workspace.manualMergeSelect)
    expect(html).toContain(tr.workspace.manualMergeSearch)
    expect(html).toContain(tr.workspace.manualMergePossible)
    expect(html).toContain('Mehmet Yılmaz')
    expect(html).toContain('[KİŞİ_1]')
    expect(html).toContain(tr.workspace.manualMergeOthers)
    expect(html).toContain('Ayşe Demir')
    expect(html).toContain('Selin Arslan')
    expect(html).toContain('[AVUKAT_1]')
    expect(html).toContain(tr.workspace.manualMergeCancel)
    expect(html.indexOf('Mehmet Yılmaz')).toBeLessThan(html.indexOf('Ayşe Demir'))
    expect(html.match(/Mehmet(?! Yılmaz)/g)?.length).toBeGreaterThan(0)
    const sourceBlock = html.slice(html.indexOf('manual-merge-source'), html.indexOf('manual-merge-lead'))
    expect(sourceBlock).toContain('[KİŞİ_4]')
    expect(sourceBlock).not.toContain('[KİŞİ_1]')
    expect(html.slice(html.indexOf('manual-merge-targets'))).not.toContain('[KİŞİ_4]')
  })

  it('uses English UI copy while keeping document-language tags', () => {
    const html = renderToStaticMarkup(
      <ManualMergePanel
        sourceEntity={source}
        entities={[source, yilmaz, ayse]}
        possibleMatches={matches}
        t={(key, options) => lookup(en, key, options)}
        onMerge={() => undefined}
        onCancel={() => undefined}
      />,
    )
    expect(html).toContain(en.workspace.manualMergeTitle)
    expect(html).toContain(en.workspace.manualMergeSearch)
    expect(html).toContain(en.workspace.manualMergePossible)
    expect(html).toContain(en.workspace.manualMergeOthers)
    expect(html).toContain(en.workspace.manualMergeCancel)
    expect(html).toContain('[KİŞİ_4]')
    expect(html).toContain('[KİŞİ_1]')
    expect(html).not.toContain('[PERSON_4]')
  })

  it('shows a custom-finding person as a merge source', () => {
    const custom = entity({
      id: 'custom',
      type: 'PERSON_NAME',
      text: 'Mehmet',
      resolved_entity_id: 'kisi-4',
      placeholder_token: '[KİŞİ_4]',
      method: 'MANUAL',
      detector: 'USER_DEFINED_TERM',
    })
    const html = renderToStaticMarkup(
      <ManualMergePanel
        sourceEntity={custom}
        entities={[custom, yilmaz]}
        possibleMatches={matches}
        t={(key, options) => lookup(tr, key, options)}
        onMerge={() => undefined}
        onCancel={() => undefined}
      />,
    )
    expect(html).toContain('Mehmet')
    expect(html).toContain('Mehmet Yılmaz')
  })
})
