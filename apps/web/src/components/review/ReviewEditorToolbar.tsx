import { useEffect, useState, type ReactNode } from 'react'
import type { DocumentViewMode, EditorTool } from '../../state/types'
import {
  REDACT_FILLS,
  redactFillLabelKey,
} from './documentFonts'
import { ColorRow } from './ManualAreaPopover'
import {
  canZoomIn,
  canZoomOut,
  ZOOM_MAX_PERCENT,
  ZOOM_MIN_PERCENT,
} from './zoom'

type Props = {
  fileName: string
  tool: EditorTool
  viewMode: DocumentViewMode
  zoomPercent: number
  page: number
  pageCount: number
  textSelectAvailable: boolean
  geometryTools?: boolean
  t: (key: string, options?: Record<string, unknown>) => string
  onTool: (tool: EditorTool) => void
  onViewMode: (mode: DocumentViewMode) => void
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onZoomOut: () => void
  onZoomIn: () => void
  onZoomReset: () => void
  onPageChange: (page: number) => void
  hasSelectedDetection?: boolean
  showFillPicker?: boolean
  selectedFill?: string | null
  onFillChange?: (color: string) => void
}

export function ReviewEditorToolbar({
  fileName,
  tool,
  viewMode,
  zoomPercent,
  page,
  pageCount,
  textSelectAvailable,
  geometryTools = true,
  t,
  onTool,
  onViewMode,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onZoomOut,
  onZoomIn,
  onZoomReset,
  onPageChange,
  hasSelectedDetection,
  showFillPicker = false,
  selectedFill = null,
  onFillChange,
}: Props) {
  const hint =
    tool === 'add-text'
      ? t('workspace.drawTextHint')
      : tool === 'select-text'
        ? t('workspace.selectTextHint')
        : tool === 'redact-area'
          ? t('workspace.drawRedactHint')
          : tool === 'select' && viewMode === 'detections'
            ? t(
                hasSelectedDetection
                  ? 'workspace.resizeDetectionActive'
                  : 'workspace.resizeDetectionHint',
              )
            : null

  return (
    <header className="review-editor-toolbar">
      <div className="review-chrome">
        <div className="review-chrome-start">
          <div className="review-chrome-doc">
            <span className="review-file-badge" aria-hidden="true">
              <FileIcon />
            </span>
            <span className="review-file-link" title={fileName}>
              {fileName}
            </span>
          </div>

          <span className="review-chrome-rule" aria-hidden="true" />

          <div className="review-chrome-tools" role="toolbar" aria-label={t('workspace.tools')}>
            {geometryTools && (
              <ToolButton
                active={tool === 'redact-area'}
                icon={<MaskIcon />}
                label={t('workspace.toolRedactArea')}
                shortcut="R"
                onClick={() => onTool('redact-area')}
              />
            )}
            {geometryTools && (
              <ToolButton
                active={tool === 'add-text'}
                icon={<TextIcon />}
                label={t('workspace.toolAddText')}
                shortcut="T"
                onClick={() => onTool('add-text')}
              />
            )}
            {textSelectAvailable && (
              <ToolButton
                active={tool === 'select-text'}
                icon={<SelectTextIcon />}
                label={t('workspace.toolSelectText')}
                onClick={() => onTool('select-text')}
              />
            )}
            {showFillPicker && viewMode === 'preview' && onFillChange && selectedFill ? (
              <div
                className="review-fill-swatches"
                role="group"
                aria-label={t('workspace.fillColor')}
              >
                <ColorRow
                  colors={REDACT_FILLS}
                  value={selectedFill}
                  onChange={onFillChange}
                  labelFor={(color) => t(redactFillLabelKey(color))}
                />
              </div>
            ) : null}
          </div>
        </div>

        <div className="review-history" role="group" aria-label={`${t('workspace.undo')} / ${t('workspace.redo')}`}>
          <button
            type="button"
            className="review-history-btn"
            disabled={!canUndo}
            title={`${t('workspace.undo')} (Ctrl+Z)`}
            aria-label={t('workspace.undo')}
            onClick={onUndo}
          >
            <span className="review-tool-icon" aria-hidden="true">
              <UndoIcon />
            </span>
            <span>{t('workspace.undo')}</span>
          </button>
          <button
            type="button"
            className="review-history-btn"
            disabled={!canRedo}
            title={`${t('workspace.redo')} (Ctrl+Shift+Z)`}
            aria-label={t('workspace.redo')}
            onClick={onRedo}
          >
            <span className="review-tool-icon" aria-hidden="true">
              <RedoIcon />
            </span>
            <span>{t('workspace.redo')}</span>
          </button>
        </div>

        <div className="review-chrome-end">
          <div className="review-view-toggle" role="group" aria-label={t('workspace.viewMode')}>
            <button
              type="button"
              className={viewMode === 'detections' ? 'on' : ''}
              aria-pressed={viewMode === 'detections'}
              onClick={() => onViewMode('detections')}
            >
              {t('workspace.viewDetections')}
            </button>
            <button
              type="button"
              className={viewMode === 'preview' ? 'on' : ''}
              aria-pressed={viewMode === 'preview'}
              onClick={() => onViewMode('preview')}
            >
              {t('workspace.viewPreview')}
            </button>
          </div>

          <div className="review-chrome-nav">
            <div
              className={`review-well review-zoom-well${canZoomOut(zoomPercent) ? '' : ' is-zoom-min'}${canZoomIn(zoomPercent) ? '' : ' is-zoom-max'}`}
              role="group"
              aria-label={t('workspace.zoom')}
            >
              <button
                type="button"
                className="review-well-btn"
                aria-label={
                  canZoomOut(zoomPercent)
                    ? t('workspace.zoomOut')
                    : t('workspace.zoomOutLimit', { percent: ZOOM_MIN_PERCENT })
                }
                title={
                  canZoomOut(zoomPercent)
                    ? t('workspace.zoomOut')
                    : t('workspace.zoomOutLimit', { percent: ZOOM_MIN_PERCENT })
                }
                disabled={!canZoomOut(zoomPercent)}
                onClick={onZoomOut}
              >
                −
              </button>
              <button
                type="button"
                className="review-zoom-value"
                title={t('workspace.resetZoom')}
                onClick={onZoomReset}
              >
                {zoomPercent}%
              </button>
              <button
                type="button"
                className="review-well-btn"
                aria-label={
                  canZoomIn(zoomPercent)
                    ? t('workspace.zoomIn')
                    : t('workspace.zoomInLimit', { percent: ZOOM_MAX_PERCENT })
                }
                title={
                  canZoomIn(zoomPercent)
                    ? t('workspace.zoomIn')
                    : t('workspace.zoomInLimit', { percent: ZOOM_MAX_PERCENT })
                }
                disabled={!canZoomIn(zoomPercent)}
                onClick={onZoomIn}
              >
                +
              </button>
            </div>

            <PageJump page={page} pageCount={pageCount} t={t} onPageChange={onPageChange} />
          </div>
        </div>
      </div>

      {hint && <p className="review-tool-hint">{hint}</p>}
    </header>
  )
}

