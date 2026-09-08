import { describe, expect, it } from 'vitest'
import { applyOverlayResize, replaceOverlayRect } from './overlayResize'

const box = { x0: 100, y0: 80, x1: 200, y1: 120 }
const page = { width: 595, height: 842 }

describe('applyOverlayResize', () => {
  it('extends and shortens each edge', () => {
    expect(applyOverlayResize(box, 'e', 20, 0, page)).toEqual({
      ...box,
      x1: 220,
    })
    expect(applyOverlayResize(box, 'w', -10, 0, page)).toEqual({
      ...box,
      x0: 90,
    })
    expect(applyOverlayResize(box, 's', 0, 15, page)).toEqual({
      ...box,
      y1: 135,
    })
    expect(applyOverlayResize(box, 'n', 0, -8, page)).toEqual({
      ...box,
      y0: 72,
    })
  })

  it('keeps a minimum size and stays on the page', () => {
    const tiny = applyOverlayResize(box, 'e', -500, 0, page)
    expect(tiny.x1 - tiny.x0).toBeGreaterThanOrEqual(6)
    const clamped = applyOverlayResize(box, 'w', -400, 0, page)
    expect(clamped.x0).toBe(0)
  })
})

describe('replaceOverlayRect', () => {
  it('replaces only the resized occurrence', () => {
    const next = replaceOverlayRect([box, { ...box, y0: 200, y1: 240 }], 1, {
      x0: 10,
      y0: 20,
      x1: 30,
      y1: 40,
    })
    expect(next[0]).toEqual(box)
    expect(next[1]).toEqual({ x0: 10, y0: 20, x1: 30, y1: 40 })
  })
})
