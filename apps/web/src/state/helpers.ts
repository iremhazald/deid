import {
  type Analysis,
  type AnalysisStatus,
  type CategoryDefaults,
  type Decisions,
  type DocumentViewMode,
  type Entity,
  type EntityStrategies,
  type ManualRect,
  type ManualRedaction,
  type PurposePreset,
  type Result,
  type TransformationStrategy,
  type TransformCatalog,
  type UserDefinedTerm,
  CATEGORY_FAMILIES,
  PRIMARY_FILTER_FAMILIES,
  RECOMMENDED_CATEGORY_TYPES,
  STRATEGY_ORDER,
} from './types'
import {
  PRESENTATION_GROUP_ORDER,
  presentationGroupForEntityType,
  presentationGroupOrder,
  shouldFlattenPresentationGroup,
  subcategoryForEntityType,
  subcategoryOrder,
} from './presentationTaxonomy'

export { locateCorrectedSpan } from './findingSpan'

export function isReviewRecommended(entity: Entity): boolean {
  if (entity.needs_review) return true
  return false
}

const LEGAL_GLUE = /^(nezdinde|ibana|anlaştıkları|anlastiklari|adına kayıtlı|adina kayitli)$/i

function isLegalGlueOverlay(text: string): boolean {
  const folded = text.trim().toLocaleLowerCase('tr-TR')
  if (!folded) return true
  if (LEGAL_GLUE.test(folded)) return true
  if (/ibana/.test(folded) && /anlaşt|anlast/.test(folded)) return true
  const words = folded.split(/\s+/).length
  if (words < 8) return false
  return /bilindiği üzere|bilindigi uzere|kendi adına tahsisli|gsm hatlarının|kimlik bilgilerini|ıp numaraları|ip numaralari/.test(
    folded,
  )
}

/** Overlay visibility follows the effective strategy, not the raw category. */
export function showDetectionOverlay(
  entity: Entity,
  strategy: TransformationStrategy,
  viewMode: DocumentViewMode,
  showPreserved = false,
): boolean {
  if (isLegalGlueOverlay(entity.text)) return false
  if (strategy !== 'KEEP') return true
  if (viewMode !== 'detections') return false
  return showPreserved
}

export function isActionableFinding(
  entity: Entity,
  decisions: Decisions,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
): boolean {
  return effectiveStrategy(entity, decisions, categoryDefaults, entityStrategies) !== 'KEEP'
}

export function partitionFindingsByAction(
  entities: Entity[],
  decisions: Decisions,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
): { actionable: Entity[]; preserved: Entity[] } {
  const actionable: Entity[] = []
  const preserved: Entity[] = []
  for (const entity of entities) {
    if (isActionableFinding(entity, decisions, categoryDefaults, entityStrategies)) {
      actionable.push(entity)
    } else {
      preserved.push(entity)
    }
  }
  return { actionable, preserved }
}

export function tallyActionableFindings(
  entities: Entity[],
  decisions: Decisions,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
  manual: ManualRedaction[] = [],
): { actionable: number; preserved: number } {
  const { actionable, preserved } = partitionFindingsByAction(
    entities,
    decisions,
    categoryDefaults,
    entityStrategies,
  )
  return {
    actionable: actionable.length + manual.filter((item) => !item.kept).length,
    preserved: preserved.length,
  }
}

export function catalogStrategyFor(
  type: string,
  catalog: TransformCatalog | null,
  entity?: Entity,
): TransformationStrategy {
  if (entity?.recommended_strategy) return entity.recommended_strategy
  const entry = catalog?.categories.find((item) => item.category === type)
  if (entry?.recommended_strategy) return entry.recommended_strategy
  return 'REDACT'
}

function categoryStrategyForPreset(
  type: string,
  entities: Entity[],
  catalog: TransformCatalog | null,
  preset: PurposePreset,
): TransformationStrategy {
  if (preset === 'DETECT_ONLY') return 'KEEP'
  const sample = entities.find((entity) => entity.type === type)
  if (preset === 'STRICT_PRODUCTION') {
    return sample?.recommended ? 'REDACT' : 'KEEP'
  }
  return catalogStrategyFor(type, catalog, catalog ? undefined : sample)
}

export function seedDecisions(
  entities: Entity[],
  preset: PurposePreset = 'ANONYMIZED',
): Decisions {
  return Object.fromEntries(
    entities.map((entity) => {
      if (preset === 'DETECT_ONLY') return [entity.id, 'KEEP']
      if (isReviewRecommended(entity)) return [entity.id, 'KEEP']
      return [entity.id, entity.recommended ? 'REDACT' : 'KEEP']
    }),
  )
}

export type StrategySeedOptions = {
  workspaceMode?: string | null
}

/** Text workspace reads as running prose, so the default method is a label. */
function textWorkspaceLabels(options?: StrategySeedOptions): boolean {
  return options?.workspaceMode === 'TEXT'
}

function textWorkspaceCategoryStrategy(
  type: string,
  entities: Entity[],
  catalog: TransformCatalog | null,
  preset: PurposePreset,
): TransformationStrategy {
  const fallback = categoryStrategyForPreset(type, entities, catalog, preset)
  if (preset !== 'ANONYMIZED') return fallback
  if (!allowedStrategiesFor(type, catalog).includes('PLACEHOLDER')) return fallback
  return 'PLACEHOLDER'
}

export function seedCategoryDefaults(
  entities: Entity[],
  catalog: TransformCatalog | null,
  preset: PurposePreset = 'ANONYMIZED',
  options?: StrategySeedOptions,
): CategoryDefaults {
  const defaults: CategoryDefaults = {}
  for (const entity of entities) {
    if (defaults[entity.type]) continue
    defaults[entity.type] = textWorkspaceLabels(options)
      ? textWorkspaceCategoryStrategy(entity.type, entities, catalog, preset)
      : categoryStrategyForPreset(entity.type, entities, catalog, preset)
  }
  return defaults
}

