import { useEffect, useId, useRef, useState } from 'react'
import { outputStrategyLabelKey } from '../../state/helpers'
import {
  clampMenuPosition,
  findingContextMenuItems,
  shouldCloseFindingContextMenu,
} from '../../state/findingContextMenu'
import type { Entity, TransformCatalog, TransformationStrategy } from '../../state/types'

type Props = {
  entity: Entity
  catalog: TransformCatalog | null
  currentStrategy: TransformationStrategy
  x: number
  y: number
  t: (key: string, options?: Record<string, unknown>) => string
  onStrategy: (strategy: TransformationStrategy) => void
  onMerge?: () => void
  onRemove: () => void
  onClose: () => void
}

export function FindingContextMenu({
  entity,
  catalog,
  currentStrategy,
  x,
  y,
  t,
  onStrategy,
  onMerge,
  onRemove,
  onClose,
}: Props) {
  const items = findingContextMenuItems(entity, catalog)
  const rootRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ left: x, top: y })
  const labelId = useId()
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    rootRef.current?.focus()
  }, [])

  useEffect(() => {
    const node = rootRef.current
    if (!node) return
    const box = node.getBoundingClientRect()
    setPos(
      clampMenuPosition(
        x,
        y,
        box.width || 220,
        box.height || 160,
        window.innerWidth,
        window.innerHeight,
      ),
    )
  }, [x, y, items.length])

  useEffect(() => {
    const onPointer = (event: PointerEvent) => {
      const inside = Boolean(rootRef.current?.contains(event.target as Node))
      if (shouldCloseFindingContextMenu({ type: 'pointerdown', insideMenu: inside })) {
        onClose()
      }
    }
    const onKey = (event: KeyboardEvent) => {
      if (shouldCloseFindingContextMenu({ key: event.key })) {
        event.preventDefault()
        onClose()
      }
    }
    document.addEventListener('pointerdown', onPointer, true)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer, true)
      document.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  const run = (index: number) => {
    const item = items[index]
    if (!item) return
    if (item.kind === 'strategy') onStrategy(item.strategy)
    else if (item.kind === 'merge') onMerge?.()
    else onRemove()
  }

  return (
    <div
      ref={rootRef}
      className="finding-context-menu"
      role="menu"
      tabIndex={-1}
      aria-labelledby={labelId}
      style={{ left: pos.left, top: pos.top }}
      onContextMenu={(event) => event.preventDefault()}
      onKeyDown={(event) => {
        if (event.key === 'ArrowDown') {
          event.preventDefault()
          setActiveIndex((current) => (current + 1) % items.length)
        } else if (event.key === 'ArrowUp') {
          event.preventDefault()
          setActiveIndex((current) => (current - 1 + items.length) % items.length)
        } else if (event.key === 'Home') {
          event.preventDefault()
          setActiveIndex(0)
        } else if (event.key === 'End') {
          event.preventDefault()
          setActiveIndex(items.length - 1)
        } else if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          run(activeIndex)
        }
      }}
    >
      <div className="finding-context-head" id={labelId}>
        <span>{t(`categories.${entity.type}`, { defaultValue: entity.type })}</span>
        <strong>{entity.text}</strong>
      </div>
      <div className="finding-context-methods">
        {items
          .map((item, index) => ({ item, index }))
          .filter(({ item }) => item.kind === 'strategy')
          .map(({ item, index }) => {
            if (item.kind !== 'strategy') return null
            const selected = item.strategy === currentStrategy
            return (
              <button
                key={item.strategy}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
                className={`${selected ? 'on' : ''}${index === activeIndex ? ' is-active' : ''}`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => run(index)}
              >
                <span className="finding-context-bullet" aria-hidden="true">
                  {selected ? '●' : ''}
                </span>
                {t(outputStrategyLabelKey(item.strategy))}
              </button>
            )
          })}
      </div>
      <div className="finding-context-sep" role="separator" />
      {items
        .map((item, index) => ({ item, index }))
        .filter(({ item }) => item.kind !== 'strategy')
        .map(({ item, index }) => (
          <button
            key={item.kind}
            type="button"
            role="menuitem"
            className={`finding-context-${item.kind}${index === activeIndex ? ' is-active' : ''}`}
            onMouseEnter={() => setActiveIndex(index)}
            onClick={() => run(index)}
          >
            {item.kind === 'merge'
              ? t('workspace.contextMergePerson')
              : t('workspace.contextRemoveFinding')}
          </button>
        ))}
    </div>
  )
}
