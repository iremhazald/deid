import { describe, expect, it } from 'vitest'
import {
  NORMAL_SCAN_MODE,
  analyzeModeForNormalScan,
  fallbackModeWhenLocalNerUnavailable,
  nextDocumentLanguageAfterRegime,
  nextUiLanguageAfterRegime,
  normalUserFacingScanCanSelectRulesOnly,
  reanalyzeSendsMode,
} from './scanFlow'

describe('normal scan mode', () => {
  it('always requests LOCAL_CONTEXT', () => {
    expect(analyzeModeForNormalScan()).toBe('LOCAL_CONTEXT')
    expect(NORMAL_SCAN_MODE).toBe('LOCAL_CONTEXT')
  })

  it('does not request HYBRID or RULES_ONLY for the normal scan', () => {
    expect(analyzeModeForNormalScan()).not.toBe('HYBRID')
    expect(analyzeModeForNormalScan()).not.toBe('RULES_ONLY')
    expect(normalUserFacingScanCanSelectRulesOnly()).toBe(false)
  })

  it('retries without sending a mode override', () => {
    expect(reanalyzeSendsMode()).toBe(false)
  })

  it('does not fall back to HYBRID when local NER is unavailable', () => {
    expect(fallbackModeWhenLocalNerUnavailable()).toBe('LOCAL_CONTEXT')
    expect(fallbackModeWhenLocalNerUnavailable()).not.toBe('HYBRID')
  })

  it('does not change document or UI language when a legal regime is mentioned', () => {
    expect(nextDocumentLanguageAfterRegime('auto', 'kvkk')).toBe('auto')
    expect(nextDocumentLanguageAfterRegime('en', 'kvkk')).toBe('en')
    expect(nextUiLanguageAfterRegime('en', 'kvkk')).toBe('en')
    expect(nextUiLanguageAfterRegime('tr', 'gdpr')).toBe('tr')
  })
})
