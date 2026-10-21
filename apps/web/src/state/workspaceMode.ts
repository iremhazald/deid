export type WorkspaceMode = 'DOCUMENT' | 'TEXT'
export type SourceDocumentType = 'PDF' | 'DOCX' | 'UDF'

/** Only a PDF asks the user to choose a workspace. DOCX and UYAP UDF are text. */
export function asksWorkspaceMode(fileName?: string | null): boolean {
  return Boolean(fileName && fileName.toLowerCase().endsWith('.pdf'))
}

export function workspaceModeForSelectedFile(
  fileName: string,
  choice: WorkspaceMode | null,
): WorkspaceMode | null {
  const name = fileName.toLowerCase()
  if (name.endsWith('.docx') || name.endsWith('.udf')) return 'TEXT'
  return choice
}

/** PDF page viewer is the V1 path. Omitted mode stays on that path. */
export function showsPdfPageViewer(
  documentKind?: string | null,
  workspaceMode?: string | null,
): boolean {
  if (workspaceMode === 'TEXT') return false
  return documentKind === 'PDF'
}

/**
 * Resolve a manual text selection against the immutable source string.
 * A candidate from the DOM is used only when it still matches that string.
 * Duplicate phrases without a matching candidate are left unresolved.
 */
export function offsetsForSelectedSource(
  sourceText: string,
  selected: string,
  candidateStart: number | null,
): { start: number; end: number } | null {
  if (!selected) return null
  if (
    candidateStart != null
    && candidateStart >= 0
    && sourceText.slice(candidateStart, candidateStart + selected.length) === selected
  ) {
    return { start: candidateStart, end: candidateStart + selected.length }
  }
  const first = sourceText.indexOf(selected)
  if (first < 0) return null
  if (sourceText.indexOf(selected, first + 1) >= 0) return null
  return { start: first, end: first + selected.length }
}
