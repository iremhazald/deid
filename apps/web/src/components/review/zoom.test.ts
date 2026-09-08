import { describe, expect, it } from 'vitest'
import { canZoomIn, canZoomOut, clampZoom, ZOOM_MAX, ZOOM_MIN } from './zoom'

describe('zoom limits', () => {
  it('clamps to 40% and 170%', () => {
    expect(clampZoom(0.2)).toBe(ZOOM_MIN)
    expect(clampZoom(2.4)).toBe(ZOOM_MAX)
    expect(clampZoom(1.2)).toBe(1.2)
  })

  it('disables stepping past the ends', () => {
    expect(canZoomOut(40)).toBe(false)
    expect(canZoomOut(50)).toBe(true)
    expect(canZoomIn(170)).toBe(false)
    expect(canZoomIn(160)).toBe(true)
  })
})
