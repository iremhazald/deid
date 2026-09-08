import { assetUrl } from '../../api/client'
import type { Result } from '../../state/types'

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
  onReset,
}: Props) {
  const failed = result.validation.status === 'FAILED'
  const canDownload = Boolean(result.download_url)
  const blocked = failed && !canDownload
  const caution = failed && canDownload
  const title = blocked ? failTitle : caution ? warnTitle : readyTitle
  const body = blocked ? failBody : caution ? warnBody : null

  return (
    <section className="export-screen">
      <article
        className={`export-card export-ready-card${blocked ? ' status-failed' : caution ? ' status-warning' : ''}`}
      >
        {title ? <h1>{title}</h1> : null}
        {body ? <p className="lead">{body}</p> : null}
        {!blocked ? <p className="export-redaction-count">{countLabel}</p> : null}
        <div className="export-actions export-ready-actions">
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
