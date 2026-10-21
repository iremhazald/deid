import type { CSSProperties } from "react";

/** Document face for Text Workspace pages. Application chrome stays on the sans stack. */
export const TEXT_WORKSPACE_FONT_FAMILY = '"Times New Roman", Times, serif';
export const TEXT_WORKSPACE_FONT_SIZE = "12pt";

export const textWorkspaceCanvasStyle: CSSProperties = {
  boxSizing: "border-box",
  minHeight: "100%",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: "48px",
  padding: "32px 16px 56px",
  background: "#e6e6e6",
  position: "relative",
};

export const textDocumentPageStyle: CSSProperties = {
  boxSizing: "border-box",
  flex: "0 0 auto",
  width: "min(210mm, 100%)",
  maxWidth: "210mm",
  minHeight: "297mm",
  margin: 0,
  padding: "25mm 22mm",
  background: "#ffffff",
  color: "#111111",
  border: "1px solid rgba(0, 0, 0, 0.12)",
  borderRadius: "2px",
  boxShadow:
    "0 1px 2px rgba(0, 0, 0, 0.06), 0 8px 18px rgba(0, 0, 0, 0.12)",
  fontFamily: TEXT_WORKSPACE_FONT_FAMILY,
  fontSize: TEXT_WORKSPACE_FONT_SIZE,
  fontWeight: 400,
  lineHeight: 1.5,
  textAlign: "left",
  whiteSpace: "pre-wrap",
  overflowWrap: "break-word",
  wordBreak: "normal",
  tabSize: 8,
  hyphens: "manual",
  userSelect: "text",
};

/** Finding marks must not collapse the source whitespace they sit inside. */
export const textDocumentEntityStyle: CSSProperties = {
  display: "inline",
  whiteSpace: "pre-wrap",
  margin: 0,
  padding: 0,
  textAlign: "left",
  verticalAlign: "baseline",
  overflowWrap: "break-word",
  userSelect: "text",
};

/**
 * PDF TEXT pages, only when the slices reconstruct analysis text exactly.
 * DOCX and UYAP UDF stay one surface: their extractors do not provide source pages.
 */
export function pdfSourcePageTexts(
  documentKind: string | null | undefined,
  text: string,
  pageTexts?: readonly string[] | null,
): readonly string[] | null {
  if (documentKind !== "PDF") return null;
  if (!pageTexts || pageTexts.length < 2) return null;
  let combined = "";
  for (const page of pageTexts) combined += page;
  if (combined !== text) return null;
  return pageTexts;
}

export function textPageBoundaries(
  text: string,
  pages: readonly string[] | null,
): number[] {
  if (!pages) return [0, text.length];
  const boundaries = [0];
  for (const page of pages) {
    boundaries.push(boundaries[boundaries.length - 1] + page.length);
  }
  return boundaries;
}

export function pageIndexAt(boundaries: readonly number[], offset: number): number {
  const last = Math.max(0, boundaries.length - 2);
  let index = 0;
  while (index < last && offset >= boundaries[index + 1]) index += 1;
  return index;
}

export type PdfTextRun = {
  start: number;
  end: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  size: number;
  bold?: boolean;
};

/** Span boxes mapped onto one page of analysis text. Offsets are page-local. */
export type PdfTextLayout = {
  page: number;
  width: number;
  height: number;
  runs: PdfTextRun[];
};

export function usablePdfTextLayout(
  documentKind: string | null | undefined,
  pageText: string,
  layout: PdfTextLayout | null | undefined,
): PdfTextLayout | null {
  if (documentKind !== "PDF" || !layout) return null;
  if (!(layout.width > 0) || !(layout.height > 0) || layout.runs.length === 0) return null;
  let cursor = 0;
  for (const run of layout.runs) {
    if (run.start < cursor || run.end > pageText.length || run.start >= run.end) return null;
    cursor = run.end;
  }
  return layout;
}

export const textFlowPageStyle: CSSProperties = {
  ...textDocumentPageStyle,
  position: "relative",
  whiteSpace: "normal",
};

export type FlowPiece = {
  text: string;
  localStart: number;
  localEnd: number;
  kind: "text" | "join" | "break";
};

/** One visual line. Characters stay in source order; boxes are not reused. */
export type FlowTextLine = {
  align: "left" | "center" | "form" | "blank";
  pieces: FlowPiece[];
  valueFrom: number;
};

function flowPiece(text: string, start: number, kind: FlowPiece["kind"]): FlowPiece {
  return { text, localStart: start, localEnd: start + text.length, kind };
}

function sameBaseline(a: PdfTextRun, b: PdfTextRun): boolean {
  const size = Math.min(a.size || 12, b.size || 12);
  return Math.abs(a.y0 - b.y0) <= Math.max(3, size * 0.45);
}

