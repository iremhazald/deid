export const DOCUMENT_FONTS = [
  { id: 'times', label: 'Times New Roman', css: '"Times New Roman", Times, serif' },
  { id: 'arial', label: 'Arial', css: 'Arial, Helvetica, sans-serif' },
  { id: 'calibri', label: 'Calibri', css: 'Calibri, "Segoe UI", sans-serif' },
  { id: 'cambria', label: 'Cambria', css: 'Cambria, Georgia, serif' },
  { id: 'georgia', label: 'Georgia', css: 'Georgia, "Times New Roman", serif' },
  { id: 'courier', label: 'Courier New', css: '"Courier New", Courier, monospace' },
] as const

export const DOCUMENT_FONT_SIZES = [8, 9, 10, 11, 12, 14] as const

export const DEFAULT_TEXT_FONT = 'times'
export const DEFAULT_TEXT_SIZE = 11
export const TEXT_AREA_FILL = '#ffffff'
export const TRANSPARENT_FILL = 'transparent'
export const REDACT_BLACK = '#161616'
export const REDACT_WHITE = '#ffffff'
export const REDACT_FILLS = [
  REDACT_BLACK,
  REDACT_WHITE,
  '#1e3a5f',
  '#5c1f1f',
  '#3d3d3d',
] as const
export const TEXT_BACKGROUNDS = [
  TRANSPARENT_FILL,
  TEXT_AREA_FILL,
  '#f4f1ea',
  '#e8e8e8',
  '#dbe4f0',
] as const

export function defaultRedactFill(paper = false) {
  return paper ? REDACT_WHITE : REDACT_BLACK
}

export function redactFillLabelKey(color: string) {
  switch (color) {
    case REDACT_BLACK:
      return 'workspace.fillBlack'
    case REDACT_WHITE:
      return 'workspace.fillWhite'
    case '#1e3a5f':
      return 'workspace.fillNavy'
    case '#5c1f1f':
      return 'workspace.fillBurgundy'
    case '#3d3d3d':
      return 'workspace.fillGray'
    default:
      return 'workspace.fillColor'
  }
}

export type DocumentFontId = (typeof DOCUMENT_FONTS)[number]['id']

export function fontCss(id?: string) {
  return DOCUMENT_FONTS.find((item) => item.id === id)?.css ?? DOCUMENT_FONTS[0].css
}
