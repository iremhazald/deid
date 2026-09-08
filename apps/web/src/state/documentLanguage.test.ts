import { describe, expect, it } from 'vitest'
import {
  DEFAULT_DOCUMENT_LANGUAGE,
  DOCUMENT_LANGUAGE_UI_OPTIONS,
  analyzeLanguagePayload,
  defaultDocumentLanguageForUi,
  documentTagLanguage,
  nextDocumentLanguageAfterUiSwitch,
} from './documentLanguage'

describe('document language state', () => {
  it('keeps auto as an internal default, not a UI option', () => {
    expect(DEFAULT_DOCUMENT_LANGUAGE).toBe('auto')
    expect(DOCUMENT_LANGUAGE_UI_OPTIONS).toEqual(['tr', 'en'])
    expect(DOCUMENT_LANGUAGE_UI_OPTIONS).not.toContain('auto')
  })

  it('defaults the upload control to the current UI language', () => {
    expect(defaultDocumentLanguageForUi('tr')).toBe('tr')
    expect(defaultDocumentLanguageForUi('en')).toBe('en')
  })

  it('keeps auto when the UI switches to English', () => {
    expect(nextDocumentLanguageAfterUiSwitch('auto', 'en')).toBe('auto')
  })

  it('keeps explicit Turkish after a UI switch to English', () => {
    expect(nextDocumentLanguageAfterUiSwitch('tr', 'en')).toBe('tr')
  })

  it('keeps explicit English after a UI switch to Turkish', () => {
    expect(nextDocumentLanguageAfterUiSwitch('en', 'tr')).toBe('en')
  })

  it('does not overwrite a document-language default when the UI later changes', () => {
    const chosen = defaultDocumentLanguageForUi('tr')
    expect(nextDocumentLanguageAfterUiSwitch(chosen, 'en')).toBe('tr')
  })

  it('sends document language in the analyze payload, not the UI locale', () => {
    expect(analyzeLanguagePayload('auto', 'en')).toBe('auto')
    expect(analyzeLanguagePayload('tr', 'en')).toBe('tr')
    expect(analyzeLanguagePayload('en', 'tr')).toBe('en')
  })

  it('resolves tag language from the persisted document language, never the UI', () => {
    expect(documentTagLanguage({ resolved_document_language: 'en', requested_document_language: 'tr' })).toBe('en')
    expect(documentTagLanguage({ requested_document_language: 'en' })).toBe('en')
    expect(documentTagLanguage({ requested_document_language: 'tr' })).toBe('tr')
    expect(documentTagLanguage({})).toBe('tr')
  })
})