export function seedEntityStrategies(
  entities: Entity[],
  catalog: TransformCatalog | null,
  preset: PurposePreset = 'ANONYMIZED',
  options?: StrategySeedOptions,
): EntityStrategies {
  const next: EntityStrategies = {}
  if (preset === 'DETECT_ONLY') return next
  if (textWorkspaceLabels(options) && preset === 'ANONYMIZED') return next
  for (const entity of entities) {
    if (isReviewRecommended(entity)) {
      const recommended = catalogStrategyFor(entity.type, catalog, entity)
      next[entity.id] = recommended === 'REDACT' ? 'KEEP' : recommended
      continue
    }
    if (preset === 'ANONYMIZED' && entity.recommended_strategy) {
      const category = catalogStrategyFor(entity.type, catalog)
      if (entity.recommended_strategy !== category) {
        next[entity.id] = entity.recommended_strategy
      }
    }
  }
  return next
}

/**
 * When profile recommendations change, reseed only entities the user has not
 * manually overridden relative to the previous recommendation baseline.
 */
function decisionBaseline(entity: Entity, preset: PurposePreset = 'ANONYMIZED'): 'REDACT' | 'KEEP' {
  if (preset === 'DETECT_ONLY' || isReviewRecommended(entity)) return 'KEEP'
  return entity.recommended ? 'REDACT' : 'KEEP'
}

export function mergeProfileDecisions(
  entities: Entity[],
  previous: Decisions,
  previousEntities: Entity[],
  preset: PurposePreset = 'ANONYMIZED',
): Decisions {
  const previousById = new Map(previousEntities.map((entity) => [entity.id, entity]))
  const next: Decisions = { ...previous }

  for (const entity of entities) {
    const prior = previousById.get(entity.id)
    const priorDecision = previous[entity.id]
    const priorDefault = prior ? decisionBaseline(prior, preset) : decisionBaseline(entity, preset)
    const untouched = !priorDecision || priorDecision === priorDefault
    if (untouched || !priorDecision) {
      next[entity.id] = decisionBaseline(entity, preset)
    }
  }

  return next
}

export function mergeCategoryDefaults(
  entities: Entity[],
  previous: CategoryDefaults,
  catalog: TransformCatalog | null,
  preset: PurposePreset = 'ANONYMIZED',
  options?: StrategySeedOptions,
): CategoryDefaults {
  const seeded = seedCategoryDefaults(entities, catalog, preset, options)
  return { ...seeded, ...previous }
}

export function mergePresetCategoryDefaults(
  entities: Entity[],
  previous: CategoryDefaults,
  previousPreset: PurposePreset,
  nextPreset: PurposePreset,
  catalog: TransformCatalog | null,
): CategoryDefaults {
  const oldSeed = seedCategoryDefaults(entities, catalog, previousPreset)
  const newSeed = seedCategoryDefaults(entities, catalog, nextPreset)
  const next: CategoryDefaults = { ...newSeed }
  for (const type of new Set([...Object.keys(previous), ...Object.keys(newSeed)])) {
    const wasUntouched = !previous[type] || previous[type] === oldSeed[type]
    if (!wasUntouched) next[type] = previous[type]
  }
  return next
}

export function mergePresetDecisions(
  entities: Entity[],
  previous: Decisions,
  previousPreset: PurposePreset,
  nextPreset: PurposePreset,
): Decisions {
  const next: Decisions = { ...previous }
  for (const entity of entities) {
    const prior = previous[entity.id]
    const oldDefault = decisionBaseline(entity, previousPreset)
    const untouched = !prior || prior === oldDefault
    if (untouched) next[entity.id] = decisionBaseline(entity, nextPreset)
  }
  return next
}

/**
 * Collapse rows that share a normalized text group so "Mehmet Yılmaz"
 * appearing 12 times is one list line.
 *
 * This is exact/normalized-string grouping for the UI. It is not identity
 * resolution, coreference, or a claim that the mentions are the same person.
 */
export function collapseForList(entities: Entity[]): Entity[] {
  return collapseResolvedEntities(entities)
}

function collapseGroup(group: Entity[]): Entity {
  const first = group[0]
  return group.length > 1 ? { ...first, occurrence_count: group.length } : first
}

function collapseResolvedEntities(entities: Entity[]): Entity[] {
  const byResolved = new Map<string, Entity[]>()
  const byText = new Map<string, Entity[]>()

  for (const entity of entities) {
    const resolved = entity.resolved_entity_id
    if (resolved) {
      byResolved.set(resolved, [...(byResolved.get(resolved) ?? []), entity])
      continue
    }
    const key = `${entity.type}::${entity.text.trim().toLowerCase()}`
    byText.set(key, [...(byText.get(key) ?? []), entity])
  }

  return [
    ...[...byResolved.values()].map(collapseGroup),
    ...[...byText.values()].map(collapseGroup),
  ]
}

function sameSurfaceValue(left: Entity, right: Entity): boolean {
  return (
    left.type === right.type &&
    left.text.trim().toLowerCase() === right.text.trim().toLowerCase()
  )
}

/** IDs that share a normalized text group, or the same type+spelling.

 * `resolved_entity_id` is a text-group key from the backend, not a resolved
 * person identity.
 */
export function relatedEntityIds(entityId: string, entities: Entity[]): string[] {
  const target = entities.find((entity) => entity.id === entityId)
  if (!target) return [entityId]
  if (target.resolved_entity_id) {
    return entities
      .filter((entity) => entity.resolved_entity_id === target.resolved_entity_id)
      .map((entity) => entity.id)
  }
  return entities
    .filter((entity) => !entity.resolved_entity_id && sameSurfaceValue(entity, target))
    .map((entity) => entity.id)
}

/** Expand a list of (possibly collapsed) IDs to every related occurrence. */
export function expandRelatedIds(ids: string[], entities: Entity[]): string[] {
  const expanded = new Set<string>()
  for (const id of ids) {
    for (const related of relatedEntityIds(id, entities)) {
      expanded.add(related)
    }
  }
  return [...expanded]
}

