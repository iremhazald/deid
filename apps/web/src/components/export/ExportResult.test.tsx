import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ExportResult } from './ExportResult'
import tr from '../../locales/tr.json'
import type { Result } from '../../state/types'

const ready: Result = {
  validation: { status: 'PASS', messages: [] },
  download_url: '/api/jobs/job/download',
  audit_url: '/api/jobs/job/audit',
}

describe('ExportResult', () => {
  it('shows the applied-redaction count and a download button', () => {
    const html = renderToStaticMarkup(
      <ExportResult
        result={ready}
        countLabel={tr.redactionApplied.replace('{{count}}', '44')}
        downloadLabel={tr.downloadDocument}
        backLabel={tr.backToWork}
        readyTitle={tr.exportReadyTitle}
        onReset={() => undefined}
      />,
    )
    expect(html).toContain(tr.exportReadyTitle)
    expect(html).toContain('44 gizleme uygulandı')
    expect(html).toContain(tr.downloadDocument)
    expect(html).toContain('/api/jobs/job/download')
    expect(html).not.toContain('Temiz belge oluştur')
    expect(html).not.toContain('Orijinal düzeni koru')
    expect(html).not.toContain('Belge düzeni')
    expect(html).not.toContain(tr.audit)
  })

  it('still offers download when validation failed but a file exists', () => {
    const html = renderToStaticMarkup(
      <ExportResult
        result={{ ...ready, validation: { status: 'FAILED', messages: [] } }}
        countLabel={tr.redactionApplied.replace('{{count}}', '44')}
        downloadLabel={tr.downloadDocument}
        backLabel={tr.backToWork}
        failTitle={tr.exportFailTitle}
        failBody={tr.exportFailBody}
        warnTitle={tr.exportWarnTitle}
        warnBody={tr.exportWarnBody}
        onReset={() => undefined}
      />,
    )
    expect(html).toContain(tr.exportWarnTitle)
    expect(html).toContain(tr.downloadDocument)
    expect(html).toContain('/api/jobs/job/download')
    expect(html).not.toContain(tr.exportFailTitle)
  })

  it('hides download only when the output file is missing', () => {
    const html = renderToStaticMarkup(
      <ExportResult
        result={{ ...ready, download_url: null, validation: { status: 'FAILED', messages: [] } }}
        countLabel={tr.redactionApplied.replace('{{count}}', '44')}
        downloadLabel={tr.downloadDocument}
        backLabel={tr.backToWork}
        failTitle={tr.exportFailTitle}
        failBody={tr.exportFailBody}
        onReset={() => undefined}
      />,
    )
    expect(html).toContain(tr.exportFailTitle)
    expect(html).not.toContain(tr.downloadDocument)
  })

  it('shows selectable transformed text and a copy action instead of a download', () => {
    const html = renderToStaticMarkup(
      <ExportResult
        result={{
          ...ready,
          download_url: null,
          copy_text: 'Ada [GİZLENDİ] kalan.\nJane [REDACTED] stays.',
          export_path: 'text_copy',
        }}
        countLabel={tr.redactionApplied.replace('{{count}}', '2')}
        downloadLabel={tr.downloadDocument}
        backLabel={tr.backToWork}
        readyTitle={tr.exportReadyTitle}
        textReadyTitle={tr.textReadyTitle}
        copyLabel={tr.copyText}
        copiedLabel={tr.textCopied}
        onReset={() => undefined}
      />,
    )
    expect(html).toContain(tr.textReadyTitle)
    expect(html).toContain(tr.copyText)
    expect(html).toContain('[GİZLENDİ]')
    expect(html).toContain('[REDACTED]')
    expect(html).toContain('export-copy-text')
    expect(html).not.toContain(tr.downloadDocument)
    expect(html).not.toContain('ChatGPT')
    expect(html).not.toContain('OpenAI')
    expect(html).not.toContain('Claude')
    expect(html).not.toContain('Gemini')
    expect(html).not.toContain(tr.downloadNewDocx)
  })

  it('offers a new DOCX and PDF beside copy text for a DOCX result', () => {
    const html = renderToStaticMarkup(
      <ExportResult
        result={{
          ...ready,
          download_url: null,
          copy_text: 'Before [REDACTED] after.',
          export_path: 'text_copy',
          downloads: [
            { format: 'DOCX', url: '/api/jobs/job/download?output_format=docx' },
            { format: 'PDF', url: '/api/jobs/job/download?output_format=pdf' },
          ],
        }}
        countLabel={tr.redactionApplied.replace('{{count}}', '1')}
        downloadLabel={tr.downloadDocument}
        backLabel={tr.backToWork}
        textReadyTitle={tr.textReadyTitle}
        copyLabel={tr.copyText}
        copiedLabel={tr.textCopied}
        downloadNewDocxLabel={tr.downloadNewDocx}
        downloadNewDocxNotice={tr.downloadNewDocxNotice}
        downloadNewPdfLabel={tr.downloadNewPdf}
        downloadNewPdfNotice={tr.downloadNewPdfNotice}
        onReset={() => undefined}
      />,
    )
    expect(html).toContain(tr.copyText)
    expect(html).toContain('[REDACTED]')
    expect(html).toContain(tr.downloadNewDocx)
    expect(html).toContain(tr.downloadNewDocxNotice)
    expect(html).toContain(tr.downloadNewPdf)
    expect(html).toContain(tr.downloadNewPdfNotice)
    expect(html).toContain('output_format=docx')
    expect(html).not.toContain(tr.downloadDocument)
  })

  it('offers a new PDF for UYAP UDF text and no UDF download', () => {
    const html = renderToStaticMarkup(
      <ExportResult
        result={{
          ...ready,
          download_url: null,
          copy_text: 'Ayşe [GİZLENDİ] kaldı.',
          export_path: 'text_copy',
          downloads: [{ format: 'PDF', url: '/api/jobs/job/download?output_format=pdf' }],
        }}
        countLabel={tr.redactionApplied.replace('{{count}}', '1')}
        downloadLabel={tr.downloadDocument}
        backLabel={tr.backToWork}
        copyLabel={tr.copyText}
        copiedLabel={tr.textCopied}
        downloadNewPdfLabel={tr.downloadNewPdfFromUdf}
        downloadNewPdfNotice={tr.downloadNewPdfFromUdfNotice}
        onReset={() => undefined}
      />,
    )
    expect(html).toContain(tr.copyText)
    expect(html).toContain('[GİZLENDİ]')
    expect(html).toContain(tr.downloadNewPdfFromUdf)
    expect(html).toContain(tr.downloadNewPdfFromUdfNotice)
    expect(html).not.toContain('UDF indir')
    expect(html).not.toContain('Download UDF')
    expect(html).not.toContain('output_format=udf')
  })
})
