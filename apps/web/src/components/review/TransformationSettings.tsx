import type { TransformationStrategy, TransformCatalog } from '../../state/types'
import { allowedStrategiesFor } from '../../state/helpers'

type Props = {
  title: string
  recommendedLabel: string
  categories: string[]
  defaults: Record<string, TransformationStrategy>
  catalog: TransformCatalog | null
  categoryLabel: (type: string) => string
  strategyLabel: (strategy: TransformationStrategy) => string
  recommendedFor: (type: string) => TransformationStrategy | undefined
  onChange: (type: string, strategy: TransformationStrategy) => void
  showOutputFormat?: boolean
  outputFormatLabel?: string
  txtLabel?: string
  pdfLabel?: string
  outputFormat?: 'TXT' | 'PDF'
  onOutputFormatChange?: (value: 'TXT' | 'PDF') => void
}

export function TransformationSettings({
  title,
  recommendedLabel,
  categories,
  defaults,
  catalog,
  categoryLabel,
  strategyLabel,
  recommendedFor,
  onChange,
  showOutputFormat,
  outputFormatLabel,
  txtLabel,
  pdfLabel,
  outputFormat,
  onOutputFormatChange,
}: Props) {
  return (
    <section className="settings-block">
      <h3>{title}</h3>
      <div className="strategy-defaults">
        {categories.map((type) => {
          const recommended = recommendedFor(type)
          const allowed = allowedStrategiesFor(type, catalog)
          return (
            <label key={type} className="strategy-default-row">
              <span className="strategy-default-label">
                {categoryLabel(type)}
                {recommended && (
                  <small>{recommendedLabel}: {strategyLabel(recommended)}</small>
                )}
              </span>
              <select
                value={defaults[type] ?? recommended ?? 'REDACT'}
                onChange={(event) => onChange(type, event.target.value as TransformationStrategy)}
              >
                {allowed.map((strategy) => (
                  <option key={strategy} value={strategy}>
                    {strategyLabel(strategy)}
                  </option>
                ))}
              </select>
            </label>
          )
        })}
      </div>

      {showOutputFormat && outputFormat && onOutputFormatChange && (
        <>
          <h3>{outputFormatLabel}</h3>
          <div className="options" role="radiogroup" aria-label={outputFormatLabel}>
            <label className={outputFormat === 'TXT' ? 'on' : ''}>
              <input
                type="radio"
                name="format"
                checked={outputFormat === 'TXT'}
                onChange={() => onOutputFormatChange('TXT')}
              />
              {txtLabel}
            </label>
            <label className={outputFormat === 'PDF' ? 'on' : ''}>
              <input
                type="radio"
                name="format"
                checked={outputFormat === 'PDF'}
                onChange={() => onOutputFormatChange('PDF')}
              />
              {pdfLabel}
            </label>
          </div>
        </>
      )}
    </section>
  )
}