export function groupEntities(entities: Entity[]): Array<[string, Entity[]]> {
  const collapsed = collapseResolvedEntities(entities)
  const grouped = new Map<string, Entity[]>()
  for (const entity of collapsed) {
    grouped.set(entity.type, [...(grouped.get(entity.type) ?? []), entity])
  }
  return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b))
}

export function splitRecommendedGroups(groups: Array<[string, Entity[]]>) {
  const recommended: Array<[string, Entity[]]> = []
  const other: Array<[string, Entity[]]> = []
  for (const group of groups) {
    const [type, entities] = group
    const bucket = entities.some((entity) => entity.recommended)
      || RECOMMENDED_CATEGORY_TYPES.has(type)
      ? recommended
      : other
    bucket.push(group)
  }
  return { recommended, other }
}

export function effectiveStrategy(
  entity: Entity,
  decisions: Decisions,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
): TransformationStrategy {
  if (decisions[entity.id] === 'KEEP') return 'KEEP'
  const stored = entityStrategies[entity.id]
  if (stored && stored !== 'KEEP') return stored
  if (categoryDefaults[entity.type]) return categoryDefaults[entity.type]
  return entity.recommended_strategy ?? 'REDACT'
}

/** Masking method to re-apply when a kept detection is restored. */
export function restoreStrategyFor(
  entity: Entity,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
): TransformationStrategy {
  const stored = entityStrategies[entity.id]
  if (stored && stored !== 'KEEP') return stored
  const category = categoryDefaults[entity.type]
  if (category && category !== 'KEEP') return category
  if (entity.recommended_strategy && entity.recommended_strategy !== 'KEEP') {
    return entity.recommended_strategy
  }
  return 'REDACT'
}

export function allowedStrategiesFor(
  type: string,
  catalog: TransformCatalog | null,
): TransformationStrategy[] {
  const lookup = CATALOG_TYPE_FOR_DISPLAY[type] ?? type
  const entry = catalog?.categories.find((item) => item.category === lookup)
  if (entry) return entry.allowed_strategies
  return STRATEGY_ORDER
}

/**
 * User-output methods for preview/export.
 */
export function userOutputStrategiesFor(
  type: string,
  catalog: TransformCatalog | null,
): TransformationStrategy[] {
  return allowedStrategiesFor(type, catalog)
}

export function outputStrategyLabelKey(strategy: TransformationStrategy): string {
  switch (strategy) {
    case 'KEEP':
      return 'workspace.strategyKeep'
    case 'REDACT':
      return 'workspace.strategyRedact'
    case 'PLACEHOLDER':
      return 'workspace.strategyPlaceholder'
    case 'INITIALS':
      return 'workspace.strategyInitials'
    case 'PARTIAL_MASK':
      return 'workspace.strategyPartial'
    default:
      return `strategies.${strategy}`
  }
}

export function requiresTextRebuild(
  entities: Entity[],
  decisions: Decisions,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
  documentKind: string,
  secureStrategies: TransformationStrategy[] = ['REDACT', 'INITIALS', 'PLACEHOLDER', 'PARTIAL_MASK'],
): boolean {
  if (documentKind !== 'PDF') return documentKind !== 'PDF'
  const secure = new Set(secureStrategies)
  for (const entity of entities) {
    const strategy = effectiveStrategy(entity, decisions, categoryDefaults, entityStrategies)
    if (strategy === 'KEEP') continue
    if (entity.type === 'QR_CODE' && strategy === 'REDACT') continue
    if (entity.type === 'COURT_NAME' && (strategy === 'PARTIAL_MASK' || strategy === 'PLACEHOLDER')) continue
    if (!secure.has(strategy)) return true
  }
  return false
}

export function tallyDecisions(decisions: Decisions, manual: ManualRedaction[]) {
  const values = Object.values(decisions)
  return {
    redact: values.filter((value) => value === 'REDACT').length + manual.filter((item) => !item.kept).length,
    keep: values.filter((value) => value === 'KEEP').length,
  }
}

export function manualItemId(item: ManualRedaction, index: number) {
  return item.id ?? `manual:${index}`
}

export function findManualById(items: ManualRedaction[], id: string) {
  return items.find((item, index) => manualItemId(item, index) === id)
}

/** Overlay boxes already shown in review — send them on export so PDF mapping cannot miss them. */
export function exportRectanglesForEntity(
  entity: Entity,
  analysis: Analysis,
  boxOverrides: Record<string, ManualRect[]>,
): ManualRect[] | undefined {
  const overridden = boxOverrides[entity.id]
  if (overridden?.length) return overridden
  if (entity.rectangles?.length) return entity.rectangles
  const collected: ManualRect[] = []
  for (const page of analysis.page_spans ?? []) {
    if (page.page !== entity.page) continue
    for (const span of page.spans) {
      if (span.entity_id !== entity.id) continue
      collected.push(...span.rectangles)
    }
  }
  return collected.length ? collected : undefined
}

export function manualKindKey(item: ManualRedaction): 'text' | 'mask' | 'phrase' {
  if (item.replacement?.trim()) return 'text'
  if (item.rectangles?.length) return 'mask'
  return 'phrase'
}

export function summarizeByCategory(
  analysis: Analysis | null,
  decisions: Decisions,
  manualCount: number,
): Array<{ type: string; count: number }> {
  if (!analysis) return []
  const counts = new Map<string, number>()
  for (const entity of analysis.entities) {
    if (decisions[entity.id] !== 'REDACT') continue
    counts.set(entity.type, (counts.get(entity.type) ?? 0) + 1)
  }
  const rows = [...counts.entries()]
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type))
  if (manualCount > 0) rows.push({ type: 'MANUAL', count: manualCount })
  return rows
}

