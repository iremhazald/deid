import { afterEach, describe, expect, it, vi } from 'vitest'
import { analyzeDocument, PRODUCT_ANALYZE_MODE, reanalyzeJob } from './client'
import { analyzeModeForNormalScan } from '../state/scanFlow'
import app from '../App.tsx?raw'
import hero from '../components/upload/UploadHero.tsx?raw'
import picker from '../components/upload/DocumentLanguagePicker.tsx?raw'
import client from './client.ts?raw'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function jsonResponse(body: unknown = { job_id: 'job' }) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('normal analyze request', () => {
  it('sends LOCAL_CONTEXT and never HYBRID', async () => {
    const captured: { url?: string; body?: FormData } = {}
    vi.stubGlobal(
      'fetch',
      async (url: string | URL, init?: RequestInit) => {
        captured.url = String(url)
        captured.body = init?.body as FormData
        return jsonResponse()
      },
    )
    const file = new File(['text'], 'dilekce.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    await analyzeDocument(file, 'GENERAL', analyzeModeForNormalScan(), {
      documentLanguage: 'auto',
    })
    expect(captured.body?.get('mode')).toBe('LOCAL_CONTEXT')
    expect(captured.body?.get('mode')).toBe(PRODUCT_ANALYZE_MODE)
    expect(captured.body?.get('mode')).not.toBe('HYBRID')
    expect(captured.body?.get('mode')).not.toBe('RULES_ONLY')
    expect(captured.body?.get('document_language')).toBe('auto')
    expect(String(captured.url)).toContain('/api/documents/analyze')
  })

  it('sends LOCAL_CONTEXT even when the caller omits mode', async () => {
    const captured: { body?: FormData } = {}
    vi.stubGlobal(
      'fetch',
      async (_url: string | URL, init?: RequestInit) => {
        captured.body = init?.body as FormData
        return jsonResponse()
      },
    )
    const file = new File(['text'], 'claim.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    await analyzeDocument(file)
    expect(captured.body?.get('mode')).toBe('LOCAL_CONTEXT')
    expect(captured.body?.has('mode')).toBe(true)
  })

  it('retries through reanalyze without a mode body', async () => {
    const captured: { url?: string; body?: string | null } = {}
    vi.stubGlobal(
      'fetch',
      async (url: string | URL, init?: RequestInit) => {
        captured.url = String(url)
        captured.body = typeof init?.body === 'string' ? init.body : null
        return jsonResponse()
      },
    )
    await reanalyzeJob('job-1')
    expect(String(captured.url)).toContain('/api/jobs/job-1/reanalyze')
    expect(captured.body).toBeNull()
  })
})

describe('normal UI source contract', () => {
  it('Start Scan always uses analyzeModeForNormalScan and never RULES_ONLY', () => {
    expect(app).toContain('analyzeModeForNormalScan()')
    expect(app).not.toContain('RULES_ONLY')
    expect(app).not.toContain('DetectionModePicker')
    expect(hero).not.toContain('DetectionModePicker')
    expect(hero).not.toContain('RULES_ONLY')
    expect(picker).toContain('DOCUMENT_LANGUAGE_UI_OPTIONS')
    expect(picker).not.toContain('DOCUMENT_LANGUAGE_OPTIONS')
    expect(client).not.toContain('enrich-ai')
    expect(client).not.toContain('HYBRID')
    expect(client).not.toContain('/api/ai/')
  })
})
