import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { DocumentViewer } from './DocumentViewer'
import { ReviewWorkspace } from './ReviewWorkspace'
import type { Analysis, Entity } from '../../state/types'
import {
  TEXT_WORKSPACE_FONT_FAMILY,
  TEXT_WORKSPACE_FONT_SIZE,
  pdfSourcePageTexts,
  flowTextLines,
  textDocumentPageStyle,
  textWorkspaceCanvasStyle,
  type PdfTextLayout,
} from './textWorkspacePages'

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

const labels: Record<string, string> = {
  selectModeHint:
    'Belgeden istediğiniz bir metni seçin, anında gizleme listesine ekleyin.',
  'workspace.sourceFile': 'Kaynak dosya: PDF',
  'workspace.workViewText': 'Çalışma görünümü: Metin',
  warning: 'Uyarı',
  'messages.OCR_USED': 'Bu belgede tarama var.',
  'messages.DOCX_UNSUPPORTED_CONTENT': 'Desteklenmeyen içerik var.',
  'messages.UDF_TEXT_ONLY': 'UDF metin olarak açıldı.',
}

function t(key: string) {
  return labels[key] ?? key
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
  t,
  onSelect: () => undefined,
  onPageInView: () => undefined,
  onManualAdd: () => undefined,
  onAreaDrawn: () => undefined,
}

function articleTexts(html: string): string[] {
  return html.split(/<article\b/).slice(1).map((part) => {
    const inner = part.slice(part.indexOf('>') + 1).split('</article>')[0] ?? ''
    return inner.replace(/<[^>]+>/g, '')
  })
}

describe('text workspace page metadata', () => {
  it('uses PDF page texts only when they reconstruct the source string', () => {
    const pages = ['Birinci satır\n', '  İkinci\tsütun']
    const text = pages.join('')
    expect(pdfSourcePageTexts('PDF', text, pages)).toEqual(pages)
    expect(pdfSourcePageTexts('PDF', text, ['tek'])).toBeNull()
    expect(pdfSourcePageTexts('PDF', `${text}x`, pages)).toBeNull()
    expect(pdfSourcePageTexts('DOCX', text, pages)).toBeNull()
    expect(pdfSourcePageTexts('UDF', text, pages)).toBeNull()
  })
})

