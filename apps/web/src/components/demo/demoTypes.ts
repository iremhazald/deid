export type DemoLocale = 'tr' | 'en'

export type DemoCategory =
  | 'person'
  | 'identifier'
  | 'address'
  | 'case'
  | 'court'
  | 'company'
  | 'contact'
  | 'financial'

export type DemoTextState = 'idle' | 'detected' | 'transforming' | 'transformed'

export type DemoMethod =
  | 'redact'
  | 'placeholder'
  | 'initials'
  | 'partial'

export type DemoEntity = {
  /** Relative order used to stagger the detection pass (not a wall-clock timestamp). */
  at: number
  category: DemoCategory
  /** Floating category label is only shown for a handful of entities. */
  label?: true
  method?: DemoMethod
  replacement?: string
  transformAt?: number
}

export type DemoScript = {
  detections: Record<string, DemoEntity>
  categories: DemoCategory[]
  maxAt: number
  scrollAnchor: (elapsed: number) => string
}