export function categoryAccent(type: string): string {
  if (/INSTITUTION|ORGANISATION|COMPANY/.test(type)) return 'accent-other'
  if (type === 'COURT_NAME' || type === 'PROFESSIONAL_ID') return 'accent-legal'
  if (/NAME|PERSON|CLAIMANT|DEFENDANT|LAWYER|JUDGE|WITNESS|EXPERT|ALIAS/.test(type)) {
    return 'accent-person'
  }
  if (/ID|PASSPORT|TAX|CUSTOMER|EMPLOYEE|IDENTIFIER|PLATE/.test(type)) {
    return 'accent-id'
  }
  if (/ADDRESS|POSTAL|LOCATION/.test(type)) return 'accent-address'
  if (/EMAIL|PHONE|IP|URL|CYBER|PORT/.test(type)) return 'accent-contact'
  if (/IBAN|BANK|CREDIT|FINANCIAL|SALARY/.test(type)) return 'accent-finance'
  if (/HEALTH|CRIMINAL/.test(type)) {
    return 'accent-sensitive'
  }
  if (/COURT|CASE|FILE|DECISION|UYAP/.test(type)) return 'accent-legal'
  if (/QR_CODE|SIGNATURE/.test(type)) return 'accent-id'
  return 'accent-other'
}

export function usesPaperRedaction(
  type: string,
  attributes?: Record<string, unknown> | null,
): boolean {
  if (type === 'QR_CODE' || type === 'UYAP_ACCESS' || type === 'PROFESSIONAL_ID') return true
  return attributes?.mask_scope === 'header_line'
}

const PERSON_TYPES = new Set(CATEGORY_FAMILIES.find((family) => family.id === 'person')?.types ?? [])

/** Catalog lookup for leftover synthetic panel keys. */
const CATALOG_TYPE_FOR_DISPLAY: Record<string, string> = {
  INSTITUTION: 'COMPANY_NAME',
  CYBER: 'IP_ADDRESS',
  BANKING: 'IBAN',
}

export function detectedFontSize(entity: Entity): number | undefined {
  const raw = entity.attributes?.font_size
  const value = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(value) || value < 4 || value > 72) return undefined
  return value
}

export function initialsPointSize(entity: Entity, fallback: number): number {
  return detectedFontSize(entity) ?? fallback
}

export function needsInitialsSizeControl(
  entities: Entity[],
  decisions: Decisions,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
): boolean {
  return entities.some((entity) => {
    if (!PERSON_TYPES.has(entity.type)) return false
    if (effectiveStrategy(entity, decisions, categoryDefaults, entityStrategies) !== 'INITIALS') {
      return false
    }
    return detectedFontSize(entity) == null
  })
}

export function familyOf(type: string): string {
  return CATEGORY_FAMILIES.find((family) => family.types.includes(type))?.id ?? 'other'
}

export function summarizeFamilies(entities: Entity[]): Array<{ id: string; count: number }> {
  const counts = new Map<string, number>()
  for (const entity of entities) {
    const id = familyOf(entity.type)
    counts.set(id, (counts.get(id) ?? 0) + 1)
  }
  const known = CATEGORY_FAMILIES
    .map((family) => ({ id: family.id, count: counts.get(family.id) ?? 0 }))
    .filter((row) => row.count > 0)
  const other = counts.get('other') ?? 0
  return other > 0 ? [...known, { id: 'other', count: other }] : known
}

export type TypeGroup = {
  type: string
  rows: Entity[]
  mentionCount: number
  backendTypes: string[]
}

export type FamilyGroup = {
  id: string
  rows: Entity[]
  mentionCount: number
  types: TypeGroup[]
  flattened: boolean
}

function mentionCountOf(rows: Entity[]): number {
  return rows.reduce((sum, entity) => sum + (entity.occurrence_count ?? 1), 0)
}

/** Subcategory key used for panel headings. Detection types stay unchanged. */
export function listDisplayType(type: string): string {
  return subcategoryForEntityType(type)
}

function typesWithin(rows: Entity[]): TypeGroup[] {
  const buckets = new Map<string, Entity[]>()
  for (const entity of rows) {
    const key = subcategoryForEntityType(entity.type)
    buckets.set(key, [...(buckets.get(key) ?? []), entity])
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => subcategoryOrder(a) - subcategoryOrder(b) || a.localeCompare(b))
    .map(([type, group]) => {
      const collapsed = collapseForList(group)
      return {
        type,
        rows: collapsed,
        mentionCount: mentionCountOf(collapsed),
        backendTypes: [...new Set(group.map((entity) => entity.type))],
      }
    })
}

export function filterFamilyId(familyId: string): string {
  return (PRIMARY_FILTER_FAMILIES as readonly string[]).includes(familyId) ? familyId : 'other'
}

/**
 * Collapsed findings grouped for the review panel.
 *
 * Count semantics match the existing panel: mentionCount is the sum of
 * collapsed-row occurrence_count (or 1). Subcategory counts use the same
 * rule scoped to that subtype. Parent count is the sum of subcategory
 * counts. Each finding belongs to one subtype (its backend type), so a
 * role-aware resolved_entity_id does not add a second parent count.
 */
export function groupCollapsedByFamily(entities: Entity[]): FamilyGroup[] {
  const rawByGroup = new Map<string, Entity[]>()
  for (const entity of entities) {
    const id = presentationGroupForEntityType(entity.type)
    rawByGroup.set(id, [...(rawByGroup.get(id) ?? []), entity])
  }
  const known = new Set<string>(PRESENTATION_GROUP_ORDER)
  const extra = [...rawByGroup.keys()].filter((id) => !known.has(id))
  const order = [...PRESENTATION_GROUP_ORDER, ...extra]
  return order
    .filter((id) => (rawByGroup.get(id)?.length ?? 0) > 0)
    .sort((a, b) => presentationGroupOrder(a) - presentationGroupOrder(b))
    .map((id) => {
      const types = typesWithin(rawByGroup.get(id) ?? [])
      return {
        id,
        rows: types.flatMap((group) => group.rows),
        mentionCount: types.reduce((sum, group) => sum + group.mentionCount, 0),
        types,
        flattened: shouldFlattenPresentationGroup(
          id,
          types.map((group) => group.type),
        ),
      }
    })
}

/** Collapsed list row that represents this occurrence (for scroll/highlight). */
export function listRowId(entityId: string, entities: Entity[]): string {
  const related = new Set(relatedEntityIds(entityId, entities))
  return collapseForList(entities).find((entity) => related.has(entity.id))?.id ?? entityId
}

