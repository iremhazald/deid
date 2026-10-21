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
