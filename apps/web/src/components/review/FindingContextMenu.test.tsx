import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { FindingContextMenu } from './FindingContextMenu'
import type { Entity, TransformCatalog } from '../../state/types'
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
    if (typeof current !== 'object' || current === null || !(part in current)) return key
    current = (current as Record<string, unknown>)[part]
  }
  if (typeof current !== 'string') return key
  return current.replace(/\{\{(\w+)\}\}/g, (_, name: string) => String(options?.[name] ?? ''))
}

const catalog: TransformCatalog = {
  strategies: ['REDACT', 'PLACEHOLDER', 'INITIALS', 'KEEP'],
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
  ],
  role_labels: { tr: {}, en: {} },
  secure_pdf_strategies: ['REDACT'],
}

function entity(partial: Partial<Entity> & Pick<Entity, 'id' | 'type' | 'text'>): Entity {
  return {
    start: 0,
    end: partial.text.length,
    page: 0,
    detector: 'TEST',
    method: 'DETERMINISTIC',
    validated: true,
    recommended: true,
    recommended_strategy: 'PLACEHOLDER',
    ...partial,
  }
}

const noop = () => undefined

describe('FindingContextMenu', () => {
  it('renders CASE_NUMBER methods and remove without merge, KEEP, or edit', () => {
    const html = renderToStaticMarkup(
      <FindingContextMenu
        entity={entity({ id: 'c1', type: 'CASE_NUMBER', text: '2025/446' })}
        catalog={catalog}
        currentStrategy="PLACEHOLDER"
        x={40}
        y={80}
        t={(key, options) => lookup(tr, key, options)}
        onStrategy={noop}
        onRemove={noop}
        onClose={noop}
      />,
    )
    expect(html).toContain(tr.categories.CASE_NUMBER)
    expect(html).toContain('2025/446')
    expect(html).toContain(tr.workspace.strategyPlaceholder)
    expect(html).toContain(tr.workspace.strategyRedact)
    expect(html).toContain(tr.workspace.contextRemoveFinding)
    expect(html).not.toContain(tr.workspace.contextMergePerson)
    expect(html).not.toContain(tr.workspace.strategyKeep)
    expect(html).not.toContain('Belgede bırak')
    expect(html).not.toContain('Tespiti düzenle')
    expect(html).not.toContain(tr.workspace.removeDetection)
  })

  it('renders person merge and remove, still without KEEP or edit', () => {
    const html = renderToStaticMarkup(
      <FindingContextMenu
        entity={entity({ id: 'p1', type: 'PERSON_NAME', text: 'Mehmet', placeholder_token: '[KİŞİ_4]' })}
        catalog={catalog}
        currentStrategy="PLACEHOLDER"
        x={40}
        y={80}
        t={(key, options) => lookup(tr, key, options)}
        onStrategy={noop}
        onMerge={noop}
        onRemove={noop}
        onClose={noop}
      />,
    )
    expect(html).toContain(tr.categories.PERSON_NAME)
    expect(html).toContain('Mehmet')
    expect(html).toContain(tr.workspace.strategyInitials)
    expect(html).toContain(tr.workspace.contextMergePerson)
    expect(html).toContain(tr.workspace.contextRemoveFinding)
    expect(html).not.toContain(tr.workspace.strategyKeep)
    expect(html).not.toContain('Edit finding')
    expect(html).not.toContain('Tespiti düzenle')
  })

  it('uses English copy without changing document-language tokens', () => {
    const html = renderToStaticMarkup(
      <FindingContextMenu
        entity={entity({
          id: 'p1',
          type: 'PERSON_NAME',
          text: 'Mehmet',
          placeholder_token: '[KİŞİ_4]',
        })}
        catalog={catalog}
        currentStrategy="PLACEHOLDER"
        x={12}
        y={12}
        t={(key, options) => lookup(en, key, options)}
        onStrategy={noop}
        onMerge={noop}
        onRemove={noop}
        onClose={noop}
      />,
    )
    expect(html).toContain(en.workspace.contextMergePerson)
    expect(html).toContain(en.workspace.contextRemoveFinding)
    expect(html).not.toContain(en.workspace.strategyKeep)
    expect(html).toContain('Mehmet')
  })
})
