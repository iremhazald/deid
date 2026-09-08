/**
 * Review-panel presentation taxonomy.
 *
 * Backend entity types stay authoritative. This module only decides how those
 * types are grouped, labeled, and nested in the right-hand review panel.
 */

export const PRESENTATION_GROUP_ORDER = [
  'person',
  'identity',
  'address',
  'contact',
  'banking',
  'file',
  'court',
  'organisation',
  'cyber',
  'other',
  'visual',
] as const

export type PresentationGroupId = (typeof PRESENTATION_GROUP_ORDER)[number]

/** Backend types collapsed into the generic Personal names subcategory. */
export const GENERIC_PERSON_TYPES = [
  'PERSON_NAME',
  'FIRST_NAME',
  'LAST_NAME',
  'ALIAS',
] as const

const PERSON_SUBCATEGORY_ORDER = [
  'PERSON_NAME',
  'CLAIMANT_NAME',
  'DEFENDANT_NAME',
  'LAWYER_NAME',
  'JUDGE_NAME',
  'WITNESS_NAME',
  'EXPERT_NAME',
] as const

const IDENTITY_SUBCATEGORY_ORDER = [
  'NATIONAL_ID',
  'PASSPORT_NUMBER',
  'TAX_IDENTIFIER',
  'EMPLOYEE_ID',
  'CUSTOMER_ID',
  'OTHER_IDENTIFIER',
  'VEHICLE_PLATE',
  'DATE_OF_BIRTH',
  'BIRTH_PLACE',
  'SIGNATURE',
] as const

const ADDRESS_SUBCATEGORY_ORDER = ['ADDRESS', 'UETS', 'POSTAL_CODE', 'LOCATION'] as const

const CONTACT_SUBCATEGORY_ORDER = ['PHONE_NUMBER', 'EMAIL'] as const

const BANKING_SUBCATEGORY_ORDER = [
  'IBAN',
  'BANK_ACCOUNT',
  'CREDIT_CARD',
  'FINANCIAL_IDENTIFIER',
] as const

const FILE_SUBCATEGORY_ORDER = [
  'CASE_NUMBER',
  'FILE_NUMBER',
  'DECISION_NUMBER',
  'UYAP_ACCESS',
] as const

const COURT_SUBCATEGORY_ORDER = ['COURT_NAME', 'PROFESSIONAL_ID'] as const

const ORGANISATION_SUBCATEGORY_ORDER = ['COMPANY_NAME', 'ORGANISATION'] as const

const CYBER_SUBCATEGORY_ORDER = [
  'IP_ADDRESS',
  'URL',
  'SYSTEM_URL',
  'PORT_NUMBER',
] as const

const OTHER_SUBCATEGORY_ORDER = [
  'DATE',
] as const

const VISUAL_SUBCATEGORY_ORDER = ['QR_CODE'] as const

const GROUP_SUBCATEGORIES: Record<PresentationGroupId, readonly string[]> = {
  person: PERSON_SUBCATEGORY_ORDER,
  identity: IDENTITY_SUBCATEGORY_ORDER,
  address: ADDRESS_SUBCATEGORY_ORDER,
  contact: CONTACT_SUBCATEGORY_ORDER,
  banking: BANKING_SUBCATEGORY_ORDER,
  file: FILE_SUBCATEGORY_ORDER,
  court: COURT_SUBCATEGORY_ORDER,
  organisation: ORGANISATION_SUBCATEGORY_ORDER,
  cyber: CYBER_SUBCATEGORY_ORDER,
  other: OTHER_SUBCATEGORY_ORDER,
  visual: VISUAL_SUBCATEGORY_ORDER,
}