describe('Text Workspace presentation', () => {
  it('sets Times New Roman 12pt on PDF, DOCX, and UDF text surfaces', () => {
    for (const documentKind of ['PDF', 'DOCX', 'UDF'] as const) {
      const html = renderToStaticMarkup(
        <DocumentViewer {...base} documentKind={documentKind} workspaceMode="TEXT" />,
      )
      expect(html).toContain('Times New Roman')
      expect(html).toContain(TEXT_WORKSPACE_FONT_SIZE)
      expect(html).toContain('Times, serif')
      expect(html).toContain('text-doc-page')
      expect(html).toContain('white-space:pre-wrap')
      expect(html).toContain('210mm')
      expect(html).toContain('297mm')
      expect(html).toContain('#e6e6e6')
      expect(html).toContain('#ffffff')
      expect(html.match(/text-doc-page/g)).toHaveLength(1)
      expect(html).not.toContain('data-pdf-source-page')
    }
    expect(TEXT_WORKSPACE_FONT_FAMILY).toBe('"Times New Roman", Times, serif')
    expect(textDocumentPageStyle.fontSize).toBe('12pt')
    expect(textDocumentPageStyle.whiteSpace).toBe('pre-wrap')
    expect(textDocumentPageStyle.textAlign).toBe('left')
    expect(textWorkspaceCanvasStyle.gap).toBe('48px')
    expect(textWorkspaceCanvasStyle.background).toBe('#e6e6e6')
  })

  it('renders each PDF source page as its own surface and keeps line breaks', () => {
    const pages = ['Birinci satır\n', 'Sayın Ayşe Demir,\n  devam\tnotu']
    const text = pages.join('')
    const start = text.indexOf('Ayşe Demir')
    const html = renderToStaticMarkup(
      <DocumentViewer
        {...base}
        documentKind="PDF"
        workspaceMode="TEXT"
        pageCount={2}
        text={text}
        pageTexts={[...pages]}
        entities={[{ ...person, start, end: start + person.text.length, page: 1 }]}
      />,
    )
    expect(html.match(/data-pdf-source-page="/g)).toHaveLength(2)
    expect(html).toContain('id="pdf-page-1"')
    expect(html).toContain('id="pdf-page-2"')
    expect(html).not.toContain('page-separator')
    expect(html).not.toContain('pdf-page-wrap')
    expect(articleTexts(html)).toEqual(pages)
    expect(html).toContain('doc-entity')
    expect(html).toContain('id="entity-name-1"')
    expect(html).toContain('class="sheet text-doc-page select-mode"')
    expect(html).toContain('user-select:text')
  })

  it('keeps DOCX and UDF on one page and retains breaks, spaces, and tabs', () => {
    const text = 'Sol    sağ\nİkinci satır\n\nKolon\tDeğer'
    for (const documentKind of ['DOCX', 'UDF'] as const) {
      const html = renderToStaticMarkup(
        <DocumentViewer
          {...base}
          documentKind={documentKind}
          workspaceMode="TEXT"
          text={text}
          entities={[]}
          pageTexts={['Sol    sağ\n', 'İkinci satır\n\nKolon\tDeğer']}
        />,
      )
      expect(html.match(/text-doc-page/g)).toHaveLength(1)
      expect(html).not.toContain('data-pdf-source-page')
      expect(html).not.toContain('pdf-page-wrap')
      expect(articleTexts(html)).toEqual([text])
      expect(html).not.toContain('&nbsp;')
    }
  })

  it('does not drop PDF text when page metadata does not match the source', () => {
    const text = 'ABCDEFGH\nIKINCI'
    const html = renderToStaticMarkup(
      <DocumentViewer
        {...base}
        documentKind="PDF"
        workspaceMode="TEXT"
        text={text}
        entities={[]}
        pageTexts={['ABC', 'DEF']}
      />,
    )
    expect(html.match(/text-doc-page/g)).toHaveLength(1)
    expect(articleTexts(html)).toEqual([text])
    expect(html).not.toContain('data-pdf-source-page')
  })

  it('removes the manual-selection banner and keeps finding marks selectable', () => {
    const html = renderToStaticMarkup(
      <DocumentViewer {...base} documentKind="PDF" workspaceMode="TEXT" tool="select-text" />,
    )
    expect(html).not.toContain('select-mode-hint')
    expect(html).not.toContain(labels.selectModeHint)
    expect(html).toContain('select-mode')
    expect(html).toContain('doc-entity')
    expect(html).toContain('Ayşe Demir')
    expect(articleTexts(html)).toEqual([base.text])
  })

  it('leaves the PDF document viewer on the page canvas', () => {
    const html = renderToStaticMarkup(
      <DocumentViewer {...base} documentKind="PDF" workspaceMode="DOCUMENT" />,
    )
    expect(html).toContain('pdf-page-wrap')
    expect(html).not.toContain('text-doc-page')
    expect(html).not.toContain('text-workspace')
    expect(html).not.toContain('Times New Roman')
    expect(html).not.toContain(labels.selectModeHint)
  })

  it('joins same-baseline PDF spans into one reading line and lets a short label close the gap', () => {
    const text = 'TALIMAT NO\n: 2023/216 Talimat\nBASKAN\n: HASAN ISIK\n'
    const layout: PdfTextLayout = {
      page: 0,
      width: 595,
      height: 842,
      runs: [
        { start: 0, end: 10, x0: 72, y0: 178.5, x1: 150, y1: 193.8, size: 11 },
        { start: 11, end: 29, x0: 230, y0: 178.4, x1: 340, y1: 193.1, size: 11 },
        { start: 30, end: 36, x0: 72, y0: 238.5, x1: 130, y1: 253.8, size: 11 },
        { start: 37, end: 49, x0: 230, y0: 238.4, x1: 320, y1: 253.1, size: 11 },
      ],
    }
    const lines = flowTextLines(text, layout)
    expect(lines.flatMap((line) => line.pieces).map((piece) => piece.text).join('')).toBe(text)
    expect(lines.filter((line) => line.align !== 'blank')).toHaveLength(2)
    expect(lines[0]?.align).toBe('form')
    expect(lines[0]?.pieces.some((piece) => piece.kind === 'join')).toBe(true)
    const nameStart = text.indexOf('HASAN ISIK')
    const html = renderToStaticMarkup(
      <DocumentViewer
        {...base}
        documentKind="PDF"
        workspaceMode="TEXT"
        viewMode="preview"
        text={text}
        entities={[{
          ...person,
          text: 'HASAN ISIK',
          start: nameStart,
          end: nameStart + 'HASAN ISIK'.length,
          placeholder_token: '[KİŞİ_1]',
        }]}
        pageLayouts={[layout]}
      />,
    )
    expect(html).toContain('data-text-flow="true"')
    expect(html).toContain('text-flow-line is-form')
    expect(html).toContain('[KİŞİ_1]')
    expect(html).not.toContain('font-weight:700')
    expect(html).not.toContain('position:absolute')
    const value = html.split('text-flow-value')[2] ?? ''
    expect(value).toContain('[KİŞİ_1]')
    expect(value).not.toContain('left:')
  })

  it('does not apply PDF span positions to a DOCX text page', () => {
    const text = 'TALIMAT NO\n: 2023/216 Talimat\n'
    const html = renderToStaticMarkup(
      <DocumentViewer
        {...base}
        documentKind="DOCX"
        workspaceMode="TEXT"
        text={text}
        entities={[]}
        pageLayouts={[{
          page: 0,
          width: 595,
          height: 842,
          runs: [
            { start: 0, end: 10, x0: 72, y0: 10, x1: 100, y1: 20, size: 11 },
            { start: 11, end: text.length, x0: 230, y0: 10, x1: 300, y1: 20, size: 11 },
          ],
        }]}
      />,
    )
    expect(html).not.toContain('data-text-flow')
    expect(articleTexts(html)).toEqual([text])
  })
})

function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    job_id: 'job',
    file_name: 'dilekce.pdf',
    document_kind: 'PDF',
    source_document_type: 'PDF',
    workspace_mode: 'TEXT',
    page_count: 1,
    text: 'Contact Ayşe Demir today.',
    page_texts: ['Contact Ayşe Demir today.'],
    entities: [person],
    warnings: ['OCR_USED'],
    profile: 'KVKK',
    ...overrides,
  }
}

