import { useEffect, useId, useMemo, useState } from 'react'
import {
  buildManualMergeTargets,
  mergeEntityIdsForEngine,
  personMergeRoleConflict,
  type ManualMergeTarget,
} from '../../state/manualMerge'
import type { Entity, PossibleMatch } from '../../state/types'

type Props = {
  sourceEntity: Entity
  entities: Entity[]
  possibleMatches?: PossibleMatch[]
  t: (key: string, options?: Record<string, unknown>) => string
  onMerge: (entityIds: string[]) => void | Promise<void>
  onCancel: () => void
  notice?: string | null
}

export function ManualMergePanel({
  sourceEntity,
  entities,
  possibleMatches = [],
  t,
  onMerge,
  onCancel,
  notice = null,
}: Props) {
  const [query, setQuery] = useState('')
  const searchId = useId()
  const { source, possible, others } = useMemo(
    () => buildManualMergeTargets(sourceEntity, entities, possibleMatches, query),
    [sourceEntity, entities, possibleMatches, query],
  )

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      const target = event.target as HTMLElement | null
      if (target?.matches('input, textarea')) {
        if (query) {
          event.stopPropagation()
          setQuery('')
          return
        }
      }
      onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, query])

  const selectTarget = (target: ManualMergeTarget) => {
    void onMerge(mergeEntityIdsForEngine(sourceEntity, target))
  }

  return (
    <div className="manual-merge-panel" data-testid="manual-merge-panel">
      <header className="manual-merge-head">
        <h2>{t('workspace.manualMergeTitle')}</h2>
        {source && (
          <p className="manual-merge-source">
            <strong>{source.displayName}</strong>
            {source.placeholderToken ? <span>{source.placeholderToken}</span> : null}
          </p>
        )}
      </header>
      <p className="manual-merge-lead">{t('workspace.manualMergeSelect')}</p>
      <label className="manual-merge-search" htmlFor={searchId}>
        <span className="visually-hidden">{t('workspace.manualMergeSearch')}</span>
        <input
          id={searchId}
          type="search"
          value={query}
          placeholder={t('workspace.manualMergeSearch')}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {notice ? <p className="manual-merge-notice">{notice}</p> : null}
      {possible.length > 0 && (
        <section className="manual-merge-group">
          <h3>{t('workspace.manualMergePossible')}</h3>
          <TargetList targets={possible} t={t} onSelect={selectTarget} />
        </section>
      )}
      {others.length > 0 && (
        <section className="manual-merge-group">
          <h3>{t('workspace.manualMergeOthers')}</h3>
          <TargetList targets={others} t={t} onSelect={selectTarget} />
        </section>
      )}
      {possible.length === 0 && others.length === 0 && (
        <p className="review-panel-empty">{t('workspace.manualMergeEmpty')}</p>
      )}
      <div className="manual-merge-actions">
        <button type="button" className="manual-merge-cancel" onClick={onCancel}>
          {t('workspace.manualMergeCancel')}
        </button>
      </div>
    </div>
  )
}

function TargetList({
  targets,
  t,
  onSelect,
}: {
  targets: ManualMergeTarget[]
  t: (key: string, options?: Record<string, unknown>) => string
  onSelect: (target: ManualMergeTarget) => void
}) {
  return (
    <ul className="manual-merge-targets">
      {targets.map((target) => (
        <li key={target.canonicalId}>
          <button type="button" onClick={() => onSelect(target)}>
            <span className="manual-merge-name">
              <strong>{target.displayName}</strong>
              {target.placeholderToken ? <em>{target.placeholderToken}</em> : null}
            </span>
            {target.occurrenceCount > 1 ? (
              <span className="manual-merge-count">
                {t('workspace.occurrenceCount', { count: target.occurrenceCount })}
              </span>
            ) : null}
          </button>
        </li>
      ))}
    </ul>
  )
}

export function mergeConflictNotice(
  source: Entity,
  target: ManualMergeTarget,
  t: (key: string, options?: Record<string, unknown>) => string,
): string | null {
  if (!personMergeRoleConflict([source.type], target.types)) return null
  return t('workspace.manualMergeRoleConflict')
}