export function pageReviewState(entities: Entity[], inspected: Set<string>, pageCount: number) {
  return Array.from({ length: pageCount }, (_, page) => {
    const onPage = entities.filter((entity) => entity.page === page)
    const pending = onPage.filter((entity) => !inspected.has(entity.id)).length
    return { page, total: onPage.length, pending }
  })
}

/** Preview prefixes. Must stay aligned with backend tag_taxonomy.py.
 * Panel grouping (listDisplayType) is independent of these families.
 * Overlay/export prefer entity.placeholder_token from the backend registry.
 */
const PLACEHOLDER_TR: Record<string, string> = {
  PERSON_NAME: 'KİŞİ',
  FIRST_NAME: 'KİŞİ',
  LAST_NAME: 'KİŞİ',
  ALIAS: 'KİŞİ',
  LAWYER_NAME: 'AVUKAT',
  JUDGE_NAME: 'HÂKİM',
  CLAIMANT_NAME: 'DAVACI',
  DEFENDANT_NAME: 'DAVALI',
  WITNESS_NAME: 'TANIK',
  EXPERT_NAME: 'BİLİRKİŞİ',
  NATIONAL_ID: 'TCKN',
  PASSPORT_NUMBER: 'PASAPORT',
  TAX_IDENTIFIER: 'VKN',
  EMPLOYEE_ID: 'PERSONEL_NO',
  CUSTOMER_ID: 'MÜŞTERİ_NO',
  OTHER_IDENTIFIER: 'TANIMLAYICI',
  PHONE_NUMBER: 'TELEFON',
  EMAIL: 'EPOSTA',
  ADDRESS: 'ADRES',
  POSTAL_CODE: 'POSTA_KODU',
  LOCATION: 'KONUM',
  IBAN: 'IBAN',
  CREDIT_CARD: 'KART',
  BANK_ACCOUNT: 'HESAP',
  FINANCIAL_IDENTIFIER: 'FİNANSAL_ID',
  CASE_NUMBER: 'ESAS',
  FILE_NUMBER: 'DOSYA',
  DECISION_NUMBER: 'KARAR',
  COURT_NAME: 'MAHKEME',
  COMPANY_NAME: 'ŞİRKET',
  ORGANISATION: 'KURUM',
  UETS: 'UETS',
  QR_CODE: 'KAREKOD',
  UYAP_ACCESS: 'UYAP',
  SIGNATURE: 'İMZA',
  DATE: 'TARİH',
  DATE_OF_BIRTH: 'DOĞUM_TARİHİ',
  BIRTH_PLACE: 'DOĞUM_YERİ',
  PROFESSIONAL_ID: 'SİCİL',
  PORT_NUMBER: 'PORT',
  MONEY_AMOUNT: 'TUTAR',
  SYSTEM_URL: 'SİSTEM_URL',
  IP_ADDRESS: 'IP',
  URL: 'URL',
  VEHICLE_PLATE: 'PLAKA',
  SALARY_INFORMATION: 'MAAŞ',
  POLITICAL_INFORMATION: 'SİYASİ',
}

const PLACEHOLDER_EN: Record<string, string> = {
  PERSON_NAME: 'PERSON',
  FIRST_NAME: 'PERSON',
  LAST_NAME: 'PERSON',
  ALIAS: 'PERSON',
  LAWYER_NAME: 'LAWYER',
  JUDGE_NAME: 'JUDGE',
  CLAIMANT_NAME: 'CLAIMANT',
  DEFENDANT_NAME: 'DEFENDANT',
  WITNESS_NAME: 'WITNESS',
  EXPERT_NAME: 'EXPERT',
  NATIONAL_ID: 'NATIONAL_ID',
  PASSPORT_NUMBER: 'PASSPORT',
  TAX_IDENTIFIER: 'TAX_ID',
  EMPLOYEE_ID: 'EMPLOYEE_ID',
  CUSTOMER_ID: 'CUSTOMER_ID',
  OTHER_IDENTIFIER: 'IDENTIFIER',
  PHONE_NUMBER: 'PHONE',
  EMAIL: 'EMAIL',
  ADDRESS: 'ADDRESS',
  POSTAL_CODE: 'POSTAL_CODE',
  LOCATION: 'LOCATION',
  IBAN: 'IBAN',
  CREDIT_CARD: 'CARD',
  BANK_ACCOUNT: 'ACCOUNT',
  FINANCIAL_IDENTIFIER: 'FINANCIAL_ID',
  CASE_NUMBER: 'CASE_NO',
  FILE_NUMBER: 'FILE_NO',
  DECISION_NUMBER: 'DECISION_NO',
  COURT_NAME: 'COURT',
  COMPANY_NAME: 'COMPANY',
  ORGANISATION: 'ORGANISATION',
  UETS: 'UETS',
  QR_CODE: 'QR',
  UYAP_ACCESS: 'UYAP',
  SIGNATURE: 'SIGNATURE',
  DATE: 'DATE',
  DATE_OF_BIRTH: 'DATE_OF_BIRTH',
  BIRTH_PLACE: 'PLACE_OF_BIRTH',
  PROFESSIONAL_ID: 'REGISTRY_NO',
  PORT_NUMBER: 'PORT',
  MONEY_AMOUNT: 'AMOUNT',
  SYSTEM_URL: 'SYSTEM_URL',
  IP_ADDRESS: 'IP',
  URL: 'URL',
  VEHICLE_PLATE: 'VEHICLE_PLATE',
  SALARY_INFORMATION: 'SALARY',
  POLITICAL_INFORMATION: 'POLITICAL',
}

const UNNUMBERED_PLACEHOLDER = new Set([
  'DATE',
  'POSTAL_CODE',
  'MONEY_AMOUNT',
  'COURT_NAME',
  'SALARY_INFORMATION',
  'POLITICAL_INFORMATION',
  'SIGNATURE',
  'QR_CODE',
  'UYAP_ACCESS',
])

