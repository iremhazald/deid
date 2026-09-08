import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { REDACT_FILLS } from './documentFonts'
import { ReviewEditorToolbar } from './ReviewEditorToolbar'

const t = (key: string) => key

const base = {
  fileName: 'ornek.pdf',
  tool: 'select' as const,
  viewMode: 'detections' as const,
  page: 1,
  pageCount: 3,
  textSelectAvailable: false,
  t,
  onTool: () => undefined,
  onViewMode: () => undefined,
  canUndo: false,
  canRedo: false,
  onUndo: () => undefined,
  onRedo: () => undefined,
  onZoomOut: () => undefined,
  onZoomIn: () => undefined,
  onZoomReset: () => undefined,
  onPageChange: () => undefined,
}

describe('ReviewEditorToolbar zoom limits', () => {
  it('disables minus at 40% and plus at 170%', () => {
    const min = renderToStaticMarkup(<ReviewEditorToolbar {...base} zoomPercent={40} />)
    expect(min).toContain('is-zoom-min')
    expect(min).toContain('workspace.zoomOutLimit')
    expect(min).toMatch(/disabled[^>]*workspace\.zoomOutLimit|workspace\.zoomOutLimit[^>]*disabled/)

    const max = renderToStaticMarkup(<ReviewEditorToolbar {...base} zoomPercent={170} />)
    expect(max).toContain('is-zoom-max')
    expect(max).toContain('workspace.zoomInLimit')
    expect(max).not.toContain('is-zoom-min')
  })

  it('keeps both zoom buttons enabled in the middle', () => {
    const html = renderToStaticMarkup(<ReviewEditorToolbar {...base} zoomPercent={110} />)
    expect(html).not.toContain('is-zoom-min')
    expect(html).not.toContain('is-zoom-max')
    expect(html).toContain('workspace.zoomOut')
    expect(html).toContain('workspace.zoomIn')
    expect(html).not.toContain('workspace.zoomOutLimit')
    expect(html).not.toContain('workspace.zoomInLimit')
  })
})

describe('ReviewEditorToolbar redact fill swatches', () => {
  it('keeps black then white as the first two fills', () => {
    expect([...REDACT_FILLS]).toEqual([
      '#161616',
      '#ffffff',
      '#1e3a5f',
      '#5c1f1f',
      '#3d3d3d',
    ])
  })

  it('hides fill swatches until a redacted detection is selected in preview', () => {
    const hidden = renderToStaticMarkup(
      <ReviewEditorToolbar {...base} viewMode="preview" zoomPercent={110} />,
    )
    expect(hidden).not.toContain('review-fill-swatches')

    const detections = renderToStaticMarkup(
      <ReviewEditorToolbar
        {...base}
        viewMode="detections"
        zoomPercent={110}
        showFillPicker
        selectedFill="#161616"
        onFillChange={() => undefined}
      />,
    )
    expect(detections).not.toContain('review-fill-swatches')
  })

  it('shows black then white and three more fills between add text and undo', () => {
    const html = renderToStaticMarkup(
      <ReviewEditorToolbar
        {...base}
        viewMode="preview"
        zoomPercent={110}
        showFillPicker
        selectedFill="#161616"
        onFillChange={() => undefined}
      />,
    )
    expect(html).toContain('review-fill-swatches')
    expect(html).toContain('workspace.fillColor')
    const black = html.indexOf('background:#161616')
    const white = html.indexOf('background:#ffffff')
    const navy = html.indexOf('background:#1e3a5f')
    const burgundy = html.indexOf('background:#5c1f1f')
    const gray = html.indexOf('background:#3d3d3d')
    expect(black).toBeGreaterThan(html.indexOf('workspace.toolAddText'))
    expect(white).toBeGreaterThan(black)
    expect(navy).toBeGreaterThan(white)
    expect(burgundy).toBeGreaterThan(navy)
    expect(gray).toBeGreaterThan(burgundy)
    expect(gray).toBeGreaterThan(-1)
    expect(html.indexOf('workspace.undo')).toBeGreaterThan(gray)
  })
})

describe('ReviewEditorToolbar document actions', () => {
  it('does not add a Remove finding or merge control to the toolbar', () => {
    const html = renderToStaticMarkup(
      <ReviewEditorToolbar {...base} zoomPercent={110} hasSelectedDetection />,
    )
    expect(html).not.toContain('workspace.contextRemoveFinding')
    expect(html).not.toContain('workspace.removeDetection')
    expect(html).not.toContain('workspace.contextMergePerson')
    expect(html).not.toContain('workspace.manualMergeTitle')
    expect(html).toContain('workspace.undo')
    expect(html).toContain('workspace.redo')
  })
})
