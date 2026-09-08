import { describe, expect, it } from 'vitest'
import {
  isElementVisibleInCanvas,
  pageInViewFromRects,
  placePopoverNearBox,
  scrollOffsetToCenter,
} from './overlayScroll'

describe('scrollOffsetToCenter', () => {
  it('centers a box that sits far down the page', () => {
    const top = scrollOffsetToCenter(
      { scroll: 0, start: 0, size: 400 },
      { start: 800, size: 20 },
    )
    expect(top).toBe(610)
  })

  it('does not scroll above the start of the canvas', () => {
    expect(
      scrollOffsetToCenter(
        { scroll: 0, start: 0, size: 400 },
        { start: 10, size: 20 },
      ),
    ).toBe(0)
  })
})

describe('pageInViewFromRects', () => {
  const pages = [
    { page: 1, top: 0, bottom: 400 },
    { page: 2, top: 428, bottom: 828 },
    { page: 3, top: 856, bottom: 1256 },
  ]

  it('reports the page that fills most of the viewport', () => {
    expect(pageInViewFromRects(pages, { top: 350, bottom: 750 })).toBe(2)
    expect(pageInViewFromRects(pages, { top: 0, bottom: 300 })).toBe(1)
    expect(pageInViewFromRects(pages, { top: 900, bottom: 1300 })).toBe(3)
  })
})

describe('isElementVisibleInCanvas', () => {
  it('is true when the box sits inside the canvas', () => {
    const canvas = {
      getBoundingClientRect: () => ({ top: 80, bottom: 680, left: 20, right: 620 }),
    } as HTMLElement
    const target = {
      getBoundingClientRect: () => ({ top: 240, bottom: 280, left: 80, right: 200 }),
    } as HTMLElement
    expect(isElementVisibleInCanvas(canvas, target)).toBe(true)
  })

  it('is false when the box is above the canvas', () => {
    const canvas = {
      getBoundingClientRect: () => ({ top: 80, bottom: 680, left: 20, right: 620 }),
    } as HTMLElement
    const target = {
      getBoundingClientRect: () => ({ top: -40, bottom: 10, left: 80, right: 200 }),
    } as HTMLElement
    expect(isElementVisibleInCanvas(canvas, target)).toBe(false)
  })
})

describe('placePopoverNearBox', () => {
  it('opens to the right of the selection when there is room', () => {
    const place = placePopoverNearBox(
      { left: 80, top: 120, right: 200, bottom: 150 },
      { width: 320, height: 420 },
      { width: 1200, height: 800 },
    )
    expect(place.x).toBe(210)
    expect(place.y).toBe(120)
    expect(place.maxHeight).toBeGreaterThan(180)
  })

  it('keeps the popover on screen and leaves room to scroll', () => {
    const place = placePopoverNearBox(
      { left: 40, top: 600, right: 180, bottom: 760 },
      { width: 320, height: 520 },
      { width: 400, height: 800 },
    )
    expect(place.x).toBeGreaterThanOrEqual(12)
    expect(place.x + 320).toBeLessThanOrEqual(388)
    expect(place.y + place.maxHeight).toBeLessThanOrEqual(800)
  })
})
