type Props = {
  hasFile: boolean
  hasLanguage: boolean
  hasWorkspace: boolean
  t: (key: string, options?: Record<string, unknown>) => string
  onStart: () => void
}

export function LocalScanStart({
  hasFile,
  hasLanguage,
  hasWorkspace,
  t,
  onStart,
}: Props) {
  const canStart = hasFile && hasLanguage && hasWorkspace
  const hint = !hasFile
    ? t('localScan.needFile')
    : !hasLanguage
      ? t('localScan.needLanguage')
      : !hasWorkspace
        ? t('workspaceChoice.needChoice')
        : null

  return (
    <div className="local-scan-start">
      <button
        type="button"
        className="local-scan-start-btn"
        disabled={!canStart}
        onClick={onStart}
      >
        {t('localScan.cta')}
      </button>
      {hint && (
        <p className="local-scan-hint" role="status">
          {hint}
        </p>
      )}
    </div>
  )
}
