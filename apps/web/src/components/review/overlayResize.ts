export type OverlayBox = {
  x0: number
  y0: number
  x1: number
  y1: number
}

export type ResizeEdge = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export const RESIZE_EDGES: ResizeEdge[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

const MIN_SIZE = 6

export function applyOverlayResize(
  box: OverlayBox,
  edge: ResizeEdge,
  dx: number,
  dy: number,
  bounds: { width: number; height: number },
): OverlayBox {
  let { x0, y0, x1, y1 } = box
  if (edge.includes('w')) x0 += dx
  if (edge.includes('e')) x1 += dx
  if (edge.includes('n')) y0 += dy
  if (edge.includes('s')) y1 += dy
  x0 = Math.max(0, Math.min(x0, bounds.width - MIN_SIZE))
  y0 = Math.max(0, Math.min(y0, bounds.height - MIN_SIZE))
  x1 = Math.max(MIN_SIZE, Math.min(x1, bounds.width))
  y1 = Math.max(MIN_SIZE, Math.min(y1, bounds.height))
  if (x1 - x0 < MIN_SIZE) {
    if (edge.includes('w')) x0 = x1 - MIN_SIZE
    else x1 = x0 + MIN_SIZE
  }
  if (y1 - y0 < MIN_SIZE) {
    if (edge.includes('n')) y0 = y1 - MIN_SIZE
    else y1 = y0 + MIN_SIZE
  }
  return {
    x0: Math.max(0, x0),
    y0: Math.max(0, y0),
    x1: Math.min(bounds.width, x1),
    y1: Math.min(bounds.height, y1),
  }
}

export function replaceOverlayRect(
  rects: OverlayBox[],
  index: number,
  next: OverlayBox,
): OverlayBox[] {
  return rects.map((rect, item) => (item === index ? next : rect))
}
