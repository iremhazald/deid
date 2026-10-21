import { useEffect, useRef, useState } from 'react'
import { RedactionDemo } from '../demo/RedactionDemo'
import { AnimatedRedactionText } from '../hero/AnimatedRedactionText'
import type { DocumentLanguage } from '../../state/documentLanguage'
import { DocumentLanguagePicker } from './DocumentLanguagePicker'
import { LocalScanStart } from './LocalScanStart'
import { WorkspaceModeChooser } from './WorkspaceModeChooser'
import { asksWorkspaceMode, type WorkspaceMode } from '../../state/workspaceMode'
import { isDocxFileName, isUdfFileName } from '../../state/types'
import { DropZone } from './DropZone'
import { PrivacyNotice } from './PrivacyNotice'
import { UploadGuidance } from './UploadGuidance'

type Props = {
  eyebrow: string
  /** Headline phrase that plays the detection/redaction micro-animation. */
  titleRedacted: string
  titleLead: string
  titleTail: string
  titleMuted: string
  subtitle: string
  ctaLabel: string
  openSourceTitle: string
  openSourceBody: string
  openSourceLinkLabel: string
  githubUrl?: string
  uploadTitle: string
  uploadBody: string
  dropTitle: string
  browseLabel: string
  limitsLabel: string
  processing: boolean
  privacyTitle: string
  privacyBody: string
  privacyToggle: string
  t: (key: string, options?: Record<string, unknown>) => string
  onUpload: (file: File) => void
  onStartScan: () => void
  selectedFileName?: string
  documentLanguage: DocumentLanguage
  onDocumentLanguageChange: (value: DocumentLanguage) => void
  workspaceMode: WorkspaceMode | null
  onWorkspaceModeChange: (value: WorkspaceMode) => void
}

type View = 'hero' | 'leaving' | 'upload'

/** Matches the hero exit animation in style.css. */
const EXIT_MS = 460

