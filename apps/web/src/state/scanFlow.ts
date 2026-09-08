import { PRODUCT_ANALYZE_MODE, type DetectionMode } from '../api/client'
import type { DocumentLanguage, UiLanguage } from './documentLanguage'

/** Internal backend mode used by the normal user-facing scan. */
export const NORMAL_SCAN_MODE: DetectionMode = PRODUCT_ANALYZE_MODE

export function analyzeModeForNormalScan(): DetectionMode {
  return NORMAL_SCAN_MODE
}

/** Reanalyze sends no mode. The job's stored LOCAL_CONTEXT must be preserved. */
export function reanalyzeSendsMode(): boolean {
  return false
}

/** Local NER gaps stay on the local path. */
export function fallbackModeWhenLocalNerUnavailable(): DetectionMode {
  return NORMAL_SCAN_MODE
}

/** RULES_ONLY is never a normal user-facing scan choice. */
export function normalUserFacingScanCanSelectRulesOnly(): boolean {
  return false
}

/** Legal-regime choice must not rewrite the document-language control. */
export function nextDocumentLanguageAfterRegime(
  current: DocumentLanguage,
  _regime: string,
): DocumentLanguage {
  return current
}

/** Legal-regime choice must not rewrite the interface language. */
export function nextUiLanguageAfterRegime(
  current: UiLanguage,
  _regime: string,
): UiLanguage {
  return current
}