function workspaceHtml(overrides: Partial<Analysis> = {}) {
  const current = analysis(overrides)
  return renderToStaticMarkup(
    <ReviewWorkspace
      analysis={current}
      decisions={{ 'name-1': 'REDACT' }}
      categoryDefaults={{ PERSON_NAME: 'PLACEHOLDER' }}
      entityStrategies={{ 'name-1': 'PLACEHOLDER' }}
      catalog={null}
      previewText={current.text}
      activeId={null}
      profile="KVKK"
      outputFormat="TXT"
      manual={[]}
      busy={false}
      language="tr"
      t={t}
      onSelect={() => undefined}
      onDecision={() => undefined}
      onBulk={() => undefined}
      onProfileChange={() => undefined}
      onCategoryDefault={() => undefined}
      onEntityStrategy={() => undefined}
      onOutputFormatChange={() => undefined}
      onManualChange={() => undefined}
      onRestoreState={() => undefined}
    />,
  )
}

describe('Text Workspace chrome', () => {
  it('drops the source/workspace row and the selection banner for every text source', () => {
    const cases: Array<Partial<Analysis>> = [
      {},
      {
        file_name: 'dilekce.docx',
        document_kind: 'DOCX',
        source_document_type: 'DOCX',
        warnings: ['DOCX_UNSUPPORTED_CONTENT'],
      },
      {
        file_name: 'dilekce.udf',
        document_kind: 'DOCX',
        source_document_type: 'UDF',
        warnings: ['UDF_TEXT_ONLY'],
      },
    ]
    for (const item of cases) {
      const html = workspaceHtml(item)
      expect(html).toContain(item.file_name ?? 'dilekce.pdf')
      expect(html).not.toContain('Kaynak dosya')
      expect(html).not.toContain('Çalışma görünümü')
      expect(html).not.toContain('text-workspace-caption')
      expect(html).not.toContain(labels.selectModeHint)
      expect(html).not.toContain('select-mode-hint')
      expect(html).toContain('doc-entity')
      expect(html).toContain('Ayşe Demir')
      expect(html).toContain('class="notice')
    }
  })

  it('keeps the PDF document workspace on the page viewer', () => {
    const html = workspaceHtml({
      workspace_mode: 'DOCUMENT',
      file_name: 'dilekce.pdf',
    })
    expect(html).toContain('dilekce.pdf')
    expect(html).toContain('pdf-page-wrap')
    expect(html).not.toContain('text-doc-page')
    expect(html).not.toContain('Kaynak dosya')
    expect(html).toContain('Bu belgede tarama var.')
  })
})
