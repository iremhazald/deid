export function scrollOffsetToCenter(
  viewport: { scroll: number; start: number; size: number },
  target: { start: number; size: number },
): number {
  const center =
    viewport.scroll + (target.start - viewport.start) + target.size / 2
  return Math.max(0, center - viewport.size / 2)
}

export function pageInViewFromRects(
  pages: Array<{ page: number; top: number; bottom: number }>,
  viewport: { top: number; bottom: number },
): number | null {
  let bestPage: number | null = null
  let bestVisible = 0
  for (const page of pages) {
    if (page.page < 1) continue
    const visible = Math.max(
      0,
      Math.min(page.bottom, viewport.bottom) - Math.max(page.top, viewport.top),
    )
    if (visible > bestVisible) {
      bestVisible = visible
      bestPage = page.page
    }
  }
  return bestPage
}

export function placePopoverNearBox(
  box: { left: number; top: number; right: number; bottom: number },
  pop: { width: number; height: number },
  viewport: { width: number; height: number },
  gap = 10,
  margin = 12,
): { x: number; y: number; maxHeight: number } {
  let x = box.right + gap
  let y = box.top
  if (x + pop.width > viewport.width - margin) {
    x = box.left - pop.width - gap
  }
  if (x < margin) {
    x = Math.max(margin, Math.min(box.left, viewport.width - pop.width - margin))
    y = box.bottom + gap
  }
  const roomBelow = viewport.height - y - margin
  if (roomBelow < 180) {
    y = Math.max(margin, box.top - Math.min(pop.height, viewport.height - margin * 2) - gap)
  }
  y = Math.max(margin, Math.min(y, viewport.height - 180 - margin))
  return {
    x: Math.max(margin, Math.min(x, viewport.width - pop.width - margin)),
    y,
    maxHeight: Math.max(180, viewport.height - y - margin),
  }
}

export function isElementVisibleInCanvas(
  canvas: HTMLElement,
  target: HTMLElement,
  slop = 8,
): boolean {
  const canvasBox = canvas.getBoundingClientRect()
  const targetBox = target.getBoundingClientRect()
  return (
    targetBox.bottom > canvasBox.top + slop &&
    targetBox.top < canvasBox.bottom - slop &&
    targetBox.right > canvasBox.left + slop &&
    targetBox.left < canvasBox.right - slop
  )
}

export function scrollElementIntoCanvas(
  canvas: HTMLElement,
  target: HTMLElement,
  behavior: ScrollBehavior = 'smooth',
) {
  const canvasBox = canvas.getBoundingClientRect()
  const targetBox = target.getBoundingClientRect()
  canvas.scrollTo({
    top: scrollOffsetToCenter(
      { scroll: canvas.scrollTop, start: canvasBox.top, size: canvasBox.height },
      { start: targetBox.top, size: targetBox.height },
    ),
    left: scrollOffsetToCenter(
      { scroll: canvas.scrollLeft, start: canvasBox.left, size: canvasBox.width },
      { start: targetBox.left, size: targetBox.width },
    ),
    behavior,
  })
}
