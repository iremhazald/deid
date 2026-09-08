/**
 * Shared timeline helpers for the landing-page redaction demonstration.
 *
 * Locale-specific documents, entity IDs and scroll anchors live in
 * demoScript.tr.ts and demoScript.en.ts. Everything here is synthetic demo
 * content used purely for illustration; it is intentionally disconnected from
 * the detection pipeline and the redaction engine.
 */

import { EN_DEMO_DETECTIONS, enDemoScrollAnchor } from './demoScript.en.ts'
import { TR_DEMO_DETECTIONS, trDemoScrollAnchor } from './demoScript.tr.ts'
import type { DemoCategory, DemoEntity, DemoLocale, DemoMethod, DemoScript, DemoTextState } from './demoTypes'

export type {
  DemoCategory,
  DemoEntity,
  DemoLocale,
  DemoMethod,
  DemoScript,
  DemoTextState,
} from './demoTypes'

/** Full loop duration. Last method finishes near 6280, then a short hold and fade. */
export const DEMO_TOTAL = 7200

/** How long an entity stays highlighted before the redaction bar covers it. */
export const DEMO_DETECT_MS = 240

/** Elapsed value used when the visitor prefers reduced motion: after all four methods. */
export const DEMO_STATIC_ELAPSED = 6600

export const DEMO_DETECTION_END = 1800
export const DEMO_TRANSFORM_MS = 280

const METHOD_STAGES: Array<{ method: DemoMethod; at: number }> = [
  { method: 'redact', at: 2200 },
  { method: 'placeholder', at: 3400 },
  { method: 'initials', at: 4700 },
  { method: 'partial', at: 6000 },
]

function maxDetectionAt(detections: Record<string, DemoEntity>): number {
  return Math.max(...Object.values(detections).map((entity) => entity.at))
}

export const DEMO_SCRIPTS: Record<DemoLocale, DemoScript> = {
  tr: {
    detections: TR_DEMO_DETECTIONS,
    categories: ['person', 'identifier', 'address', 'case', 'court'],
    maxAt: maxDetectionAt(TR_DEMO_DETECTIONS),
    scrollAnchor: trDemoScrollAnchor,
  },
  en: {
    detections: EN_DEMO_DETECTIONS,
    categories: ['person', 'identifier', 'address', 'contact', 'financial', 'company'],
    maxAt: maxDetectionAt(EN_DEMO_DETECTIONS),
    scrollAnchor: enDemoScrollAnchor,
  },
}

export type TrDemoEntityId = Extract<keyof typeof TR_DEMO_DETECTIONS, string>
export type EnDemoEntityId = Extract<keyof typeof EN_DEMO_DETECTIONS, string>
export type DemoEntityId = TrDemoEntityId | EnDemoEntityId

export function demoLocaleFromLanguage(language: string): DemoLocale {
  return language.startsWith('tr') ? 'tr' : 'en'
}

function detectionAt(script: DemoScript, entity: DemoEntity): number {
  return 180 + (entity.at / script.maxAt) * 1320
}

export function demoEntity(locale: DemoLocale, id: DemoEntityId): DemoEntity | undefined {
  return DEMO_SCRIPTS[locale].detections[id]
}

export function demoTextState(
  locale: DemoLocale,
  id: DemoEntityId,
  elapsed: number,
): DemoTextState {
  const script = DEMO_SCRIPTS[locale]
  const entity = script.detections[id]
  if (!entity) return 'idle'
  const at = detectionAt(script, entity)
  if (elapsed < at) return 'idle'
  if (elapsed < at + DEMO_DETECT_MS) return 'detected'
  if (!entity.transformAt) return 'idle'
  if (elapsed < entity.transformAt) return 'idle'
  if (elapsed < entity.transformAt + DEMO_TRANSFORM_MS) return 'transforming'
  return 'transformed'
}

export function demoEntityCategory(
  locale: DemoLocale,
  id: DemoEntityId,
): DemoCategory | undefined {
  return demoEntity(locale, id)?.category
}

export function demoEntityHasLabel(locale: DemoLocale, id: DemoEntityId): boolean {
  return demoEntity(locale, id)?.label === true
}

export function demoEntityMethod(locale: DemoLocale, id: DemoEntityId): DemoMethod | undefined {
  return demoEntity(locale, id)?.method
}

export function demoEntityReplacement(locale: DemoLocale, id: DemoEntityId): string | undefined {
  return demoEntity(locale, id)?.replacement
}

/**
 * Section of the document the viewport should be parked on. Anchors are matched
 * against `data-anchor` attributes in the document; each change produces one
 * smooth glide, so the viewport follows the detections section by section.
 */
export function demoScrollAnchor(locale: DemoLocale, elapsed: number): string {
  return DEMO_SCRIPTS[locale].scrollAnchor(elapsed)
}

export function demoDetectedCounts(
  locale: DemoLocale,
  elapsed: number,
): Partial<Record<DemoCategory, number>> {
  const script = DEMO_SCRIPTS[locale]
  const counts: Partial<Record<DemoCategory, number>> = {}
  for (const category of script.categories) counts[category] = 0
  for (const entity of Object.values(script.detections)) {
    if (elapsed >= detectionAt(script, entity)) {
      counts[entity.category] = (counts[entity.category] ?? 0) + 1
    }
  }
  return counts
}

export function demoMethodSet(locale: DemoLocale): DemoMethod[] {
  const present = new Set<DemoMethod>()
  for (const entity of Object.values(DEMO_SCRIPTS[locale].detections)) {
    if (entity.method) present.add(entity.method)
  }
  return METHOD_STAGES.map((stage) => stage.method).filter((method) => present.has(method))
}

export function demoSceneOpacity(elapsed: number): number {
  if (elapsed < 260) return elapsed / 260
  const fadeStart = DEMO_TOTAL - 420
  if (elapsed > fadeStart) return Math.max(0, (DEMO_TOTAL - elapsed) / 520)
  return 1
}

export function demoIsComplete(elapsed: number): boolean {
  return elapsed >= 6280
}

export type DemoStage =
  | { kind: 'detection' }
  | { kind: 'capability' }
  | { kind: 'method'; method: DemoMethod; index: number }
  | { kind: 'complete' }

export function demoStage(elapsed: number): DemoStage {
  if (elapsed < DEMO_DETECTION_END) return { kind: 'detection' }
  if (elapsed < METHOD_STAGES[0].at) return { kind: 'capability' }
  for (let index = METHOD_STAGES.length - 1; index >= 0; index -= 1) {
    if (elapsed >= METHOD_STAGES[index].at) {
      if (elapsed >= 6480) return { kind: 'complete' }
      return { kind: 'method', method: METHOD_STAGES[index].method, index: index + 1 }
    }
  }
  return { kind: 'capability' }
}

export function demoIsTransforming(elapsed: number): boolean {
  return elapsed >= DEMO_DETECTION_END
}
