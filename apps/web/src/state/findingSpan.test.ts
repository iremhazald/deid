import { describe, expect, it } from 'vitest'
import {
  clampSpanAgainstOthers,
  locateCorrectedSpan,
  spanFromGrip,
  spanStepOverlaps,
  stepFindingSpan,
} from './findingSpan'

const text = 'Mağdur Hande Karakan geldi.'
const hande = { start: 7, end: 12 }

describe('stepFindingSpan', () => {
  it('extends the end by one word over the unchanged text', () => {
    const next = stepFindingSpan(text, hande, 'end', 'grow')
    expect(next).toEqual({ start: 7, end: 20 })
    expect(text.slice(next!.start, next!.end)).toBe('Hande Karakan')
  })

  it('extends the start by one word', () => {
    const next = stepFindingSpan(text, hande, 'start', 'grow')
    expect(text.slice(next!.start, next!.end)).toBe('Mağdur Hande')
  })

  it('shrinks either edge but never empties the finding', () => {
    const both = { start: 7, end: 20 }
    expect(text.slice(...Object.values(stepFindingSpan(text, both, 'end', 'shrink')!) as [number, number])).toBe('Hande')
    expect(text.slice(...Object.values(stepFindingSpan(text, both, 'start', 'shrink')!) as [number, number])).toBe('Karakan')
    expect(stepFindingSpan(text, hande, 'end', 'shrink')).toBeNull()
    expect(stepFindingSpan(text, hande, 'start', 'shrink')).toBeNull()
  })

  it('stops at the document edges', () => {
    expect(stepFindingSpan(text, { start: 0, end: 6 }, 'start', 'grow')).toBeNull()
    expect(stepFindingSpan(text, { start: 21, end: text.length }, 'end', 'grow')).toBeNull()
  })

  it('crosses a line break, as PDF text often splits a name', () => {
    const wrapped = 'Mağdur Hande\nKarakan geldi.'
    const next = stepFindingSpan(wrapped, hande, 'end', 'grow')
    expect(wrapped.slice(next!.start, next!.end)).toBe('Hande\nKarakan')
  })
})

describe('locateCorrectedSpan', () => {
  it('prefers the occurrence that overlaps the original finding', () => {
    const doc = 'Hande Karakan ... Mağdur Hande Karakan geldi.'
    const original = { start: doc.lastIndexOf('Hande'), end: doc.lastIndexOf('Hande') + 5 }
    const next = locateCorrectedSpan(doc, original, ' Hande Karakan ')
    expect(next).toEqual({ start: original.start, end: original.start + 'Hande Karakan'.length })
  })

  it('returns null for text that is not near the finding', () => {
    expect(locateCorrectedSpan(text, hande, 'Mersin')).toBeNull()
    expect(locateCorrectedSpan(text, hande, '   ')).toBeNull()
  })
})

describe('spanFromGrip', () => {
  const origin = { start: 7, end: 12 }

  it('extends and shortens from every side', () => {
    expect(spanFromGrip(origin, 'w', 0, text.length)).toEqual({ start: 0, end: 12 })
    expect(spanFromGrip(origin, 'e', 20, text.length)).toEqual({ start: 7, end: 20 })
    expect(spanFromGrip(origin, 'n', 4, text.length, { x: 0, y: -30 })).toEqual({ start: 4, end: 12 })
    expect(spanFromGrip(origin, 's', 18, text.length, { x: 0, y: 24 })).toEqual({ start: 7, end: 18 })
  })

  it('lets a corner follow the stronger axis', () => {
    expect(spanFromGrip(origin, 'ne', 20, text.length, { x: 28, y: -4 })).toEqual({ start: 7, end: 20 })
    expect(spanFromGrip(origin, 'ne', 2, text.length, { x: 2, y: -30 })).toEqual({ start: 2, end: 12 })
    expect(spanFromGrip(origin, 'sw', 0, text.length, { x: -20, y: 3 })).toEqual({ start: 0, end: 12 })
    expect(spanFromGrip(origin, 'sw', 16, text.length, { x: -2, y: 22 })).toEqual({ start: 7, end: 16 })
  })

  it('keeps the left and top grips on the start edge', () => {
    expect(spanFromGrip(origin, 'n', 40, 50)).toEqual({ start: 11, end: 12 })
    expect(spanFromGrip(origin, 'w', 2, 50)).toEqual({ start: 2, end: 12 })
    expect(spanFromGrip(origin, 's', 0, 50)).toEqual({ start: 7, end: 8 })
    expect(spanFromGrip(origin, 'e', 30, 50)).toEqual({ start: 7, end: 30 })
  })

  it('shortens the grabbed edge while the pointer stays inside the span', () => {
    expect(spanFromGrip(origin, 'e', 9, 50)).toEqual({ start: 7, end: 9 })
    expect(spanFromGrip(origin, 'w', 10, 50)).toEqual({ start: 10, end: 12 })
  })
})

describe('clampSpanAgainstOthers', () => {
  it('stops the growing edge at the neighbour', () => {
    const others = [{ id: 'b', start: 13, end: 20 }]
    expect(clampSpanAgainstOthers({ start: 7, end: 18 }, 'a', others, false)).toEqual({
      start: 7,
      end: 13,
    })
    expect(clampSpanAgainstOthers({ start: 10, end: 16 }, 'b', [{ id: 'a', start: 7, end: 12 }], true)).toEqual({
      start: 12,
      end: 16,
    })
  })
})

describe('spanStepOverlaps', () => {
  it('blocks a step that runs into another finding', () => {
    const others = [
      { id: 'a', start: 7, end: 12 },
      { id: 'b', start: 13, end: 20 },
    ]
    expect(spanStepOverlaps({ start: 7, end: 20 }, 'a', others)).toBe(true)
    expect(spanStepOverlaps({ start: 0, end: 12 }, 'a', others)).toBe(false)
  })
})
