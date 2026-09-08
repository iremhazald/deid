import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { DeIDMark } from '../brand/DeIDMark'

/** Tracks whether the page has left the very top, for the header's border state. */
function useScrolled() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const sync = () => setScrolled(window.scrollY > 4)
    sync()
    window.addEventListener('scroll', sync, { passive: true })
    return () => window.removeEventListener('scroll', sync)
  }, [])

  return scrolled
}

type PrimaryAction = {
  label: string
  count?: number
  busy?: boolean
  busyLabel?: string
  disabled?: boolean
  disabledHint?: string
  onClick: () => void
}

type Props = {
  brand: string
  language: string
  githubUrl?: string
  githubLabel: string
  languageLabel: string
  variant?: 'landing' | 'workspace'
  workspaceLabel?: string
  backLabel?: string
  newDocumentLabel?: string
  primaryAction?: PrimaryAction
  onReset: () => void
  onNewDocument?: () => void
  onLanguageChange: (language: 'tr' | 'en') => void
  children?: ReactNode
}

export function Header({
  brand,
  language,
  githubUrl,
  githubLabel,
  languageLabel,
  variant = 'landing',
  workspaceLabel,
  backLabel,
  newDocumentLabel,
  primaryAction,
  onReset,
  onNewDocument,
  onLanguageChange,
  children,
}: Props) {
  const scrolled = useScrolled()
  const workspace = variant === 'workspace'

  return (
    <header className={`app-header${scrolled ? ' is-scrolled' : ''}${workspace ? ' is-workspace-header' : ''}`}>
      <div className="app-header-inner">
        <button type="button" className="brand" onClick={onReset} aria-label={brand}>
          <span className="brand-mark">
            <DeIDMark />
          </span>
          <span className="brand-name">{brand}</span>
          {workspace && workspaceLabel && (
            <span className="workspace-chip">{workspaceLabel}</span>
          )}
        </button>

        {workspace && newDocumentLabel && onNewDocument && (
          <button type="button" className="header-new-document" onClick={onNewDocument}>
            <PlusIcon />
            <span>{newDocumentLabel}</span>
          </button>
        )}

        {children}

        <div className="header-actions">
          {workspace && primaryAction ? (
            <button
              type="button"
              className="header-apply"
              disabled={primaryAction.busy || primaryAction.disabled}
              title={primaryAction.disabled ? primaryAction.disabledHint : undefined}
              onClick={primaryAction.onClick}
            >
              <span className="header-apply-icon" aria-hidden="true">
                <ShieldIcon />
              </span>
              <span>
                {primaryAction.busy ? primaryAction.busyLabel : primaryAction.label}
              </span>
              {!primaryAction.busy && primaryAction.count ? (
                <span className="header-apply-count">{primaryAction.count}</span>
              ) : null}
            </button>
          ) : (
            workspace &&
            backLabel && (
              <button type="button" className="header-back" onClick={onReset}>
                {backLabel}
              </button>
            )
          )}
          {githubUrl && !workspace && (
            <a className="header-link" href={githubUrl} target="_blank" rel="noreferrer">
              {githubLabel}
            </a>
          )}
          <div className="lang" role="group" aria-label={languageLabel}>
            <button
              type="button"
              className={language === 'tr' ? 'on' : ''}
              aria-pressed={language === 'tr'}
              onClick={() => onLanguageChange('tr')}
            >
              TR
            </button>
            <button
              type="button"
              className={language === 'en' ? 'on' : ''}
              aria-pressed={language === 'en'}
              onClick={() => onLanguageChange('en')}
            >
              EN
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}

function ShieldIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 1.9 13 3.6v4.1c0 3-2.1 5.3-5 6.4-2.9-1.1-5-3.4-5-6.4V3.6L8 1.9Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M5.8 7.9 7.3 9.4l3-3.1"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 3v10M3 8h10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}
