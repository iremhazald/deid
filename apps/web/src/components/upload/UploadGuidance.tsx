type Props = {
  t: (key: string, options?: Record<string, unknown>) => string
}

function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 1.6 13.2 3.6v4.1c0 3.05-2.05 5.2-5.2 6.55C4.85 12.9 2.8 10.75 2.8 7.7V3.6L8 1.6Z"
        stroke="currentColor"
        strokeWidth="1.15"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function UploadGuidance({ t }: Props) {
  return (
    <div className="upload-guidance">
      <div className="upload-guidance-card">
        <span className="upload-guidance-icon">
          <ShieldIcon />
        </span>
        <div className="upload-guidance-copy">
          <p>{t('localScan.privacy')} {t('localScan.reviewHint')}</p>
        </div>
      </div>
      <div className="upload-notice-box">
        <p className="upload-notice-title">{t('uploadNotice.title')}</p>
        <p>{t('uploadNotice.body')}</p>
        <p className="upload-notice-disclaimer">{t('uploadNotice.disclaimer')}</p>
      </div>
    </div>
  )
}