function splitAfterLine(gap: string, start: number): {
  separator: FlowPiece | null;
  blanks: FlowTextLine[];
  prefix: FlowPiece | null;
} {
  if (!gap) return { separator: null, blanks: [], prefix: null };
  if (!/^\s*$/.test(gap)) {
    return {
      separator: null,
      blanks: [{ align: "left", valueFrom: 0, pieces: [flowPiece(gap, start, "text")] }],
      prefix: null,
    };
  }
  const newlineAt = gap.indexOf("\n");
  if (newlineAt < 0) {
    return { separator: null, blanks: [], prefix: flowPiece(gap, start, "join") };
  }
  const separator = flowPiece(gap.slice(0, newlineAt + 1), start, "break");
  const blanks: FlowTextLine[] = [];
  let cursor = newlineAt + 1;
  while (cursor < gap.length) {
    const next = gap.indexOf("\n", cursor);
    if (next < 0) break;
    blanks.push({
      align: "blank",
      valueFrom: 0,
      pieces: [flowPiece(gap.slice(cursor, next + 1), start + cursor, "break")],
    });
    cursor = next + 1;
  }
  const prefix = cursor < gap.length ? flowPiece(gap.slice(cursor), start + cursor, "join") : null;
  return { separator, blanks, prefix };
}

function splitLeading(gap: string, start: number): {
  blanks: FlowTextLine[];
  prefix: FlowPiece | null;
} {
  if (!gap) return { blanks: [], prefix: null };
  if (!/^\s*$/.test(gap)) {
    return {
      blanks: [{ align: "left", valueFrom: 0, pieces: [flowPiece(gap, start, "text")] }],
      prefix: null,
    };
  }
  const blanks: FlowTextLine[] = [];
  let cursor = 0;
  while (cursor < gap.length) {
    const next = gap.indexOf("\n", cursor);
    if (next < 0) break;
    blanks.push({
      align: "blank",
      valueFrom: 0,
      pieces: [flowPiece(gap.slice(cursor, next + 1), start + cursor, "break")],
    });
    cursor = next + 1;
  }
  const prefix = cursor < gap.length ? flowPiece(gap.slice(cursor), start + cursor, "join") : null;
  return { blanks, prefix };
}

function isCentered(runs: readonly PdfTextRun[], width: number): boolean {
  const left = Math.min(...runs.map((run) => run.x0));
  const right = Math.max(...runs.map((run) => run.x1));
  if (right - left > width * 0.72) return false;
  const marginLeft = left;
  const marginRight = width - right;
  return marginLeft > width * 0.18 && marginRight > width * 0.12 && marginLeft > marginRight * 0.45;
}

function isFormLine(pageText: string, runs: readonly PdfTextRun[], width: number): boolean {
  if (runs.length < 2) return false;
  const first = runs[0];
  const second = runs[1];
  if (!first || !second) return false;
  const label = pageText.slice(first.start, first.end).trim();
  const value = pageText.slice(second.start, second.end).trim();
  if (!label || label.length > 36) return false;
  if (first.x0 > width * 0.22) return false;
  if (second.x0 - first.x1 < 16) return false;
  return value.startsWith(":") || value.startsWith("：");
}

function classifyLine(
  pageText: string,
  layout: PdfTextLayout,
  pieces: FlowPiece[],
  runs: readonly PdfTextRun[],
): FlowTextLine {
  const centered = isCentered(runs, layout.width);
  const form = !centered && isFormLine(pageText, runs, layout.width);
  const second = runs[1];
  const valueIndex = form && second
    ? pieces.findIndex((item) => item.localStart >= second.start)
    : 0;
  return {
    align: centered ? "center" : form ? "form" : "left",
    pieces,
    valueFrom: valueIndex > 0 ? valueIndex : 0,
  };
}

/**
 * Group PDF spans that share a baseline into one reading line.
 * The joined characters are still the extractor text, in the same order.
 * A shorter label then occupies only its own width.
 */
export function flowTextLines(pageText: string, layout: PdfTextLayout): FlowTextLine[] {
  const lines: FlowTextLine[] = [];
  let pieces: FlowPiece[] = [];
  let runs: PdfTextRun[] = [];

  const finish = (separator: FlowPiece | null) => {
    if (separator) pieces.push(separator);
    if (pieces.some((item) => item.kind === "text")) {
      lines.push(classifyLine(pageText, layout, pieces, runs));
    } else {
      for (const item of pieces) {
        lines.push({ align: "blank", valueFrom: 0, pieces: [item] });
      }
    }
    pieces = [];
    runs = [];
  };

  let cursor = 0;
  for (const run of layout.runs) {
    const gap = pageText.slice(cursor, run.start);
    const previous = runs[runs.length - 1];
    if (previous && sameBaseline(previous, run) && /^\s*$/.test(gap)) {
      if (gap) pieces.push(flowPiece(gap, cursor, "join"));
    } else if (previous) {
      const split = splitAfterLine(gap, cursor);
      finish(split.separator);
      lines.push(...split.blanks);
      if (split.prefix) pieces.push(split.prefix);
    } else {
      const split = splitLeading(gap, cursor);
      lines.push(...split.blanks);
      if (split.prefix) pieces.push(split.prefix);
    }
    pieces.push(flowPiece(pageText.slice(run.start, run.end), run.start, "text"));
    runs.push(run);
    cursor = run.end;
  }
  const tail = splitAfterLine(pageText.slice(cursor), cursor);
  finish(tail.separator);
  lines.push(...tail.blanks);
  if (tail.prefix) {
    lines.push({ align: "left", valueFrom: 0, pieces: [tail.prefix] });
  }
  return lines;
}