const TYPE_TO_SUBCATEGORY: Record<string, string> = {
  PERSON_NAME: 'PERSON_NAME',
  FIRST_NAME: 'PERSON_NAME',
  LAST_NAME: 'PERSON_NAME',
  ALIAS: 'PERSON_NAME',
  CLAIMANT_NAME: 'CLAIMANT_NAME',
  DEFENDANT_NAME: 'DEFENDANT_NAME',
  LAWYER_NAME: 'LAWYER_NAME',
  JUDGE_NAME: 'JUDGE_NAME',
  WITNESS_NAME: 'WITNESS_NAME',
  EXPERT_NAME: 'EXPERT_NAME',
  NATIONAL_ID: 'NATIONAL_ID',
  PASSPORT_NUMBER: 'PASSPORT_NUMBER',
  TAX_IDENTIFIER: 'TAX_IDENTIFIER',
  EMPLOYEE_ID: 'EMPLOYEE_ID',
  CUSTOMER_ID: 'CUSTOMER_ID',
  OTHER_IDENTIFIER: 'OTHER_IDENTIFIER',
  PROFESSIONAL_ID: 'PROFESSIONAL_ID',
  VEHICLE_PLATE: 'VEHICLE_PLATE',
  DATE_OF_BIRTH: 'DATE_OF_BIRTH',
  BIRTH_PLACE: 'BIRTH_PLACE',
  SIGNATURE: 'SIGNATURE',
  ADDRESS: 'ADDRESS',
  UETS: 'UETS',
  POSTAL_CODE: 'POSTAL_CODE',
  LOCATION: 'LOCATION',
  PHONE_NUMBER: 'PHONE_NUMBER',
  EMAIL: 'EMAIL',
  IBAN: 'IBAN',
  BANK_ACCOUNT: 'BANK_ACCOUNT',
  CREDIT_CARD: 'CREDIT_CARD',
  FINANCIAL_IDENTIFIER: 'FINANCIAL_IDENTIFIER',
  CASE_NUMBER: 'CASE_NUMBER',
  FILE_NUMBER: 'FILE_NUMBER',
  DECISION_NUMBER: 'DECISION_NUMBER',
  UYAP_ACCESS: 'UYAP_ACCESS',
  COURT_NAME: 'COURT_NAME',
  COMPANY_NAME: 'COMPANY_NAME',
  ORGANISATION: 'ORGANISATION',
  IP_ADDRESS: 'IP_ADDRESS',
  URL: 'URL',
  SYSTEM_URL: 'SYSTEM_URL',
  PORT_NUMBER: 'PORT_NUMBER',
  DATE: 'DATE',
  QR_CODE: 'QR_CODE',
}

const SUBCATEGORY_TO_GROUP = new Map<string, PresentationGroupId>(
  PRESENTATION_GROUP_ORDER.flatMap((group) =>
    GROUP_SUBCATEGORIES[group].map((sub) => [sub, group] as const),
  ),
)

const SUBCATEGORY_BACKEND_TYPES: Record<string, readonly string[]> = {
  PERSON_NAME: GENERIC_PERSON_TYPES,
}

/**
 * Flatten when a group has one meaningful detected subtype, or when the group
 * is structurally a single backend subtype (visual QR).
 *
 * Flattening still binds method control to that subtype's backend type(s), so
 * strategy editability is preserved. Nested rows appear when two or more
 * detected subcategories share a group, and when a lone Person-group role
 * (lawyer, judge, …) would otherwise lose its distinct label and method.
 */
export function shouldFlattenPresentationGroup(
  groupId: string,
  detectedSubcategories: readonly string[],
): boolean {
  if (isStructurallySingleSubtype(groupId)) return true
  if (detectedSubcategories.length > 1) return false
  if (groupId === 'person' && detectedSubcategories[0] !== 'PERSON_NAME') {
    return false
  }
  return true
}

export function isStructurallySingleSubtype(groupId: string): boolean {
  const subs = GROUP_SUBCATEGORIES[groupId as PresentationGroupId]
  return (subs?.length ?? 0) <= 1
}

export function presentationGroupForEntityType(type: string): PresentationGroupId | 'other' {
  const subcategory = subcategoryForEntityType(type)
  return SUBCATEGORY_TO_GROUP.get(subcategory) ?? 'other'
}

export function subcategoryForEntityType(type: string): string {
  return TYPE_TO_SUBCATEGORY[type] ?? type
}

export function backendTypesForSubcategory(subcategory: string): readonly string[] {
  return SUBCATEGORY_BACKEND_TYPES[subcategory] ?? [subcategory]
}

export function presentationGroupOrder(group: string): number {
  const index = PRESENTATION_GROUP_ORDER.indexOf(group as PresentationGroupId)
  return index === -1 ? PRESENTATION_GROUP_ORDER.length : index
}

export function subcategoryOrder(type: string): number {
  const subcategory = subcategoryForEntityType(type)
  const group = presentationGroupForEntityType(type)
  const list = GROUP_SUBCATEGORIES[group as PresentationGroupId]
  if (!list) return 0
  const index = list.indexOf(subcategory)
  return index === -1 ? list.length : index
}

export function presentationGroupLabelKey(groupId: string): string {
  return `presentation.groups.${groupId}`
}

export function subcategoryLabelKey(type: string): string {
  return `categories.${subcategoryForEntityType(type)}`
}

export function presentationTypeOptions(): string[] {
  return PRESENTATION_GROUP_ORDER.flatMap((group) => [...GROUP_SUBCATEGORIES[group]])
}

/** Family lists used by filter/summary helpers. Mirrors presentation groups. */
export const CATEGORY_FAMILIES: Array<{ id: string; types: readonly string[] }> =
  PRESENTATION_GROUP_ORDER.map((id) => ({
    id,
    types: Object.entries(TYPE_TO_SUBCATEGORY)
      .filter(([, subcategory]) => SUBCATEGORY_TO_GROUP.get(subcategory) === id)
      .map(([type]) => type),
  }))
