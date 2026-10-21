import type { Entity } from "../../state/types";

const DOCKET_LINE =
  /(?:duru[şs]ma\s+tarihi|talimat\s+no|dosya(?:\s*[-–]\s*karar)?(?:\s+no)?|esas\s+no|karar\s+no)/i;

export type TextPart = {
  text: string;
  entity?: Entity;
  paperHeader?: boolean;
};

function lineBounds(text: string, index: number): [number, number] {
  const at = Math.min(Math.max(index, 0), text.length);
  const start = text.lastIndexOf("\n", Math.max(0, at - 1)) + 1;
  const breakAt = text.indexOf("\n", at);
  return [start, breakAt < 0 ? text.length : breakAt];
}

function isHeaderCourt(entity: Entity, text: string): boolean {
  if (entity.attributes?.mask_scope === "header_line") return true;
  if (entity.type !== "COURT_NAME") return false;
  if (entity.start > 500 || entity.text.length > 160) return false;
  const line = (text.slice(0, entity.start).match(/\n/g) ?? []).length;
  if (line > 1) return false;
  const [start, end] = lineBounds(text, entity.start);
  if (end - start > 180) return false;
  return /mahkemes/i.test(entity.text);
}

/** Lines of the top court/docket strip that the PDF paints as white paper. */
export function paperHeaderRanges(text: string, entities: Entity[]): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  for (const entity of entities) {
    if (!isHeaderCourt(entity, text)) continue;
    if (entity.start < 0 || entity.start >= text.length || entity.end <= entity.start) continue;
    let [start] = lineBounds(text, entity.start);
    let end = lineBounds(text, Math.min(entity.end, text.length) - 1)[1];
    if (end < text.length && text[end] === "\n") {
      const nextStart = end + 1;
      const nextEnd = lineBounds(text, nextStart)[1];
      const nextLine = text.slice(nextStart, nextEnd);
      if (nextLine.length > 0 && nextLine.length < 180 && DOCKET_LINE.test(nextLine)) {
        end = nextEnd;
      }
    }
    if (end - start > 400) continue;
    ranges.push([start, end]);
  }
  ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: Array<[number, number]> = [];
  for (const range of ranges) {
    const last = merged[merged.length - 1];
    if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
    else merged.push([...range]);
  }
  return merged;
}

function sliceParts(parts: TextPart[], text: string, from: number, to: number): TextPart[] {
  const out: TextPart[] = [];
  let pos = 0;
  for (const part of parts) {
    const start = pos;
    const end = pos + part.text.length;
    pos = end;
    const cutFrom = Math.max(start, from);
    const cutTo = Math.min(end, to);
    if (cutTo <= cutFrom) continue;
    const entity =
      part.entity && part.entity.start >= cutFrom && part.entity.end <= cutTo
        ? part.entity
        : undefined;
    out.push({
      text: text.slice(cutFrom, cutTo),
      ...(entity ? { entity } : {}),
    });
  }
  return out;
}

/** Preview-only: replace the top court/docket lines with one white paper mask. */
export function applyPaperHeaderMasks(
  parts: TextPart[],
  text: string,
  entities: Entity[],
  viewMode: string,
): TextPart[] {
  if (viewMode !== "preview") return parts;
  const ranges = paperHeaderRanges(text, entities);
  if (!ranges.length) return parts;
  const out: TextPart[] = [];
  let cursor = 0;
  for (const [start, end] of ranges) {
    if (cursor < start) out.push(...sliceParts(parts, text, cursor, start));
    const header = entities.find(
      (entity) => isHeaderCourt(entity, text) && entity.start >= start && entity.start < end,
    );
    out.push({
      text: text.slice(start, end),
      paperHeader: true,
      ...(header ? { entity: header } : {}),
    });
    cursor = end;
  }
  if (cursor < text.length) out.push(...sliceParts(parts, text, cursor, text.length));
  return out.filter((part) => part.text.length > 0);
}
