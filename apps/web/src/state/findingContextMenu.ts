import { userOutputStrategiesFor } from './helpers'
import type {
  Analysis,
  DocumentViewMode,
  EditorTool,
  Entity,
  PossibleMatch,
  TransformCatalog,
  TransformationStrategy,
} from './types'

/** Document context menu lives on the preview canvas only; it must not pan/zoom the page. */
export function shouldOpenDocumentContextMenu(
  viewMode: DocumentViewMode,
  tool: EditorTool = 'select',
): boolean {
  return viewMode === 'preview' && tool === 'select'
}

/** Person/legal-role families supported by the human-in-the-loop merge system. */
export const PERSON_MERGE_TYPES = new Set([
  'PERSON_NAME',
  'FIRST_NAME',
  'LAST_NAME',
  'ALIAS',
  'CLAIMANT_NAME',
  'DEFENDANT_NAME',
  'LAWYER_NAME',
  'JUDGE_NAME',
  'WITNESS_NAME',
  'EXPERT_NAME',
])

export function isPersonMergeType(type: string): boolean {
  return PERSON_MERGE_TYPES.has(type)
}

export function isAddressMergeType(type: string): boolean {
  return type === 'ADDRESS'
}

export function isMergeType(type: string): boolean {
  return isPersonMergeType(type) || isAddressMergeType(type)
}

/** Context-menu methods from the catalog, excluding KEEP. */
export function contextMenuStrategies(
  type: string,
  catalog: TransformCatalog | null,
): TransformationStrategy[] {
  return userOutputStrategiesFor(type, catalog).filter((strategy) => strategy !== 'KEEP')
}

export type FindingContextMenuItem =
  | { kind: 'strategy'; strategy: TransformationStrategy }
  | { kind: 'merge' }
  | { kind: 'remove' }

export function findingContextMenuItems(
  entity: Entity,
  catalog: TransformCatalog | null,
): FindingContextMenuItem[] {
  const items: FindingContextMenuItem[] = contextMenuStrategies(entity.type, catalog).map(
    (strategy) => ({ kind: 'strategy' as const, strategy }),
  )
  if (isMergeType(entity.type)) items.push({ kind: 'merge' })
  items.push({ kind: 'remove' })
  return items
}

export function contextMenuShowsKeep(items: FindingContextMenuItem[]): boolean {
  return items.some((item) => item.kind === 'strategy' && item.strategy === 'KEEP')
}

export function contextMenuShowsEdit(_items: FindingContextMenuItem[]): boolean {
  return false
}

/** Right-click always activates that occurrence, even if another finding was selected. */
export function selectFindingOnContextClick(_activeId: string | null, clickedId: string): string {
  return clickedId
}

export function shouldCloseFindingContextMenu(event: {
  key?: string
  type?: string
  insideMenu?: boolean
}): boolean {
  if (event.key === 'Escape') return true
  if (event.type === 'pointerdown' && !event.insideMenu) return true
  return false
}

export function clampMenuPosition(
  x: number,
  y: number,
  width: number,
  height: number,
  viewportWidth: number,
  viewportHeight: number,
  margin = 8,
): { left: number; top: number } {
  const maxLeft = Math.max(margin, viewportWidth - width - margin)
  const maxTop = Math.max(margin, viewportHeight - height - margin)
  return {
    left: Math.min(Math.max(margin, x), maxLeft),
    top: Math.min(Math.max(margin, y), maxTop),
  }
}

export function withoutRemovedFindings(entities: Entity[], removedIds: Iterable<string>): Entity[] {
  const removed = removedIds instanceof Set ? removedIds : new Set(removedIds)
  if (removed.size === 0) return entities
  return entities.filter((entity) => !removed.has(entity.id))
}

export function prunePossibleMatches(
  matches: PossibleMatch[],
  entities: Entity[],
): PossibleMatch[] {
  const ids = new Set(entities.map((entity) => entity.id))
  return matches
    .map((match) => ({
      ...match,
      members: match.members
        .map((member) => ({
          ...member,
          entity_ids: member.entity_ids.filter((id) => ids.has(id)),
        }))
        .filter((member) => member.entity_ids.length > 0),
    }))
    .filter((match) => match.members.length >= 2)
}

export function analysisWithoutRemovedFindings(
  analysis: Analysis,
  removedIds: Iterable<string>,
): Analysis {
  const entities = withoutRemovedFindings(analysis.entities, removedIds)
  if (entities.length === analysis.entities.length) return analysis
  return {
    ...analysis,
    entities,
    possible_matches: prunePossibleMatches(analysis.possible_matches ?? [], entities),
  }
}
