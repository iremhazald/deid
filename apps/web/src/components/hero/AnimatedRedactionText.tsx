import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

type RedactionState = 'normal' | 'detected' | 'redacted'

/** Loop keyframes in milliseconds. */
const DETECT_AT = 1800
const REDACT_AT = 2100
const RELEASE_AT = 5000
const CYCLE = 7000

function stateAt(elapsed: number): RedactionState {
  if (elapsed < DETECT_AT) return 'normal'
  if (elapsed < REDACT_AT) return 'detected'
  if (elapsed < RELEASE_AT) return 'redacted'
  return 'normal'
}

type Props = {
  children: ReactNode
}

/**
 * Headline phrase that demonstrates the product on itself: the words are
 * detected, then covered by a redaction bar drawn across them, then released.
 *
 * The phrase stays in the DOM at full width the whole time, so the rest of the
 * sentence never moves and assistive technology still reads the full headline.
 * Purely decorative — it shares the visual language of the document demo but
 * none of its state.
 */
export function AnimatedRedactionText({ children }: Props) {
  const [state, setState] = useState<RedactionState>('normal')

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const start = performance.now()
    const timer = window.setInterval(() => {
      setState(stateAt((performance.now() - start) % CYCLE))
    }, 100)

    return () => window.clearInterval(timer)
  }, [])

  return (
    <span className="arx" data-state={state}>
      <span className="arx-text">{children}</span>
      <span className="arx-bar" aria-hidden="true" />
    </span>
  )
}
