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
      workspaceMode={null}
      onWorkspaceModeChange={() => undefined}
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
    const html = renderUpload(tr, {
      selectedFileName: 'dilekce.pdf',
      documentLanguage: 'tr',
      workspaceMode: 'DOCUMENT',
    })
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
    
    const bothReady = renderUpload(tr, {
      selectedFileName: 'test.pdf',
      documentLanguage: 'tr',
      workspaceMode: 'DOCUMENT',
    })
    expect(bothReady).not.toContain('disabled')

    const noWorkspace = renderUpload(tr, { selectedFileName: 'test.pdf', documentLanguage: 'tr' })
    expect(noWorkspace).toContain('disabled')
    expect(noWorkspace).toContain(tr.workspaceChoice.needChoice)
  })

  it('asks how to work with a PDF without changing document language', () => {
    const hidden = renderUpload(tr, { documentLanguage: 'tr' })
    expect(hidden).not.toContain(tr.workspaceChoice.question)
    expect(hidden).toContain(tr.documentLanguage.label)

    const turkish = renderUpload(tr, { selectedFileName: 'dilekce.pdf', documentLanguage: 'tr' })
    expect(turkish).toContain(tr.workspaceChoice.question)
    expect(turkish).toContain(tr.workspaceChoice.pdf)
    expect(turkish).toContain(tr.workspaceChoice.text)
    expect(turkish).toContain(tr.documentLanguage.tr)
    expect(turkish).toContain(tr.documentLanguage.en)

    const english = renderUpload(en, {
      selectedFileName: 'claim.pdf',
      documentLanguage: 'en',
      workspaceMode: 'TEXT',
    })
    expect(english).toContain(en.workspaceChoice.question)
    expect(english).toContain(en.workspaceChoice.pdf)
    expect(english).toContain(en.workspaceChoice.text)
    expect(english).toContain(en.documentLanguage.label)
    expect(english).not.toContain('ChatGPT')
    expect(english).not.toContain('OpenAI')
  })

  it('offers PDF, DOCX, and UDF', () => {
    expect(en.dropHint).toContain('PDF')
    expect(en.dropHint).toContain('DOCX')
    expect(en.dropHint).toContain('UDF')
    expect(en.dropHint).not.toContain('UYAP')
    expect(en.fileLimits).toContain('UDF')
    expect(en.fileLimits).not.toContain('UYAP')
    expect(tr.dropHint).toContain('UDF')
    expect(tr.dropHint).not.toContain('UYAP')
    expect(tr.fileLimits).toContain('UDF')
    expect(tr.fileLimits).not.toContain('UYAP')
  })

  it('asks for a workspace only after a PDF is selected', () => {
    const pdf = renderUpload(tr, { selectedFileName: 'dilekce.pdf', documentLanguage: 'tr' })
    expect(pdf).toContain(tr.workspaceChoice.question)
    expect(pdf).not.toContain(tr.docxUpload.source)

    const docx = renderUpload(tr, { selectedFileName: 'not.docx', documentLanguage: 'tr' })
    expect(docx).not.toContain(tr.workspaceChoice.question)
    expect(docx).not.toContain(tr.workspaceChoice.pdf)
    expect(docx).toContain(tr.docxUpload.source)
    expect(docx).toContain(tr.docxUpload.workspace)
    expect(docx).not.toContain('disabled')

    const english = renderUpload(en, { selectedFileName: 'claim.docx', documentLanguage: 'en' })
    expect(english).not.toContain(en.workspaceChoice.question)
    expect(english).toContain(en.docxUpload.source)
    expect(english).toContain('Workspace: Text')

    const udf = renderUpload(tr, { selectedFileName: 'dilekce.udf', documentLanguage: 'tr' })
    expect(udf).not.toContain(tr.workspaceChoice.question)
    expect(udf).toContain(tr.udfUpload.source)
    expect(udf).toContain(tr.udfUpload.workspace)
    expect(udf).not.toContain('disabled')
  })
})
