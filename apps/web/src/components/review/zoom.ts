export const ZOOM_MIN = 0.4
export const ZOOM_MAX = 1.7
export const ZOOM_STEP = 0.1
export const ZOOM_MIN_PERCENT = 40
export const ZOOM_MAX_PERCENT = 170

export function clampZoom(value: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number(value.toFixed(2))))
}

export function canZoomOut(percent: number): boolean {
  return percent > ZOOM_MIN_PERCENT
}

export function canZoomIn(percent: number): boolean {
  return percent < ZOOM_MAX_PERCENT
}
