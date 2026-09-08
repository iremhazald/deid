export type UiLanguage = 'tr' | 'en'
export type DocumentLanguageChoice = 'tr' | 'en'
export type DocumentLanguage = 'auto' | DocumentLanguageChoice | null

/** Internal/backend default. The upload UI does not offer Auto. */
export const DEFAULT_DOCUMENT_LANGUAGE: DocumentLanguage = 'auto'

export const DOCUMENT_LANGUAGE_OPTIONS: DocumentLanguage[] = ['auto', 'tr', 'en']

export const DOCUMENT_LANGUAGE_UI_OPTIONS: DocumentLanguageChoice[] = ['tr', 'en']

/** Upload page starts with no selection; user must pick one. */
export function defaultDocumentLanguageForUpload(): null {
  return null
}

/** Product default for the upload control: match the current UI language once. */
export function defaultDocumentLanguageForUi(ui: UiLanguage): DocumentLanguageChoice {
  return ui
}

/** UI locale must never replace the user's document-language choice. */
export function nextDocumentLanguageAfterUiSwitch(
  current: DocumentLanguage,
  _nextUi: UiLanguage,
): DocumentLanguage {
  return current
}

/** Analyze payload uses document language, not the interface locale. */
export function analyzeLanguagePayload(
  documentLanguage: DocumentLanguage,
  _uiLanguage: UiLanguage,
): 'auto' | DocumentLanguageChoice | undefined {
  return documentLanguage ?? undefined
}

/** PLACEHOLDER tokens follow the persisted document language, never the UI locale. */
export function documentTagLanguage(analysis: {
  resolved_document_language?: string | null
  requested_document_language?: string | null
}): UiLanguage {
  const raw =
    analysis.resolved_document_language ||
    analysis.requested_document_language ||
    'tr'
  return raw.toLowerCase().startsWith('en') ? 'en' : 'tr'
}
