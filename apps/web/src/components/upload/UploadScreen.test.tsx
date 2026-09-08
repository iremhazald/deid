import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import en from '../../locales/en.json'
import tr from '../../locales/tr.json'
import { UploadScreen } from './UploadHero'

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

function renderUpload(
  table: Record<string, unknown>,
  overrides: Partial<Parameters<typeof UploadScreen>[0]> = {},
) {
  const t = translate(table)
  return renderToStaticMarkup(
    <UploadScreen
      uploadTitle={t('uploadTitle')}
      uploadBody={t('uploadBody')}
      dropTitle={t('dropHint')}
      browseLabel={t('browse')}
      limitsLabel="PDF"
      processing={false}
      privacyTitle=""
      privacyBody={t('privacyBody')}
      privacyToggle={t('privacyToggle')}
      t={t}
      onUpload={() => undefined}
      onStartScan={() => undefined}
      documentLanguage={null}
      onDocumentLanguageChange={() => undefined}
      {...overrides}
    />,
  )
}

describe('UploadScreen', () => {
  it('does not show the three scan-mode cards', () => {
    const html = renderUpload(tr, { documentLanguage: 'tr' })
    expect(html).not.toContain('Standart Tarama')
    expect(html).not.toContain('Yerel Bağlam Taraması')
    expect(html).not.toContain('Derinlemesine Tarama')
    expect(html).not.toContain('Nasıl incelensin?')
    expect(html).not.toContain('detection-mode')
    expect(html).not.toContain('mode-card')
  })

  it('hides Standard / Local Context / Deep Scan selectors in English', () => {
    const html = renderUpload(en, { documentLanguage: 'en' })
    expect(html).not.toContain('Standard Scan')
    expect(html).not.toContain('Local Context Scan')
    expect(html).not.toContain('Deep Scan')
    expect(html).not.toContain('Scan scope')
    expect(html).not.toContain('Customize')
  })

  it('shows one Start Scan action with privacy, notice, and integrated settings', () => {
    const html = renderUpload(tr, { selectedFileName: 'dilekce.pdf', documentLanguage: 'tr' })
    expect(html).toContain(tr.uploadTitle)
    expect(html).toContain(tr.uploadBody)
    expect(html).toContain(tr.localScan.cta)
    expect(html).toContain(tr.localScan.privacy)
    expect(html).toContain(tr.localScan.reviewHint)
    expect(html).toContain(tr.uploadNotice.title)
    expect(html).toContain(tr.uploadNotice.body)
    expect(html).not.toContain('Tarama kapsamı')
    expect(html).not.toContain('Özelleştir')
    expect(html).not.toContain('scan-scope')
    expect(html).toContain(tr.privacyToggle)
    expect(html).toContain('upload-settings')
    expect(html).toContain('upload-guidance')
    expect(html).not.toContain('disabled')
    expect(html).not.toContain(tr.localScan.needFile)
  })

  it('keeps only Turkish / English document language controls', () => {
    const turkish = renderUpload(tr)
    expect(turkish).toContain(tr.documentLanguage.label)
    expect(turkish).toContain(tr.documentLanguage.help)
    expect(turkish).toContain(tr.documentLanguage.tr)
    expect(turkish).toContain(tr.documentLanguage.en)
    expect(turkish).not.toMatch(/aria-checked="[^"]*"[^>]*>Otomatik</)
    expect(turkish).not.toContain('>' + tr.documentLanguage.auto + '<')

    const english = renderUpload(en, { documentLanguage: 'en' })
    expect(english).toContain(en.documentLanguage.label)
    expect(english).toContain(en.documentLanguage.help)
    expect(english).toContain(en.documentLanguage.tr)
    expect(english).toContain(en.documentLanguage.en)
    expect(english).not.toMatch(/aria-checked="[^"]*"[^>]*>Auto</)
    expect(english).not.toContain('>' + en.documentLanguage.auto + '<')
    expect(english).toMatch(/aria-checked="true"[^>]*>English</)
  })

  it('does not use cloud-model wording on the upload page', () => {
    const turkish = renderUpload(tr)
    const english = renderUpload(en, { documentLanguage: 'en' })
    expect(turkish).not.toContain('bulut')
    expect(turkish).not.toContain('cloud')
    expect(english).not.toContain('cloud model')
    expect(english).not.toContain('cloud')
    expect(english).toContain(en.privacyToggle)
  })

  it('disables the scan CTA until a file is uploaded and language is selected', () => {
    const noFileNoLang = renderUpload(tr)
    expect(noFileNoLang).toContain('disabled')
    
    const fileButNoLang = renderUpload(tr, { selectedFileName: 'test.pdf', documentLanguage: null })
    expect(fileButNoLang).toContain('disabled')
    expect(fileButNoLang).toContain(tr.localScan.needLanguage)
    
    const langButNoFile = renderUpload(tr, { documentLanguage: 'tr' })
    expect(langButNoFile).toContain('disabled')
    expect(langButNoFile).toContain(tr.localScan.needFile)
    
    const bothReady = renderUpload(tr, { selectedFileName: 'test.pdf', documentLanguage: 'tr' })
    expect(bothReady).not.toContain('disabled')
  })

  it('offers PDF only on the upload dropzone copy', () => {
    expect(en.dropHint).toContain('PDF')
    expect(en.dropHint).not.toMatch(/Word/i)
    expect(en.fileLimits).toContain('PDF')
    expect(en.fileLimits).not.toMatch(/DOCX/i)
    expect(tr.dropHint).toContain('PDF')
    expect(tr.fileLimits).not.toMatch(/DOCX/i)
    expect(tr.fileLimits).not.toMatch(/Word/i)
  })
})
