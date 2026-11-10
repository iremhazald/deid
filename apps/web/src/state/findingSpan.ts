export type SpanEdge = 'start' | 'end'
export type SpanStep = 'grow' | 'shrink'

export type SpanRange = { start: number; end: number }

const isSpace = (char: string | undefined) => char !== undefined && /\s/.test(char)

/**
 * Move one edge of a finding by one word over the unchanged source text.
 * Returns null when that edge cannot move (document edge, or the finding
 * would lose its last word).
 */
export function stepFindingSpan(
  text: string,
  range: SpanRange,
  edge: SpanEdge,
  step: SpanStep,
): SpanRange | null {
  let { start, end } = range
  if (start < 0 || end > text.length || start >= end) return null

  if (edge === 'start' && step === 'grow') {
    let cursor = start
    while (cursor > 0 && isSpace(text[cursor - 1])) cursor -= 1
    if (cursor === 0) return null
    while (cursor > 0 && !isSpace(text[cursor - 1])) cursor -= 1
    start = cursor
  } else if (edge === 'end' && step === 'grow') {
    let cursor = end
    while (cursor < text.length && isSpace(text[cursor])) cursor += 1
    if (cursor === text.length) return null
    while (cursor < text.length && !isSpace(text[cursor])) cursor += 1
    end = cursor
  } else if (edge === 'start') {
    let cursor = start
    while (cursor < end && !isSpace(text[cursor])) cursor += 1
    while (cursor < end && isSpace(text[cursor])) cursor += 1
    if (cursor >= end) return null
    start = cursor
  } else {
    let cursor = end
    while (cursor > start && !isSpace(text[cursor - 1])) cursor -= 1
    while (cursor > start && isSpace(text[cursor - 1])) cursor -= 1
    if (cursor <= start) return null
    end = cursor
  }
  return { start, end }
}

const CORRECTION_WINDOW = 240

/**
 * Find a user-corrected finding text in the source, near the original range.
 * An occurrence overlapping the original wins; otherwise the closest one.
 */
export function locateCorrectedSpan(
  text: string,
  original: SpanRange,
  value: string,
): SpanRange | null {
  const needle = value.trim()
  if (!needle) return null
  const from = Math.max(0, original.start - CORRECTION_WINDOW)
  const to = Math.min(text.length, original.end + CORRECTION_WINDOW)
  let best: SpanRange | null = null
  let bestScore = Number.POSITIVE_INFINITY
  let index = text.indexOf(needle, from)
  while (index >= 0 && index + needle.length <= to) {
    const end = index + needle.length
    const overlaps = index < original.end && original.start < end
    const score = overlaps ? -1 : Math.min(Math.abs(index - original.start), Math.abs(end - original.end))
    if (score < bestScore) {
      best = { start: index, end }
      bestScore = score
    }
    index = text.indexOf(needle, index + 1)
  }
  return best
}

export type ResizeGrip = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export const RESIZE_GRIPS: ResizeGrip[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

/** North and west move the start. South and east move the end. A corner follows the stronger axis. */
export function gripMovesStart(grip: ResizeGrip, delta: { x: number; y: number }): boolean {
  if (grip === 'n' || grip === 'w' || grip === 'nw') return true
  if (grip === 's' || grip === 'e' || grip === 'se') return false
  if (grip === 'ne') return Math.abs(delta.y) > Math.abs(delta.x)
  return Math.abs(delta.x) >= Math.abs(delta.y)
}

/**
 * Place one edge on the character under the pointer.
 * The other edge stays put, and the span never becomes empty.
 */
export function spanFromGrip(
  origin: SpanRange,
  grip: ResizeGrip,
  offset: number,
  textLength: number,
  delta: { x: number; y: number } = { x: 0, y: 0 },
): SpanRange | null {
  if (origin.start >= origin.end) return null
  const clamped = Math.min(textLength, Math.max(0, offset))
  // Each grip owns one edge. The left and top move the start; the right and
  // bottom move the end. A grip never switches edges, so pulling left cannot
  // grow the right side.
  const moveStart = gripMovesStart(grip, delta)
  const start = moveStart ? Math.min(clamped, origin.end - 1) : origin.start
  const end = moveStart ? origin.end : Math.max(clamped, origin.start + 1)
  if (start < 0 || end > textLength || start >= end) return null
  return { start, end }
}

/** Grow until the span touches a neighbour instead of freezing on the first overlap. */
export function clampSpanAgainstOthers(
  next: SpanRange,
  entityId: string,
  others: ReadonlyArray<{ id: string; start: number; end: number }>,
  movingStart: boolean,
): SpanRange | null {
  let { start, end } = next
  for (const item of others) {
    if (item.id === entityId || !(item.start < end && start < item.end)) continue
    if (movingStart) start = Math.max(start, item.end)
    else end = Math.min(end, item.start)
  }
  if (start >= end) return null
  return { start, end }
}

/** The step is blocked when it would run into another finding. */
export function spanStepOverlaps(
  next: SpanRange,
  entityId: string,
  others: ReadonlyArray<{ id: string; start: number; end: number }>,
): boolean {
  return others.some(
    (item) => item.id !== entityId && item.start < next.end && next.start < item.end,
  )
}
