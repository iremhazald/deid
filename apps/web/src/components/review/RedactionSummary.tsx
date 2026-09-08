type Props = {
  totalLabel: string
  rows: Array<{ label: string; count: number }>
  applyLabel: string
  busy: boolean
  busyLabel: string
  disabled?: boolean
  disabledHint?: string
  onApply: () => void
}

export function RedactionSummary({
  totalLabel,
  rows,
  applyLabel,
  busy,
  busyLabel,
  disabled,
  disabledHint,
  onApply,
}: Props) {
  return (
    <div className="commit">
      <p className="summary-total">{totalLabel}</p>
      {rows.length > 0 && (
        <ul className="summary-rows">
          {rows.map((row) => (
            <li key={row.label}>
              <span>{row.label}</span>
              <span>{row.count}</span>
            </li>
          ))}
        </ul>
      )}
      {disabled && disabledHint && <p className="panel-help">{disabledHint}</p>}
      <button
        type="button"
        className="btn primary"
        disabled={busy || disabled}
        onClick={onApply}
      >
        {busy ? busyLabel : applyLabel}
      </button>
    </div>
  )
}