function ToolButton({
  icon,
  label,
  shortcut,
  active,
  onClick,
}: {
  icon: ReactNode
  label: string
  shortcut?: string
  active?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={`review-tool-btn${active ? ' is-active' : ''}`}
      title={shortcut ? `${label} (${shortcut})` : label}
      aria-label={label}
      aria-pressed={active}
      onClick={onClick}
    >
      <span className="review-tool-icon" aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
    </button>
  )
}

function PageJump({
  page,
  pageCount,
  t,
  onPageChange,
}: {
  page: number
  pageCount: number
  t: (key: string, options?: Record<string, unknown>) => string
  onPageChange: (page: number) => void
}) {
  const [draft, setDraft] = useState(String(page))

  useEffect(() => {
    setDraft(String(page))
  }, [page])

  const commit = () => {
    const parsed = Number.parseInt(draft, 10)
    if (!Number.isFinite(parsed)) {
      setDraft(String(page))
      return
    }
    const next = Math.min(pageCount, Math.max(1, parsed))
    setDraft(String(next))
    if (next !== page) onPageChange(next)
  }

  return (
    <div className="review-well review-page-well" role="group" aria-label={t('workspace.pageNav')}>
      <button
        type="button"
        className="review-well-btn"
        aria-label={t('workspace.prevPage')}
        title={t('workspace.prevPage')}
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        ‹
      </button>
      <label className="review-page-jump">
        <input
          className="review-page-input"
          type="text"
          inputMode="numeric"
          value={draft}
          aria-label={t('workspace.goToPage')}
          onChange={(event) => setDraft(event.target.value.replace(/\D/g, '').slice(0, 4))}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter') event.currentTarget.blur()
          }}
        />
        <span className="review-page-total">/ {pageCount}</span>
      </label>
      <button
        type="button"
        className="review-well-btn"
        aria-label={t('workspace.nextPage')}
        title={t('workspace.nextPage')}
        disabled={page >= pageCount}
        onClick={() => onPageChange(page + 1)}
      >
        ›
      </button>
    </div>
  )
}

function FileIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M4.2 2.4h5.1L12 5.2v8.4H4.2V2.4Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M9.2 2.5v2.9H12" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  )
}

function MaskIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2" y="3.4" width="12" height="9.2" rx="1.6" fill="currentColor" opacity="0.22" />
      <rect x="2" y="3.4" width="12" height="9.2" rx="1.6" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  )
}

function TextIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3.2 4h9.6M8 4v8.2M5.2 12.2h5.6"
        stroke="currentColor"
        strokeWidth="1.45"
        strokeLinecap="round"
      />
    </svg>
  )
}

function SelectTextIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M5 2.6h6M8 2.6v10.8M5 13.4h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function UndoIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M4.2 6.2H11a3.2 3.2 0 0 1 0 6.4H9.4"
        stroke="currentColor"
        strokeWidth="1.45"
        strokeLinecap="round"
      />
      <path
        d="M6.4 3.8 3.8 6.2 6.4 8.6"
        stroke="currentColor"
        strokeWidth="1.45"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function RedoIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M11.8 6.2H5a3.2 3.2 0 0 0 0 6.4h1.6"
        stroke="currentColor"
        strokeWidth="1.45"
        strokeLinecap="round"
      />
      <path
        d="M9.6 3.8 12.2 6.2 9.6 8.6"
        stroke="currentColor"
        strokeWidth="1.45"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
