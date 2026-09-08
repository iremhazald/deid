import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import en from '../../locales/en.json'
import tr from '../../locales/tr.json'
import { DocumentLanguagePicker } from './DocumentLanguagePicker'

function translate(table: Record<string, unknown>) {
  return (key: string) => {
    const parts = key.split('.')
    let current: unknown = table
    for (const part of parts) {
      if (typeof current !== 'object' || current === null || !(part in current)) {
        return key
      }
      current = (current as Record<string, unknown>)[part]
    }
    return typeof current === 'string' ? current : key
  }
}

describe('DocumentLanguagePicker', () => {
  it('shows only Turkish and English with no default selection', () => {
    const html = renderToStaticMarkup(
      <DocumentLanguagePicker
        value={null}
        t={translate(en)}
        onChange={() => undefined}
      />,
    )
    expect(html).toContain('Document Language')
    expect(html).toContain('Select the language of your document.')
    expect(html).toContain('Turkish')
    expect(html).toContain('English')
    expect(html).not.toContain('Auto')
    expect(html).not.toContain('>Auto<')
    expect(html).not.toMatch(/aria-checked="true"/)
  })

  it('shows Turkish labels in the Turkish UI without changing the value', () => {
    const html = renderToStaticMarkup(
      <DocumentLanguagePicker
        value="tr"
        t={translate(tr)}
        onChange={() => undefined}
      />,
    )
    expect(html).toContain('Belge Dili')
    expect(html).toContain('Belgenizin dilini seçin.')
    expect(html).toContain('Türkçe')
    expect(html).toContain('English')
    expect(html).not.toContain('Otomatik')
    expect(html).toMatch(/aria-checked="true"[^>]*>Türkçe</)
  })

  it('keeps an explicit English document language while the UI is Turkish', () => {
    const html = renderToStaticMarkup(
      <DocumentLanguagePicker
        value="en"
        t={translate(tr)}
        onChange={() => undefined}
      />,
    )
    expect(html).toMatch(/aria-checked="true"[^>]*>English</)
    expect(html).not.toContain('Otomatik')
  })
})
