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
})
