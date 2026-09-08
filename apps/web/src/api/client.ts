import type {
  Analysis,
  DecisionAction,
  ManualRedaction,
  OutputFormat,
  PreviewResponse,
  PrivacyProfile,
  Result,
  TransformationStrategy,
  TransformCatalog,
  UserDefinedTerm,
} from '../state/types'

const API = import.meta.env.VITE_API_URL ?? ''

export function apiBase() {
  return API
}

export class ApiError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail ?? response.statusText
  } catch {
    return response.statusText
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch {
    throw new ApiError('API_UNREACHABLE')
  }
  if (!response.ok) throw new ApiError(await parseError(response))
  return await response.json() as T
}

export function fetchTransformCatalog() {
  return requestJson<TransformCatalog>(`${API}/api/transforms/catalog`)
}

export type DetectionMode = 'RULES_ONLY' | 'LOCAL_CONTEXT'

/** Normal product analyze. Always sent as the form field `mode`. */
export const PRODUCT_ANALYZE_MODE: DetectionMode = 'LOCAL_CONTEXT'

export function analyzeDocument(
  file: File,
  profile: PrivacyProfile = 'GENERAL',
  mode: DetectionMode = PRODUCT_ANALYZE_MODE,
  options?: { customTerms?: UserDefinedTerm[]; scanTypes?: string[]; documentLanguage?: 'auto' | 'tr' | 'en' },
) {
  const form = new FormData()
  form.append('file', file)
  form.append('profile', profile)
  form.append('mode', mode)
  if (options?.customTerms?.length) {
    form.append('custom_terms', JSON.stringify(options.customTerms))
  }
  if (options?.scanTypes?.length) {
    form.append('scan_types', JSON.stringify(options.scanTypes))
  }
  if (options?.documentLanguage) {
    form.append('document_language', options.documentLanguage)
  }
  return requestJson<Analysis>(`${API}/api/documents/analyze`, {
    method: 'POST',
    body: form,
  })
}

export function addCustomTerms(jobId: string, terms: UserDefinedTerm[]) {
  return requestJson<Analysis>(`${API}/api/jobs/${jobId}/custom-terms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ terms }),
  })
}

export function mergeEntityMatch(jobId: string, entityIds: string[]) {
  return requestJson<Analysis>(`${API}/api/jobs/${jobId}/entity-matches/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_ids: entityIds }),
  })
}

export function rejectEntityMatch(jobId: string, entityIds: string[]) {
  return requestJson<Analysis>(`${API}/api/jobs/${jobId}/entity-matches/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_ids: entityIds }),
  })
}

export function reclassifyEntities(
  jobId: string,
  entityIds: string[],
  entityType: string,
) {
  return requestJson<Analysis>(`${API}/api/jobs/${jobId}/entities/reclassify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_ids: entityIds, entity_type: entityType }),
  })
}

export function reanalyzeJob(jobId: string) {
  return requestJson<Analysis>(`${API}/api/jobs/${jobId}/reanalyze`, {
    method: 'POST',
  })
}

export function updateJobProfile(jobId: string, profile: PrivacyProfile) {
  return requestJson<Analysis>(`${API}/api/jobs/${jobId}/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile }),
  })
}

export type RedactPayload = {
  decisions: Array<{
    entity_id: string
    action: DecisionAction
    strategy?: TransformationStrategy
    source?: 'default' | 'user_override' | 'occurrence_override'
    parameters?: {
      rectangles?: Array<{ x0: number; y0: number; x1: number; y1: number }>
      fill?: string
    }
  }>
  categoryDefaults?: Array<{
    category: string
    strategy: TransformationStrategy
  }>
  manual: ManualRedaction[]
  outputFormat?: OutputFormat
  locale?: 'tr' | 'en'
  initialsFontSize?: number
}

export function previewJob(jobId: string, payload: RedactPayload) {
  return requestJson<PreviewResponse>(`${API}/api/jobs/${jobId}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      decisions: payload.decisions,
      category_defaults: payload.categoryDefaults ?? [],
      manual_redactions: payload.manual.map((item) => ({
        text: item.text,
        page: item.page - 1,
        ...(item.replacement != null ? { replacement: item.replacement } : {}),
        ...(item.start != null ? { start: item.start } : {}),
        ...(item.end != null ? { end: item.end } : {}),
        ...(item.rectangles?.length ? { rectangles: item.rectangles } : {}),
        ...(item.fill ? { fill: item.fill } : {}),
        ...(item.textColor ? { text_color: item.textColor } : {}),
        ...(item.font ? { font: item.font } : {}),
        ...(item.fontSize ? { font_size: item.fontSize } : {}),
      })),
      locale: payload.locale ?? 'tr',
      ...(payload.initialsFontSize != null
        ? { initials_font_size: payload.initialsFontSize }
        : {}),
    }),
  })
}

export function redactJob(jobId: string, payload: RedactPayload) {
  return requestJson<Result>(`${API}/api/jobs/${jobId}/redact`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      decisions: payload.decisions,
      category_defaults: payload.categoryDefaults ?? [],
      manual_redactions: payload.manual.map((item) => ({
        text: item.text,
        page: item.page - 1,
        ...(item.replacement != null ? { replacement: item.replacement } : {}),
        ...(item.start != null ? { start: item.start } : {}),
        ...(item.end != null ? { end: item.end } : {}),
        ...(item.rectangles?.length ? { rectangles: item.rectangles } : {}),
        ...(item.fill ? { fill: item.fill } : {}),
        ...(item.textColor ? { text_color: item.textColor } : {}),
        ...(item.font ? { font: item.font } : {}),
        ...(item.fontSize ? { font_size: item.fontSize } : {}),
      })),
      output_format: payload.outputFormat,
      locale: payload.locale ?? 'tr',
      ...(payload.initialsFontSize != null
        ? { initials_font_size: payload.initialsFontSize }
        : {}),
    }),
  })
}

export function getPageImageUrl(jobId: string, pageNum: number, scale = 1.5) {
  return `${API}/api/jobs/${jobId}/pages/${pageNum}?scale=${scale}`
}

export type PdfSpanRect = { x0: number; y0: number; x1: number; y1: number }

export type PdfEntitySpan = {
  entity_id: string
  text: string
  type: string
  rectangles: PdfSpanRect[]
  mask_rectangles?: PdfSpanRect[]
}

export type PdfPageSpans = {
  page: number
  width: number
  height: number
  spans: PdfEntitySpan[]
  line_rects?: PdfSpanRect[]
}

export function fetchJobSpans(jobId: string) {
  return requestJson<{ pages: PdfPageSpans[] }>(`${API}/api/jobs/${jobId}/spans`)
}

export function deleteJob(jobId: string) {
  return fetch(`${API}/api/jobs/${jobId}`, { method: 'DELETE' })
}

export function assetUrl(path: string) {
  return `${API}${path}`
}
