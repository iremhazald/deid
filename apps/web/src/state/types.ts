import type { SourceDocumentType, WorkspaceMode } from './workspaceMode'

export type { SourceDocumentType, WorkspaceMode } from './workspaceMode'

export type PrivacyProfile = 'GENERAL' | 'GDPR' | 'KVKK' | 'GDPR_KVKK' | 'CUSTOM'
export type PurposePreset = 'ANONYMIZED' | 'STRICT_PRODUCTION' | 'DETECT_ONLY'
export type DecisionAction = 'REDACT' | 'KEEP'

export type OutputFormat = 'TXT' | 'PDF' | 'DOCX'
export type DetectionMethod = 'DETERMINISTIC' | 'STRUCTURAL' | 'AI' | 'MANUAL'
export type DocumentKind = 'PDF' | 'DOCX' | 'TEXT'
export type ValidationStatus = 'PASS' | 'WARNING' | 'FAILED'
export type WorkflowPhase = 'upload' | 'processing' | 'review' | 'validating' | 'export'
export type DecisionSource = 'default' | 'user_override' | 'occurrence_override'
export type AnalysisStatus = 'COMPLETE' | 'PARTIAL' | 'FAILED'
export type AIRunStatus = 'SUCCESS' | 'SUCCESS_ZERO' | 'FAILED' | 'DISABLED' | 'SKIPPED'

export type TransformationStrategy =
  | 'REDACT'
  | 'PLACEHOLDER'
  | 'INITIALS'
  | 'PARTIAL_MASK'
  | 'KEEP'

export type DecisionScope = 'entity' | 'occurrence'
export type EditorTool = 'select' | 'redact-area' | 'add-text' | 'select-text'
export type DocumentViewMode = 'detections' | 'preview'

/** @deprecated Use TransformationStrategy; kept for temporary API compat. */
export type RedactionMethod = 'MASK' | 'LABEL'

export type ManualRect = {
  x0: number
  y0: number
  x1: number
  y1: number
}

export type Entity = {
  id: string
  text: string
  type: string
  start: number
  end: number
  page: number
  detector: string
  method: DetectionMethod
  validated: boolean
  confidence?: number
  role?: string
  reason?: string
  recommended: boolean
  resolved_entity_id?: string
  occurrence_count?: number
  role_confident?: boolean
  recommended_strategy?: TransformationStrategy
  needs_review?: boolean
  verification_level?: 'validated' | 'review_recommended'
  verification_method?: string
  rectangles?: ManualRect[]
  attributes?: Record<string, unknown>
  relations?: Array<{
    kind: string
    target_start?: number
    target_end?: number
    target_type?: string
    target_text?: string
    label?: string
  }>
  placeholder_token?: string | null
}

export type RoutingMetadata = {
  provider?: string | null
  efficient_model?: string | null
  review_model?: string | null
  review_available?: boolean
  efficient_model_used?: boolean
  review_model_used?: boolean
  candidate_count?: number
  detection_failed?: boolean
  error_code?: string | null
  error_message?: string | null
  schema_success?: boolean
}

export type Analysis = {
  job_id: string
  file_name: string
  document_kind: DocumentKind
  source_document_type?: SourceDocumentType | null
  workspace_mode?: WorkspaceMode | null
  document_hash?: string
  page_count: number
  text: string
  page_texts?: string[]
  page_spans?: Array<{
    page: number
    width: number
    height: number
    line_rects?: Array<{ x0: number; y0: number; x1: number; y1: number }>
    spans: Array<{
      entity_id: string
      text: string
      type: string
      rectangles: Array<{ x0: number; y0: number; x1: number; y1: number }>
      mask_rectangles?: Array<{ x0: number; y0: number; x1: number; y1: number }>
    }>
  }>
  page_previews?: Array<{ page: number; image: string }>
  page_layouts?: Array<{
    page: number
    width: number
    height: number
    runs: Array<{
      start: number
      end: number
      x0: number
      y0: number
      x1: number
      y1: number
      size: number
      bold?: boolean
    }>
  }>
  entities: Entity[]
  detectors_executed?: string[]
  warnings: string[]
  profile: PrivacyProfile
  detection_mode?: 'RULES_ONLY' | 'LOCAL_CONTEXT'
  routing?: RoutingMetadata | null
  analysis_status?: AnalysisStatus
  ai_status?: AIRunStatus
  ai_error_code?: string | null
  ai_error_message?: string | null
  local_ner_status?: 'NOT_REQUESTED' | 'LOADED' | 'COMPLETED' | 'UNAVAILABLE' | 'FAILED'
  local_ner_language?: string | null
  local_ner_provider?: string | null
  local_ner_candidate_count?: number | null
  local_ner_error_code?: string | null
  local_ner_error_message?: string | null
  requested_document_language?: string | null
  resolved_document_language?: string | null
  possible_matches?: PossibleMatch[]
  resolution_state?: ResolutionState | null
}

export type PossibleMatchMember = {
  canonical_id: string
  entity_ids: string[]
  text: string
  pages: number[]
  placeholder_token?: string | null
}

export type PossibleMatch = {
  id: string
  members: PossibleMatchMember[]
  kind?: 'person' | 'address'
}

export type ResolutionState = {
  canonical_by_entity_id: Record<string, string>
  rejected_pairs: string[][]
  family_order: Record<string, string[]>
  append_ids: string[]
}

