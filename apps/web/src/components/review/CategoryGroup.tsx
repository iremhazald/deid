import type { DecisionAction, Entity, TransformationStrategy } from '../../state/types'
import { EntityRow } from './EntityRow'

type Props = {
  type: string
  title: string
  entities: Entity[]
  decisions: Record<string, DecisionAction>
  strategies: Record<string, TransformationStrategy>
  categoryDefault: TransformationStrategy
  allowedStrategies: TransformationStrategy[]
  activeId: string | null
  open: boolean
  selectedLabel: string
  redactAllLabel: string
  keepAllLabel: string
  pageLabel: string
  sourceLabel: (entity: Entity) => string
  strategyLabel: (strategy: TransformationStrategy) => string
  onToggleOpen: () => void
  onSelect: (id: string) => void
  onDecision: (id: string, action: DecisionAction) => void
  onBulk: (action: DecisionAction) => void
  onEntityStrategy: (id: string, strategy: TransformationStrategy) => void
}

export function CategoryGroup({
  title,
  entities,
  decisions,
  strategies,
  categoryDefault,
  allowedStrategies,
  activeId,
  open,
  selectedLabel,
  redactAllLabel,
  keepAllLabel,
  pageLabel,
  sourceLabel,
  strategyLabel,
  onToggleOpen,
  onSelect,
  onDecision,
  onBulk,
  onEntityStrategy,
}: Props) {
  return (
    <section className={`category-group${open ? ' open' : ''}`}>
      <button type="button" className="category-head" onClick={onToggleOpen} aria-expanded={open}>
        <span className="category-chevron" aria-hidden="true">{open ? '▾' : '▸'}</span>
        <span className="category-title">{title}</span>
        <span className="category-count">{entities.length}</span>
      </button>
      {open && (
        <div className="category-body">
          <div className="category-meta">
            <span>{selectedLabel}</span>
            <div className="bulk">
              <button type="button" onClick={() => onBulk('REDACT')}>{redactAllLabel}</button>
              <button type="button" onClick={() => onBulk('KEEP')}>{keepAllLabel}</button>
            </div>
          </div>
          <ul>
            {entities.map((entity) => (
              <EntityRow
                key={entity.id}
                entity={entity}
                selected={decisions[entity.id] === 'REDACT'}
                active={activeId === entity.id}
                pageLabel={pageLabel}
                sourceLabel={sourceLabel(entity)}
                strategy={strategies[entity.id] ?? categoryDefault}
                strategyLabel={strategyLabel}
                allowedStrategies={allowedStrategies}
                showStrategy={decisions[entity.id] === 'REDACT'}
                onSelect={() => onSelect(entity.id)}
                onToggle={(checked) => onDecision(entity.id, checked ? 'REDACT' : 'KEEP')}
                onStrategyChange={(strategy) => onEntityStrategy(entity.id, strategy)}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