const PERSON_TAG_TYPES = new Set([
  'PERSON_NAME',
  'FIRST_NAME',
  'LAST_NAME',
  'ALIAS',
  'CLAIMANT_NAME',
  'DEFENDANT_NAME',
  'LAWYER_NAME',
  'JUDGE_NAME',
  'WITNESS_NAME',
  'EXPERT_NAME',
])

const ROLE_TAG_TYPES = new Set([
  'CLAIMANT_NAME',
  'DEFENDANT_NAME',
  'LAWYER_NAME',
  'JUDGE_NAME',
  'WITNESS_NAME',
  'EXPERT_NAME',
])

const TYPE_TAG_FAMILY: Record<string, string> = {
  PERSON_NAME: 'PERSON',
  FIRST_NAME: 'PERSON',
  LAST_NAME: 'PERSON',
  ALIAS: 'PERSON',
  CLAIMANT_NAME: 'CLAIMANT',
  DEFENDANT_NAME: 'DEFENDANT',
  LAWYER_NAME: 'LAWYER',
  JUDGE_NAME: 'JUDGE',
  WITNESS_NAME: 'WITNESS',
  EXPERT_NAME: 'EXPERT',
}

function placeholderLabel(type: string, language: string) {
  const pack = language.startsWith('tr') ? PLACEHOLDER_TR : PLACEHOLDER_EN
  return pack[type] ?? (language.startsWith('tr') ? 'ETİKET' : 'LABEL')
}

function foldTagIdentity(value: string): string {
  return value
    .normalize('NFKC')
    .replace(/İ/g, 'i')
    .replace(/I/g, 'ı')
    .toLocaleLowerCase('tr-TR')
    .replace(/\u0307/g, '')
    .replace(/ı/g, 'i')
    .replace(/\s+/g, ' ')
    .trim()
}

