import { useContext } from 'react'
import type { ReactNode } from 'react'
import { DemoContext } from './demoContext'
import {
  demoEntityCategory,
  demoEntityHasLabel,
  demoEntityMethod,
  demoEntityReplacement,
  demoTextState,
  type DemoEntityId,
} from './demoScript'

type Props = {
  id: DemoEntityId
  children: ReactNode
}

/**
 * A span of the synthetic document that walks through
 * Detection and transformation are separate states. Only the four selected
 * synthetic transformation examples transform; other detections return to their
 * normal text.
 */
export function RedactableDemoText({ id, children }: Props) {
  const { elapsed, locale, categoryLabels, methodLabels } = useContext(DemoContext)
  const state = demoTextState(locale, id, elapsed)
  const category = demoEntityCategory(locale, id)
  const method = demoEntityMethod(locale, id)
  const replacement = demoEntityReplacement(locale, id)
  const transformed = state === 'transformed'
  const label = state === 'transforming' && method
    ? methodLabels[method]
    : category
      ? categoryLabels[category]
      : undefined

  if (!category) return <>{children}</>

  return (
    <span
      className={`rdt rdt-${state}${method ? ` rdt-method-${method}` : ''}`}
      data-category={category}
      aria-label={transformed && replacement ? replacement : undefined}
    >
      <span className="rdt-text">
        {transformed && replacement ? replacement : children}
      </span>
      {((state === 'detected' && demoEntityHasLabel(locale, id)) || state === 'transforming') && (
        <span className="rdt-label">{label}</span>
      )}
    </span>
  )
}
