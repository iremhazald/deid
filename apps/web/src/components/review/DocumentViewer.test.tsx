import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { DocumentViewer } from './DocumentViewer'
import { suggestSelectionCategory } from './selectionCategory'
import type { Entity } from '../../state/types'

const person: Entity = {
  id: 'name-1',
  text: 'Ayşe Demir',
  type: 'PERSON_NAME',
  start: 8,
  end: 18,
  page: 0,
  detector: 'TR_ROLE_PERSON',
  method: 'DETERMINISTIC',
  validated: true,
  recommended: true,
  recommended_strategy: 'PLACEHOLDER',
  placeholder_token: '[KİŞİ_1]',
}

const base = {
  jobId: 'job',
  pageCount: 1,
  text: 'Contact Ayşe Demir today.',
  entities: [person],
  decisions: { 'name-1': 'REDACT' as const },
  categoryDefaults: { PERSON_NAME: 'PLACEHOLDER' as const },
  entityStrategies: { 'name-1': 'PLACEHOLDER' as const },
  manual: [],
  activeId: null,
  focusId: null,
  currentPage: 1,
  viewMode: 'detections' as const,
  tool: 'select-text' as const,
  pageWidth: 560,
  language: 'tr',
  t: (key: string) => key,
  onSelect: () => undefined,
  onPageInView: () => undefined,
  onManualAdd: () => undefined,
  onAreaDrawn: () => undefined,
}

describe('DocumentViewer workspace', () => {
  it('mounts the PDF page viewer for document mode', () => {
    const html = renderToStaticMarkup(
      <DocumentViewer {...base} documentKind="PDF" workspaceMode="DOCUMENT" />,
    )
    expect(html).toContain('pdf-page-wrap')
    expect(html).not.toContain('class="sheet')
  })

  it('shows extracted text for PDF text mode and does not mount PdfPageViewer', () => {
    const html = renderToStaticMarkup(
      <DocumentViewer {...base} documentKind="PDF" workspaceMode="TEXT" />,
    )
    expect(html).toContain('Ayşe Demir')
    expect(html).toContain('doc-entity')
    expect(html).toContain('class="sheet')
    expect(html).not.toContain('pdf-page-wrap')
    expect(html).not.toContain('ChatGPT')
    expect(html).not.toContain('OpenAI')
  })

  it('uses the same text sheet for a DOCX source', () => {
    const html = renderToStaticMarkup(
      <DocumentViewer {...base} documentKind="DOCX" workspaceMode="TEXT" />,
    )
    expect(html).toContain('Ayşe Demir')
    expect(html).toContain('doc-entity')
    expect(html).toContain('class="sheet')
    expect(html).not.toContain('pdf-page-wrap')
  })

  it('uses the same text sheet for a UYAP UDF source', () => {
    const html = renderToStaticMarkup(
      <DocumentViewer {...base} documentKind="UDF" workspaceMode="TEXT" />,
    )
    expect(html).toContain('Ayşe Demir')
    expect(html).toContain('doc-entity')
    expect(html).not.toContain('pdf-page-wrap')
  })

  it('hides the opening court and docket line behind white paper in text preview', () => {
    const name = 'T.C. SİLİFKE 2. AĞIR CEZA MAHKEMESİ'
    const docket = 'Duruşma Tarihi: 10/11/2025 Talimat No: 2025/203 Talimat'
    const body = 'Gövde metni burada kalır.'
    const text = `${name}\n${docket}\n${body}`
    const court: Entity = {
      id: 'court',
      text: name,
      type: 'COURT_NAME',
      start: 0,
      end: name.length,
      page: 0,
      detector: 'TR_COURT_GRAMMAR',
      method: 'DETERMINISTIC',
      validated: true,
      recommended: true,
      recommended_strategy: 'PLACEHOLDER',
      attributes: { mask_scope: 'header_line' },
    }
    const fileStart = text.indexOf('2025/203')
    const file: Entity = {
      id: 'file',
      text: '2025/203',
      type: 'FILE_NUMBER',
      start: fileStart,
      end: fileStart + '2025/203'.length,
      page: 0,
      detector: 'TR_FILE',
      method: 'DETERMINISTIC',
      validated: true,
      recommended: true,
      recommended_strategy: 'PLACEHOLDER',
      placeholder_token: '[DOSYA_2]',
    }
    const html = renderToStaticMarkup(
      <DocumentViewer
        {...base}
        text={text}
        entities={[court, file]}
        viewMode="preview"
        categoryDefaults={{ COURT_NAME: 'PLACEHOLDER', FILE_NUMBER: 'PLACEHOLDER' }}
        documentKind="PDF"
        workspaceMode="TEXT"
        pageTexts={[text]}
      />,
    )
    expect(html).toContain('is-paper-redact')
    expect(html).toContain('doc-redact-reveal')
    expect(html).toContain(name)
    expect(html).not.toContain('[DOSYA_2]')
    expect(html).not.toContain('SİLİFKE X')
    expect(html).toContain(body)
  })

  it('keeps a PDF with no workspace mode on the page viewer', () => {
    const html = renderToStaticMarkup(<DocumentViewer {...base} documentKind="PDF" />)
    expect(html).toContain('pdf-page-wrap')
  })

  it('suggests a file number for a hearing label', () => {
    expect(suggestSelectionCategory('CELSE NO')).toBe('FILE_NUMBER')
    expect(suggestSelectionCategory('Ayşe Demir')).toBe('PERSON_NAME')
  })
})
