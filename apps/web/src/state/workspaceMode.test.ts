import { describe, expect, it } from 'vitest'
import { previewTransformLocal } from './helpers'
import type { Entity } from './types'
import {
  asksWorkspaceMode,
  offsetsForSelectedSource,
  showsPdfPageViewer,
  workspaceModeForSelectedFile,
} from './workspaceMode'

describe('DOCX workspace routing', () => {
  it('does not ask the PDF question and always uses text', () => {
    expect(asksWorkspaceMode('claim.pdf')).toBe(true)
    expect(asksWorkspaceMode('claim.docx')).toBe(false)
    expect(asksWorkspaceMode(undefined)).toBe(false)
    expect(workspaceModeForSelectedFile('claim.docx', null)).toBe('TEXT')
    expect(workspaceModeForSelectedFile('claim.docx', 'DOCUMENT')).toBe('TEXT')
    expect(workspaceModeForSelectedFile('claim.pdf', null)).toBeNull()
    expect(workspaceModeForSelectedFile('claim.pdf', 'DOCUMENT')).toBe('DOCUMENT')
    expect(asksWorkspaceMode('dilekce.udf')).toBe(false)
    expect(workspaceModeForSelectedFile('dilekce.udf', null)).toBe('TEXT')
    expect(workspaceModeForSelectedFile('dilekce.udf', 'DOCUMENT')).toBe('TEXT')
  })
})

describe('showsPdfPageViewer', () => {
  it('keeps an omitted workspace on the PDF page viewer', () => {
    expect(showsPdfPageViewer('PDF', undefined)).toBe(true)
    expect(showsPdfPageViewer('PDF', null)).toBe(true)
    expect(showsPdfPageViewer('PDF', 'DOCUMENT')).toBe(true)
  })

  it('uses the text sheet for PDF text mode and for non-PDF sources', () => {
    expect(showsPdfPageViewer('PDF', 'TEXT')).toBe(false)
    expect(showsPdfPageViewer('DOCX', 'DOCUMENT')).toBe(false)
    expect(showsPdfPageViewer('TEXT', undefined)).toBe(false)
  })
})

describe('offsetsForSelectedSource', () => {
  const source = 'Hello Ayşe Demir met Ayşe Demir today.'

  it('keeps a candidate that still matches the immutable source', () => {
    expect(offsetsForSelectedSource(source, 'Ayşe Demir', 6)).toEqual({
      start: 6,
      end: 16,
    })
    expect(source.slice(6, 16)).toBe('Ayşe Demir')
  })

  it('uses the only occurrence when the DOM candidate no longer matches', () => {
    const unique = 'Contact ada@example.com today.'
    expect(offsetsForSelectedSource(unique, 'ada@example.com', 0)).toEqual({
      start: 8,
      end: 23,
    })
  })

  it('does not guess when the same phrase occurs twice and the candidate misses', () => {
    expect(offsetsForSelectedSource(source, 'Ayşe Demir', 0)).toBeNull()
  })

  it('does not retarget offsets after a transformed preview string', () => {
    const preview = source.replace('Ayşe Demir', '[GİZLENDİ]')
    expect(offsetsForSelectedSource(source, 'Ayşe Demir', 6)?.start).toBe(6)
    expect(preview).not.toBe(source)
    expect(source.slice(6, 16)).toBe('Ayşe Demir')
  })
})

describe('text workspace preview', () => {
  it('keeps block characters in the review preview and leaves the source unchanged', () => {
    const text = 'John Brown'
    const entity: Entity = {
      id: 'p1',
      text,
      type: 'PERSON_NAME',
      start: 0,
      end: text.length,
      page: 0,
      detector: 'test',
      method: 'DETERMINISTIC',
      validated: true,
      recommended: true,
      recommended_strategy: 'REDACT',
    }
    const preview = previewTransformLocal(
      text,
      [entity],
      { p1: 'REDACT' },
      {},
      { p1: 'REDACT' },
      'tr',
    )
    expect(preview).toBe('█'.repeat(text.length))
    expect(preview).not.toContain('[GİZLENDİ]')
    expect(preview).not.toContain('[REDACTED]')
    expect(text).toBe('John Brown')
  })
})
