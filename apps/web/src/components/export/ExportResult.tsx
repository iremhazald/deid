import { useState } from 'react'
import { assetUrl } from '../../api/client'
import type { Result } from '../../state/types'
import { writeClipboardText } from './copyText'

type Props = {
  result: Result
  countLabel: string
  downloadLabel: string
  backLabel: string
  readyTitle?: string
  failTitle?: string
  failBody?: string
  warnTitle?: string
  warnBody?: string
  copyLabel?: string
  copiedLabel?: string
  textReadyTitle?: string
  downloadNewDocxLabel?: string
  downloadNewDocxNotice?: string
  downloadNewPdfLabel?: string
  downloadNewPdfNotice?: string
  onReset: () => void
}

export function ExportResult({
  result,
  countLabel,
  downloadLabel,
  backLabel,
  readyTitle,
  failTitle,
  failBody,
  warnTitle,
  warnBody,
  copyLabel,
  copiedLabel,
  textReadyTitle,
  downloadNewDocxLabel,
  downloadNewDocxNotice,
  downloadNewPdfLabel,
  downloadNewPdfNotice,
  onReset,
}: Props) {
  const [copied, setCopied] = useState(false)
  const failed = result.validation.status === 'FAILED'
  const hasCopy = result.copy_text != null
  const canDownload = Boolean(result.download_url) && !hasCopy
  const blocked = failed && !canDownload && !hasCopy
  const caution = failed && (canDownload || hasCopy)
  const title = hasCopy
    ? failed
      ? (warnTitle ?? textReadyTitle ?? readyTitle)
      : (textReadyTitle ?? readyTitle)
    : blocked
      ? failTitle
      : caution
        ? warnTitle
        : readyTitle
  const body = hasCopy ? null : blocked ? failBody : caution ? warnBody : null

  const onCopy = async () => {
    if (result.copy_text == null) return
    try {
      await writeClipboardText(result.copy_text, (value) => navigator.clipboard.writeText(value))
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="export-screen">
      <article
        className={`export-card export-ready-card${hasCopy ? ' has-copy-text' : ''}${blocked ? ' status-failed' : caution ? ' status-warning' : ''}`}
      >
        {title ? <h1>{title}</h1> : null}
        {body ? <p className="lead">{body}</p> : null}
        {!blocked ? <p className="export-redaction-count">{countLabel}</p> : null}
        {hasCopy ? (
          <pre className="export-copy-text" tabIndex={0}>
            {result.copy_text}
          </pre>
        ) : null}
        <div className="export-actions export-ready-actions">
          {hasCopy && (
            <button type="button" className="btn primary" onClick={() => void onCopy()}>
              {copyLabel}
            </button>
          )}
          {copied ? (
            <p className="export-copy-confirm" role="status">
              {copiedLabel}
            </p>
          ) : null}
          {hasCopy && result.downloads && result.downloads.length > 0 ? (
            <div className="export-derived">
              {result.downloads.map((item) => {
                const docx = item.format === 'DOCX'
                return (
                  <div key={item.format}>
                    <a className="btn ghost" href={assetUrl(item.url)}>
                      {docx ? downloadNewDocxLabel : downloadNewPdfLabel}
                    </a>
                    <p>{docx ? downloadNewDocxNotice : downloadNewPdfNotice}</p>
                  </div>
                )
              })}
            </div>
          ) : null}
          {canDownload && (
            <a className="btn primary" href={assetUrl(result.download_url ?? '')}>
              {downloadLabel}
            </a>
          )}
          <button type="button" className="btn ghost" onClick={onReset}>
            {backLabel}
          </button>
        </div>
      </article>
    </section>
  )
}