export function UploadHero({
  eyebrow,
  titleRedacted,
  titleLead,
  titleTail,
  titleMuted,
  subtitle,
  ctaLabel,
  openSourceTitle,
  openSourceBody,
  openSourceLinkLabel,
  githubUrl,
  uploadTitle,
  uploadBody,
  dropTitle,
  browseLabel,
  limitsLabel,
  processing,
  privacyTitle,
  privacyBody,
  privacyToggle,
  t,
  onUpload,
  onStartScan,
  selectedFileName,
  documentLanguage,
  onDocumentLanguageChange,
  workspaceMode,
  onWorkspaceModeChange,
}: Props) {
  const [view, setView] = useState<View>(() => {
    return window.location.hash === '#upload' ? 'upload' : 'hero'
  })
  const exitTimer = useRef<number | undefined>(undefined)

  useEffect(() => {
    const onHashChange = () => {
      setView(window.location.hash === '#upload' ? 'upload' : 'hero')
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => () => window.clearTimeout(exitTimer.current), [])

  const enterWorkspace = () => {
    window.history.pushState(null, '', '#upload')
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setView('upload')
      return
    }
    setView('leaving')
    exitTimer.current = window.setTimeout(() => setView('upload'), EXIT_MS)
  }

  if (view === 'upload') {
    return (
      <UploadScreen
        uploadTitle={uploadTitle}
        uploadBody={uploadBody}
        dropTitle={dropTitle}
        browseLabel={browseLabel}
        limitsLabel={limitsLabel}
        processing={processing}
        privacyTitle={privacyTitle}
        privacyBody={privacyBody}
        privacyToggle={privacyToggle}
        t={t}
        onUpload={onUpload}
        onStartScan={onStartScan}
        selectedFileName={selectedFileName}
        documentLanguage={documentLanguage}
        onDocumentLanguageChange={onDocumentLanguageChange}
        workspaceMode={workspaceMode}
        onWorkspaceModeChange={onWorkspaceModeChange}
      />
    )
  }

  return (
    <section className={`hero${view === 'leaving' ? ' is-leaving' : ''}`}>
      <div className="hero-copy">
        <p className="hero-eyebrow">{eyebrow}</p>

        <h1 className="hero-title">
          <span>
            <AnimatedRedactionText>{titleRedacted}</AnimatedRedactionText> {titleLead}
          </span>
          <span>{titleTail}</span>
          <span className="hero-title-muted">{titleMuted}</span>
        </h1>

        <p className="hero-subtitle">{subtitle}</p>

        <button type="button" className="hero-cta" onClick={enterWorkspace}>
          {ctaLabel}
          <svg width="20" height="20" viewBox="0 0 17 17" fill="none" aria-hidden="true">
            <path
              d="M3 8.5h10M9.5 5l3.5 3.5L9.5 12"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        {githubUrl && (
          <div className="hero-open-source">
            <strong>{openSourceTitle}</strong>
            <p>{openSourceBody}</p>
            <a href={githubUrl} target="_blank" rel="noreferrer">
              {openSourceLinkLabel}
              <span aria-hidden="true">↗</span>
            </a>
          </div>
        )}
      </div>

      <div className="hero-visual">
        <RedactionDemo />
      </div>
    </section>
  )
}

type UploadScreenProps = {
  uploadTitle: string
  uploadBody: string
  dropTitle: string
  browseLabel: string
  limitsLabel: string
  processing: boolean
  privacyTitle: string
  privacyBody: string
  privacyToggle: string
  t: (key: string, options?: Record<string, unknown>) => string
  onUpload: (file: File) => void
  onStartScan: () => void
  selectedFileName?: string
  documentLanguage: DocumentLanguage
  onDocumentLanguageChange: (value: DocumentLanguage) => void
  workspaceMode: WorkspaceMode | null
  onWorkspaceModeChange: (value: WorkspaceMode) => void
}

export function UploadScreen({
  uploadTitle,
  uploadBody,
  dropTitle,
  browseLabel,
  limitsLabel,
  processing,
  privacyTitle,
  privacyBody,
  privacyToggle,
  t,
  onUpload,
  onStartScan,
  selectedFileName,
  documentLanguage,
  onDocumentLanguageChange,
  workspaceMode,
  onWorkspaceModeChange,
}: UploadScreenProps) {
  return (
    <section className="upload-form">
      <div className="upload-form-head">
        <h1>{uploadTitle}</h1>
        <p>{uploadBody}</p>
      </div>

      <DropZone
        title={dropTitle}
        browseLabel={browseLabel}
        limitsLabel={limitsLabel}
        selectedName={selectedFileName}
        disabled={processing}
        onUpload={onUpload}
      />

      <div className="upload-settings">
        <DocumentLanguagePicker
          value={documentLanguage}
          t={t}
          onChange={onDocumentLanguageChange}
        />
        {asksWorkspaceMode(selectedFileName) && (
          <WorkspaceModeChooser
            value={workspaceMode}
            t={t}
            onChange={onWorkspaceModeChange}
          />
        )}
        {selectedFileName && isDocxFileName(selectedFileName) && (
          <p className="upload-docx-note">
            {t('docxUpload.source')}
            <br />
            {t('docxUpload.workspace')}
          </p>
        )}
        {selectedFileName && isUdfFileName(selectedFileName) && (
          <p className="upload-docx-note">
            {t('udfUpload.source')}
            <br />
            {t('udfUpload.workspace')}
          </p>
        )}
      </div>

      <UploadGuidance t={t} />

      <LocalScanStart
        hasFile={Boolean(selectedFileName)}
        hasLanguage={documentLanguage !== null && documentLanguage !== 'auto'}
        hasWorkspace={
          Boolean(
            selectedFileName
            && (isDocxFileName(selectedFileName) || isUdfFileName(selectedFileName)),
          )
          || workspaceMode === 'DOCUMENT'
          || workspaceMode === 'TEXT'
        }
        t={t}
        onStart={onStartScan}
      />

      <PrivacyNotice title={privacyTitle} body={privacyBody} toggleLabel={privacyToggle} />
    </section>
  )
}
