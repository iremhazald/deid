import type { OutputFormat, RedactionMethod } from '../../state/types'

type Props = {
  methodLabel: string
  maskLabel: string
  labelLabel: string
  method: RedactionMethod
  onMethodChange: (value: RedactionMethod) => void
  preview?: string
  showOutputFormat?: boolean
  outputFormatLabel?: string
  txtLabel?: string
  pdfLabel?: string
  outputFormat?: OutputFormat
  onOutputFormatChange?: (value: OutputFormat) => void
}

export function RedactionSettings({
  methodLabel,
  maskLabel,
  labelLabel,
  method,
  onMethodChange,
  preview,
  showOutputFormat,
  outputFormatLabel,
  txtLabel,
  pdfLabel,
  outputFormat,
  onOutputFormatChange,
}: Props) {
  return (
    <section className="settings-block">
      <h3>{methodLabel}</h3>
      <div className="options" role="radiogroup" aria-label={methodLabel}>
        <label className={method === 'MASK' ? 'on' : ''}>
          <input
            type="radio"
            name="method"
            checked={method === 'MASK'}
            onChange={() => onMethodChange('MASK')}
          />
          {maskLabel}
        </label>
        <label className={method === 'LABEL' ? 'on' : ''}>
          <input
            type="radio"
            name="method"
            checked={method === 'LABEL'}
            onChange={() => onMethodChange('LABEL')}
          />
          {labelLabel}
        </label>
      </div>
      {method === 'LABEL' && preview && <p className="method-preview mono">{preview}</p>}

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
