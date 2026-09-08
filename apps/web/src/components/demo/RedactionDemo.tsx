import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { DemoContractDocument } from './DemoContractDocument'
import { DemoCourtDocument } from './DemoCourtDocument'
import { DemoContext } from './demoContext'
import {
  DEMO_SCRIPTS,
  DEMO_STATIC_ELAPSED,
  DEMO_TOTAL,
  demoDetectedCounts,
  demoIsComplete,
  demoIsTransforming,
  demoLocaleFromLanguage,
  demoSceneOpacity,
  demoScrollAnchor,
  demoStage,
  type DemoCategory,
  type DemoMethod,
} from './demoScript'

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const sync = () => setReduced(query.matches)
    sync()
    query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])
  return reduced
}

/**
 * Landing-page product demonstration.
 *
 * Locale selects the synthetic document: the Turkish reasoned decision on `/`,
 * and the English Master Services Agreement on `/en`. Detection and the four
 * transformation examples are driven by the shared animation engine. It never
 * calls the product backend.
 */
export function RedactionDemo() {
  const { t, i18n } = useTranslation()
  const locale = demoLocaleFromLanguage(i18n.language)
  const script = DEMO_SCRIPTS[locale]
  const reducedMotion = usePrefersReducedMotion()
  const [elapsed, setElapsed] = useState(0)
  const viewportRef = useRef<HTMLDivElement>(null)
  const pageRef = useRef<HTMLDivElement>(null)
  const scrollTargetRef = useRef(-1)
  const Document = locale === 'en' ? DemoContractDocument : DemoCourtDocument

  useEffect(() => {
    setElapsed(reducedMotion ? DEMO_STATIC_ELAPSED : 0)
    scrollTargetRef.current = -1
  }, [locale, reducedMotion])

  useEffect(() => {
    if (reducedMotion) {
      setElapsed(DEMO_STATIC_ELAPSED)
      return
    }

    let frame = 0
    let start = 0

    const tick = (now: number) => {
      if (!start) start = now
      setElapsed((now - start) % DEMO_TOTAL)
      frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [reducedMotion, locale])

  useEffect(() => {
    const viewport = viewportRef.current
    const page = pageRef.current
    if (!viewport || !page) return

    const anchor = page.querySelector<HTMLElement>(`[data-anchor="${demoScrollAnchor(locale, elapsed)}"]`)
    const maxScroll = Math.max(0, page.scrollHeight - viewport.clientHeight)
    const target = anchor ? Math.min(maxScroll, Math.max(0, anchor.offsetTop - 18)) : 0

    // Only issue a scroll when the destination changes, otherwise every frame
    // would restart the smooth scroll and the viewport would never settle.
    if (Math.abs(target - scrollTargetRef.current) < 2) return
    scrollTargetRef.current = target
    viewport.style.scrollBehavior = elapsed < 400 ? 'auto' : 'smooth'
    viewport.scrollTop = target
  }, [elapsed, locale])

  const categoryLabels = useMemo(
    () =>
      Object.fromEntries(
        script.categories.map((category) => [category, t(`demo.cat.${category}`)]),
      ) as Partial<Record<DemoCategory, string>>,
    [script.categories, t],
  )

  const methodLabels = useMemo<Record<DemoMethod, string>>(
    () => ({
      redact: t('demo.methods.redact'),
      placeholder: t('demo.methods.placeholder'),
      initials: t('demo.methods.initials'),
      partial: t('demo.methods.partial'),
    }),
    [t],
  )

  const counts = demoDetectedCounts(locale, elapsed)
  const complete = demoIsComplete(elapsed)
  const transforming = demoIsTransforming(elapsed)
  const stage = demoStage(elapsed)
  const status = stage.kind === 'detection'
    ? t('demo.analyzing')
    : stage.kind === 'method'
      ? t('demo.methodStatus', {
          current: String(stage.index).padStart(2, '0'),
          method: methodLabels[stage.method],
        })
      : t('demo.methodsTitle')

  return (
    <DemoContext.Provider value={{ elapsed, locale, categoryLabels, methodLabels }}>
      <div className="demo-frame">
        <div className="demo-chrome">
          <span className="demo-chrome-label">{t('demo.frameLabel')}</span>
          <span className="demo-chrome-live" aria-live="polite">
            <span className={`demo-live-dot${complete ? ' is-done' : ''}`} aria-hidden="true" />
            {status}
          </span>
        </div>

        <div
          className="demo-viewport"
          ref={viewportRef}
          style={{ opacity: demoSceneOpacity(elapsed) }}
        >
          <Document key={locale} pageRef={pageRef} />
        </div>

        <div className={`demo-meter${transforming ? ' is-transforming' : ''}`}>
          {transforming ? (
            <div className="demo-method-summary">
              <strong>{t('demo.methodsTitle')}</strong>
              <span>{t('demo.methodsSummary')}</span>
            </div>
          ) : (
            script.categories.map((category) => (
              <MeterItem
                key={category}
                category={category}
                count={counts[category] ?? 0}
                label={t(`demo.short.${category}`)}
              />
            ))
          )}
        </div>
      </div>
    </DemoContext.Provider>
  )
}

function MeterItem({
  category,
  count,
  label,
}: {
  category: DemoCategory
  count: number
  label: string
}) {
  return (
    <span className={`demo-meter-item${count > 0 ? ' is-active' : ''}`} data-category={category}>
      {label}
      <b className="demo-meter-count">{count}</b>
    </span>
  )
}