export type ManualRedaction = {
  id?: string
  text: string
  page: number
  replacement?: string   // Custom replacement text; if absent → REDACT (black box)
  start?: number
  end?: number
  rectangles?: ManualRect[]
  category?: string
  fill?: string
  textColor?: string
  font?: string
  fontSize?: number
  kept?: boolean
}

export type Result = {
  validation: {
    status: ValidationStatus
    messages: string[]
    selected_count?: number
    remaining_selected_values?: number
    operation_messages?: string[]
    residual_messages?: string[]
    verified_count?: number
    warning_count?: number
    failed_count?: number
    strategy_results?: Array<{
      entity_id?: string | null
      strategy?: string
      status?: ValidationStatus
      reasons?: string[]
    }>
  }
  download_url: string | null
  downloads?: Array<{ format: 'DOCX' | 'PDF'; url: string }>
  audit_url: string
  copy_text?: string | null
  saved_path?: string
  saved_audit_path?: string
  export_path?: 'secure_pdf' | 'text_rebuild' | 'text_copy'
  output_mode?: 'original_layout'
  strategy_counts?: Record<string, number>
  analysis_status?: AnalysisStatus
  ai_status?: AIRunStatus
}

export type Decisions = Record<string, DecisionAction>
/** User output / preview methods. Distinct from AI sanitization tokens on the server. */
export type OutputTransformationStrategy = TransformationStrategy
export type CategoryDefaults = Record<string, OutputTransformationStrategy>
export type EntityStrategies = Record<string, OutputTransformationStrategy>

export type CatalogCategory = {
  category: string
  allowed_strategies: TransformationStrategy[]
  recommended_strategy: TransformationStrategy
  generalization_options: Array<{ id: string; label_key: string }>
  supports_role_replacement: boolean
}

export type ScanScopeGroup = {
  id: string
  types: string[]
}

export type TransformCatalog = {
  strategies: TransformationStrategy[]
  categories: CatalogCategory[]
  role_labels: { tr: Record<string, string>; en: Record<string, string> }
  secure_pdf_strategies: TransformationStrategy[]
  scan_scope_groups?: ScanScopeGroup[]
  purpose_presets?: PurposePreset[]
  placeholder_taxonomy?: Array<{
    entity_type: string
    ui_group: string
    family: string
    numbered: boolean
    reuse: boolean
    labels: { tr: string; en: string }
    example: { tr: string; en: string }
  }>
}

export type UserDefinedTerm = {
  value: string
  category: string
  strategy?: TransformationStrategy
  stable_key?: string
  starts?: number[]
}

export const PURPOSE_PRESETS: PurposePreset[] = [
  'ANONYMIZED',
  'STRICT_PRODUCTION',
  'DETECT_ONLY',
]

export type PreviewResponse = {
  text: string
  operations: Array<{
    entity_id?: string | null
    category?: string | null
    strategy: TransformationStrategy
    start: number
    end: number
    replacement: string
    export_path: 'secure_pdf' | 'text_rebuild'
    ai_assisted: boolean
  }>
  requires_text_rebuild: boolean
  warnings: string[]
  placeholder_tokens?: Record<string, string>
}

export const PROFILES: PrivacyProfile[] = ['GENERAL', 'GDPR', 'KVKK', 'GDPR_KVKK', 'CUSTOM']


export const ACCEPTED_FILES =
  'application/pdf,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.udf'

export function isPdfFileName(name: string): boolean {
  return name.toLowerCase().endsWith('.pdf')
}

export function isDocxFileName(name: string): boolean {
  return name.toLowerCase().endsWith('.docx')
}

export function isUdfFileName(name: string): boolean {
  return name.toLowerCase().endsWith('.udf')
}

export function isAcceptedUpload(file: File): boolean {
  const name = file.name.toLowerCase()
  if (name.endsWith('.doc') || name.endsWith('.docm')) return false
  if (isDocxFileName(name) || isUdfFileName(name)) return true
  return isPdfFileName(name) || file.type === 'application/pdf'
}

export const MAX_FILE_MB = 25

export const STRATEGY_ORDER: TransformationStrategy[] = [
  'REDACT',
  'PLACEHOLDER',
  'INITIALS',
  'PARTIAL_MASK',
  'KEEP',
]

export const PRIMARY_FILTER_FAMILIES = [
  'person',
  'identity',
  'address',
  'contact',
  'file',
] as const

export { CATEGORY_FAMILIES } from './presentationTaxonomy'

/** Categories treated as primary redaction suggestions in the review panel. */
export const RECOMMENDED_CATEGORY_TYPES = new Set([
  'PERSON_NAME',
  'FIRST_NAME',
  'LAST_NAME',
  'ALIAS',
  'NATIONAL_ID',
  'PASSPORT_NUMBER',
  'TAX_IDENTIFIER',
  'ADDRESS',
  'EMAIL',
  'PHONE_NUMBER',
  'IP_ADDRESS',
  'IBAN',
  'BANK_ACCOUNT',
  'CREDIT_CARD',
  'FINANCIAL_IDENTIFIER',
  'CLAIMANT_NAME',
  'DEFENDANT_NAME',
  'WITNESS_NAME',
  'EXPERT_NAME',
  'LAWYER_NAME',
  'CASE_NUMBER',
  'FILE_NUMBER',
  'DECISION_NUMBER',
  'QR_CODE',
  'UYAP_ACCESS',
  'DATE_OF_BIRTH',
  'BIRTH_PLACE',
  'PROFESSIONAL_ID',
])
