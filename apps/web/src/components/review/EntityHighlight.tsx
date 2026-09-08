import type { DecisionAction, TransformationStrategy } from '../../state/types'

// Map entity type → human-readable label (Turkish default, overridden via data-label)
type Props = {
  text: string
  accent: string
  selected: boolean
  entityId: string
  entityType?: string
  action?: DecisionAction
  strategy?: TransformationStrategy
  manual?: boolean
  onSelect: () => void
}

/** Strategy display icons used in the tooltip. */
const STRATEGY_ICONS: Partial<Record<TransformationStrategy, string>> = {
  REDACT: '⬛',
  PLACEHOLDER: '🏷',
  INITIALS: 'İ.',
  PARTIAL_MASK: '***',
}

export function EntityHighlight({
  text,
  accent,
  selected,
  entityId,
  entityType,
  action,
  strategy,
  manual,
  onSelect,
}: Props) {
  // Build tooltip string
  let tooltip: string | undefined
  if (entityType) {
    const stratIcon = strategy ? (STRATEGY_ICONS[strategy] ?? strategy) : ''
    const actionLabel = action === 'KEEP' ? '✓ Korunacak' : `🔒 Gizlenecek ${stratIcon}`.trim()
    tooltip = `${entityType}  ·  ${actionLabel}`
  }

  return (
    <span className="entity-mark-wrapper">
      <mark
        id={`entity-${entityId}`}
        className={`entity-mark ${accent}${selected ? ' on' : ''}${manual ? ' manual' : ''}${action === 'KEEP' ? ' keep' : ''}`}
        tabIndex={0}
        role="button"
        onClick={onSelect}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onSelect()
          }
        }}
      >
        {text}
      </mark>
      {tooltip && (
        <span className="entity-tooltip" aria-hidden="true">
          {tooltip}
        </span>
      )}
    </span>
  )
}
