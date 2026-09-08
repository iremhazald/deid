import type { Entity, TransformationStrategy } from '../../state/types'
import { detectionSource } from '../../state/helpers'

type Props = {
  entity: Entity
  selected: boolean
  active: boolean
  pageLabel: string
  sourceLabel: string
  strategy: TransformationStrategy
  strategyLabel: (strategy: TransformationStrategy) => string
  allowedStrategies: TransformationStrategy[]
  showStrategy: boolean
  onSelect: () => void
  onToggle: (checked: boolean) => void
  onStrategyChange: (strategy: TransformationStrategy) => void
}

export function EntityRow({
  entity,
  selected,
  active,
  pageLabel,
  sourceLabel,
  strategy,
  strategyLabel,
  allowedStrategies,
  showStrategy,
  onSelect,
  onToggle,
  onStrategyChange,
}: Props) {
  const source = detectionSource(entity)
  const occurrenceNote = entity.occurrence_count && entity.occurrence_count > 1
    ? ` (${entity.occurrence_count} yer)`
    : ''
  const meta = [entity.role, `${pageLabel} ${entity.page + 1}`].filter(Boolean).join(' · ')

  return (
    <li className={`entity-row${active ? ' on' : ''}`} id={`entity-row-${entity.id}`}>
      <label className="entity-check">
        <input
          type="checkbox"
          checked={selected}
          onChange={(event) => onToggle(event.target.checked)}
          aria-label={entity.text}
        />
      </label>
      <button type="button" className="entity-main" onClick={onSelect}>
        <strong>{entity.text}{occurrenceNote}</strong>
        <span>
          <em className={`source-badge ${source}`}>{sourceLabel}</em>
          {meta ? ` · ${meta}` : ''}
        </span>
      </button>
  {selected && showStrategy && (
        <div className="entity-strategy-wrap">
          <select
            className="entity-strategy"
            value={strategy}
            onChange={(event) => onStrategyChange(event.target.value as TransformationStrategy)}
            aria-label={strategyLabel(strategy)}
          >
            {allowedStrategies.map((item) => (
              <option key={item} value={item}>{strategyLabel(item)}</option>
            ))}
          </select>

        </div>
      )}
    </li>
  )
}