function placeholderIdentityKey(entity: Entity): string {
  if (PERSON_TAG_TYPES.has(entity.type)) {
    const stripped = entity.text.replace(/['’′][A-Za-zçğıöşüâîûÇĞİÖŞÜ]+$/, '').trim()
    return `PERSON|${foldTagIdentity(stripped).replace(/\s+/g, '')}`
  }
  if (UNNUMBERED_PLACEHOLDER.has(entity.type)) return `occ|${entity.id}`
  const compact = foldTagIdentity(entity.text).replace(/[\s\-_.]+/g, '')
  return `${entity.type}|${compact}`
}

function placeholderFamily(entity: Entity, entities: Entity[]): string {
  if (!PERSON_TAG_TYPES.has(entity.type)) {
    return TYPE_TAG_FAMILY[entity.type] ?? entity.type
  }
  const key = placeholderIdentityKey(entity)
  const roles = [
    ...new Set(
      entities
        .filter((item) => PERSON_TAG_TYPES.has(item.type) && placeholderIdentityKey(item) === key)
        .map((item) => item.type)
        .filter((type) => ROLE_TAG_TYPES.has(type))
        .map((type) => TYPE_TAG_FAMILY[type] ?? 'PERSON'),
    ),
  ]
  if (roles.length === 1) return roles[0]
  return 'PERSON'
}

function byDocumentOrder(left: Entity, right: Entity): number {
  return left.page - right.page || left.start - right.start || left.id.localeCompare(right.id)
}

/** Family-local numbers for distinct canonical keys. Prefers backend-stamped tokens. */
export function placeholderTokensByEntityId(
  entities: Entity[],
  language: string,
): Map<string, string> {
  const tokens = new Map<string, string>()
  const firstByFamilyKey = new Map<string, Entity>()
  for (const entity of [...entities].sort(byDocumentOrder)) {
    if (entity.placeholder_token?.trim()) {
      tokens.set(entity.id, entity.placeholder_token.trim())
      continue
    }
    const family = placeholderFamily(entity, entities)
    const identity = placeholderIdentityKey(entity)
    const grouped = `${family}|${identity}`
    if (!firstByFamilyKey.has(grouped)) firstByFamilyKey.set(grouped, entity)
  }
  const counters = new Map<string, number>()
  const numbers = new Map<string, number>()
  for (const [grouped] of [...firstByFamilyKey.entries()].sort(
    (left, right) => byDocumentOrder(left[1], right[1]),
  )) {
    const family = grouped.slice(0, grouped.indexOf('|'))
    const next = (counters.get(family) ?? 0) + 1
    counters.set(family, next)
    numbers.set(grouped, next)
  }
  for (const entity of entities) {
    if (tokens.has(entity.id)) continue
    const typeLabel = placeholderLabel(entity.type, language)
    if (UNNUMBERED_PLACEHOLDER.has(entity.type)) {
      tokens.set(entity.id, `[${typeLabel}]`)
      continue
    }
    const family = placeholderFamily(entity, entities)
    const grouped = `${family}|${placeholderIdentityKey(entity)}`
    const index = numbers.get(grouped) ?? 1
    const familyType =
      [...ROLE_TAG_TYPES].find((type) => TYPE_TAG_FAMILY[type] === family) ?? entity.type
    const label =
      family === 'PERSON'
        ? placeholderLabel('PERSON_NAME', language)
        : placeholderLabel(familyType, language)
    tokens.set(entity.id, `[${label}_${index}]`)
  }
  return tokens
}

function initialsOf(text: string) {
  const stripped = text.replace(/['’′][A-Za-zçğıöşüâîûÇĞİÖŞÜ]+$/, '').trim()
  const parts = stripped.split(/\s+/).filter(Boolean)
  const initials = parts.map((part) => `${part[0]?.toUpperCase() ?? ''}.`).join('')
  const suffix = text.slice(stripped.length)
  if (!suffix) return initials
  return `${initials}${suffix.startsWith("'") || suffix.startsWith('’') ? suffix : `'${suffix}`}`
}

export const COURT_ORDINAL_TAG = 'X'

export function labelCourtOrdinals(text: string, tag = COURT_ORDINAL_TAG) {
  return text.replace(/\b\d{1,3}\s*\./g, tag)
}

function courtHasOrdinal(text: string) {
  return /\b\d{1,3}\s*\./.test(text)
}

function isDutyCourt(text: string) {
  return /(?<![\p{L}\p{N}_])n[oö]bet[cç]i(?![\p{L}\p{N}_])/iu.test(text)
}

function previewCourtValue(
  text: string,
  language: string,
  options?: {
    placeholderToken?: string | null
    entity?: Entity
    entities?: Entity[]
  },
) {
  if (courtHasOrdinal(text)) return labelCourtOrdinals(text)
  if (isDutyCourt(text)) return text
  const stamped = options?.placeholderToken?.trim()
  if (stamped) return stamped
  const peers = (options?.entities ?? [])
    .filter(
      (item) =>
        item.type === 'COURT_NAME' && !courtHasOrdinal(item.text) && !isDutyCourt(item.text),
    )
    .sort((left, right) => left.start - right.start || left.id.localeCompare(right.id))
  const index = options?.entity
    ? Math.max(1, peers.findIndex((item) => item.id === options.entity?.id) + 1)
    : 1
  return `[${placeholderLabel('COURT_NAME', language)}_${index || 1}]`
}

function partialMaskDateOfBirth(text: string) {
  const matches = [...text.matchAll(/\d+/g)]
  if (!matches.length) return '█'.repeat(Math.max(1, text.length))

  const isYear4 = (value: string) => /^(?:19|20)\d{2}$/.test(value)
  const yearMatch =
    [...matches].reverse().find((match) => isYear4(match[0])) ??
    [...matches].reverse().find((match) => match[0].length === 4) ??
    (matches.length === 3 && matches[2][0].length === 2 ? matches[2] : undefined)
  if (!yearMatch) return '█'.repeat(Math.max(1, text.length))

  let out = ''
  let cursor = 0
  for (const match of matches) {
    const start = match.index ?? 0
    out += text.slice(cursor, start)
    out += match === yearMatch ? match[0] : '*'.repeat(match[0].length)
    cursor = start + match[0].length
  }
  return out + text.slice(cursor)
}

function partialMaskOf(text: string, type: string) {
  if (type === 'EMAIL' && text.includes('@')) {
    const [local, domain] = text.split('@')
    return `${local[0] ?? ''}${'*'.repeat(Math.max(1, local.length - 1))}@${domain}`
  }
  if (type === 'DATE_OF_BIRTH') {
    return partialMaskDateOfBirth(text)
  }
  if (type === 'COURT_NAME') {
    return text.replace(/\b(\d{1,3})\s*(\.)/g, (_all, digits: string, dot: string) => `${'█'.repeat(digits.length)}${dot}`)
  }
  if (type === 'PHONE_NUMBER') {
    const digits = text.replace(/\D/g, '')
    return digits.length >= 7
      ? `${digits.slice(0, 4)} *** ** ${digits.slice(-2)}`
      : '█'.repeat(Math.max(1, text.length))
  }
  if (type === 'IBAN') {
    const compact = text.replace(/\s+/g, '').toUpperCase()
    const masked = `${compact.slice(0, 4)}${'*'.repeat(Math.max(4, compact.length - 6))}${compact.slice(-2)}`
    return masked.replace(/(.{4})/g, '$1 ').trim()
  }
  const compact = text.replace(/\s+/g, '')
  return compact.length > 4
    ? `${'*'.repeat(compact.length - 4)}${compact.slice(-4)}`
    : '█'.repeat(Math.max(1, text.length))
}

/** Client-side approximation of how one entity will appear. */
export function previewEntityValue(
  text: string,
  type: string,
  strategy: TransformationStrategy,
  language: string,
  options?: {
    role?: string
    index?: number
    placeholderToken?: string | null
    entity?: Entity
    entities?: Entity[]
  },
): string {
  if (strategy === 'KEEP') return text
  if (strategy === 'REDACT') return '█'.repeat(Math.max(3, Math.min(text.length, 14)))
  if (strategy === 'PLACEHOLDER') {
    if (type === 'COURT_NAME') return previewCourtValue(text, language, options)
    if (options?.placeholderToken?.trim()) return options.placeholderToken.trim()
    if (options?.entity && options.entities?.length) {
      return placeholderTokensByEntityId(options.entities, language).get(options.entity.id)
        ?? placeholderTagPreview(type, language, options?.index ?? 1)
    }
    return placeholderTagPreview(type, language, options?.index ?? 1)
  }
  if (strategy === 'INITIALS') return initialsOf(text)
  if (strategy === 'PARTIAL_MASK') return partialMaskOf(text, type)
  return text
}

/** Compact "original → result" example for method pickers. */
export function strategyResultExample(
  text: string,
  type: string,
  strategy: TransformationStrategy,
  language: string,
  options?: {
    role?: string
    index?: number
    placeholderToken?: string | null
    entity?: Entity
    entities?: Entity[]
  },
): string {
  return `${text} → ${previewEntityValue(text, type, strategy, language, options)}`
}

export function placeholderTagPreview(type: string, language: string, index = 1): string {
  const prefix = placeholderLabel(type, language)
  if (UNNUMBERED_PLACEHOLDER.has(type)) return `[${prefix}]`
  return `[${prefix}_${index}]`
}

/** Distinct tag examples for types currently visible in a panel group. */
export function placeholderSamplesForTypes(types: string[], language: string): string[] {
  const seen = new Set<string>()
  const samples: string[] = []
  for (const type of types) {
    const sample = placeholderTagPreview(type, language, 1)
    if (seen.has(sample)) continue
    seen.add(sample)
    samples.push(sample)
  }
  return samples
}

export function labelPreview(text: string, type: string, index: number, language: string) {
  return `${text} → ${placeholderTagPreview(type, language, index)}`
}

/** Lightweight client-side preview for common strategies (instant feedback). */
export function previewTransformLocal(
  text: string,
  entities: Entity[],
  decisions: Decisions,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
  language: string,
): string {
  const counters = new Map<string, number>()
  const tokens = placeholderTokensByEntityId(entities, language)
  type Op = { start: number; end: number; replacement: string }
  const ops: Op[] = []

  for (const entity of [...entities].sort((a, b) => a.start - b.start)) {
    const strategy = effectiveStrategy(entity, decisions, categoryDefaults, entityStrategies)
    if (strategy === 'KEEP') continue
    const original = text.slice(entity.start, entity.end)
    let replacement = original
    let end = entity.end

    const key = entity.resolved_entity_id ?? entity.id
    if (!counters.has(key)) counters.set(key, counters.size + 1)
    replacement = previewEntityValue(original, entity.type, strategy, language, {
      role: entity.role_confident ? entity.role : undefined,
      index: counters.get(key),
      placeholderToken: entity.placeholder_token ?? tokens.get(entity.id),
      entity,
      entities,
    })
    if (strategy === 'REDACT') {
      replacement = '█'.repeat(Math.max(1, original.length))
    }

    ops.push({ start: entity.start, end, replacement })
  }

  let output = text
  for (const op of [...ops].sort((a, b) => b.start - a.start)) {
    output = output.slice(0, op.start) + op.replacement + output.slice(op.end)
  }
  return output
}

export function validationCounts(result: Result) {
  const failed = result.validation.failed_count
    ?? (result.validation.status === 'FAILED' ? 1 : 0)
  const warnings = result.validation.warning_count
    ?? (result.validation.status === 'WARNING' ? 1 : 0)
  const verified = result.validation.verified_count ?? 0
  return { failed, warnings, verified }
}

export function selectedTransformationCount(
  decisions: Decisions,
  manual: ManualRedaction[],
): number {
  return tallyDecisions(decisions, manual).redact
}

export function canApplyRedactions(
  decisions: Decisions,
  manual: ManualRedaction[],
): boolean {
  return selectedTransformationCount(decisions, manual) > 0
}

export function analysisStatusOf(analysis: Analysis | null): AnalysisStatus {
  return analysis?.analysis_status ?? 'COMPLETE'
}

const STRONG_DETECTORS = new Set([
  'TR_TCKN',
  'TR_IBAN',
  'GLOBAL_IBAN',
  'GLOBAL_LUHN_CARD',
  'GLOBAL_EMAIL',
  'GLOBAL_IPV4',
  'TR_MOBILE_PHONE',
  'TR_LANDLINE_PHONE',
  'TR_VKN',
  'USER_DEFINED_TERM',
])

export function verificationLevel(entity: Entity): 'validated' | 'review_recommended' {
  if (entity.verification_level === 'validated' || entity.verification_level === 'review_recommended') {
    return entity.verification_level
  }
  if (entity.validated && STRONG_DETECTORS.has(entity.detector)) return 'validated'
  return 'review_recommended'
}

export function detectionSource(entity: Entity): 'verified' | 'structural' | 'contextual' | 'manual' {
  if (entity.method === 'MANUAL') return 'manual'
  if (entity.method === 'AI') return 'contextual'
  if (entity.method === 'STRUCTURAL') return 'structural'
  return 'verified'
}

export function sourceLabelKey(source: ReturnType<typeof detectionSource>): string {
  if (source === 'contextual') return 'sourceAi'
  if (source === 'manual') return 'sourceManual'
  if (source === 'structural') return 'sourceStructural'
  return 'sourceLocal'
}

export type PhraseHit = {
  page: number
  line: string
  start: number
  end: number
  match: string
}

function originalIndexFromFolded(line: string, foldedAt: number): number {
  let folded = 0
  for (let index = 0; index < line.length; index += 1) {
    if (folded === foldedAt) return index
    folded += line[index].toLocaleLowerCase('tr').length
  }
  return Math.min(foldedAt, line.length)
}

export function findDocumentPhraseHits(pages: string[], needle: string, limit = 80): PhraseHit[] {
  const query = needle.trim()
  if (query.length < 2) return []
  const foldedNeedle = query.toLocaleLowerCase('tr')
  const hits: PhraseHit[] = []
  let offset = 0
  for (let page = 0; page < pages.length; page += 1) {
    const text = pages[page] ?? ''
    const lines = text.split('\n')
    let local = 0
    for (const line of lines) {
      const foldedLine = line.toLocaleLowerCase('tr')
      let from = 0
      while (from <= foldedLine.length - foldedNeedle.length) {
        const at = foldedLine.indexOf(foldedNeedle, from)
        if (at < 0) break
        const originalAt = originalIndexFromFolded(line, at)
        hits.push({
          page,
          line: line.trim(),
          start: offset + local + originalAt,
          end: offset + local + originalAt + query.length,
          match: line.slice(originalAt, originalAt + query.length),
        })
        if (hits.length >= limit) return hits
        from = at + Math.max(1, foldedNeedle.length)
      }
      local += line.length + 1
    }
    offset += text.length
  }
  return hits
}

function termTextMatches(entity: Entity, query: string): boolean {
  const text = entity.text.toLocaleLowerCase('tr')
  const attr = String(entity.attributes?.term ?? '').toLocaleLowerCase('tr')
  return attr === query || text === query || (query.length >= 2 && text.startsWith(query))
}

/** Entity ids that should receive the custom-term mask after /custom-terms. */
export function customTermTargetIds(
  entities: Entity[],
  term: UserDefinedTerm,
  previousIds: Iterable<string>,
): string[] {
  const prior = new Set(previousIds)
  const query = term.value.trim().toLocaleLowerCase('tr')
  const starts = new Set(term.starts ?? [])
  const ids: string[] = []
  const seen = new Set<string>()
  const take = (id: string) => {
    if (seen.has(id)) return
    seen.add(id)
    ids.push(id)
  }
  for (const entity of entities) {
    if (!prior.has(entity.id) && entity.detector === 'USER_DEFINED_TERM') {
      take(entity.id)
    }
  }
  for (const entity of entities) {
    const detectorMatch =
      entity.detector === 'USER_DEFINED_TERM' && termTextMatches(entity, query)
    const exactStart = starts.size > 0 && starts.has(entity.start)
    const sameCategory =
      entity.type === term.category || listDisplayType(entity.type) === term.category
    if (detectorMatch || (exactStart && sameCategory)) take(entity.id)
  }
  return ids
}
