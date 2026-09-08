import { useEffect, useRef, useState, type PointerEvent } from "react";
import {
  fetchJobSpans,
  getPageImageUrl,
  type PdfPageSpans,
} from "../../api/client";
import {
  categoryAccent,
  COURT_ORDINAL_TAG,
  effectiveStrategy,
  initialsPointSize,
  manualItemId,
  previewEntityValue,
  showDetectionOverlay,
  usesPaperRedaction,
} from "../../state/helpers";
import type {
  CategoryDefaults,
  Decisions,
  DocumentViewMode,
  EditorTool,
  Entity,
  EntityStrategies,
  ManualRedaction,
} from "../../state/types";
import { DEFAULT_TEXT_SIZE, TRANSPARENT_FILL, defaultRedactFill, fontCss } from "./documentFonts";
import {
  applyOverlayResize,
  replaceOverlayRect,
  RESIZE_EDGES,
  type ResizeEdge,
} from "./overlayResize";
import {
  isElementVisibleInCanvas,
  pageInViewFromRects,
  scrollElementIntoCanvas,
} from "./overlayScroll";
import { shouldOpenDocumentContextMenu } from "../../state/findingContextMenu";

const PAGE_SCALE = 1.5;
const PAGE_HYDRATE_RADIUS = 2;

export function hydratePdfPageIndexes(
  currentPage: number,
  pageCount: number,
  radius = PAGE_HYDRATE_RADIUS,
): number[] {
  const visible = Math.max(0, currentPage - 1);
  const pages: number[] = [];
  for (let index = visible - radius; index <= visible + radius; index += 1) {
    if (index >= 0 && index < pageCount) pages.push(index);
  }
  return pages;
}

type OverlayBox = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
};

function boxArea(box: OverlayBox) {
  return Math.max(0, box.x1 - box.x0) * Math.max(0, box.y1 - box.y0);
}

function boxContained(inner: OverlayBox, outer: OverlayBox, pad = 3) {
  return (
    inner.x0 >= outer.x0 - pad &&
    inner.y0 >= outer.y0 - pad &&
    inner.x1 <= outer.x1 + pad &&
    inner.y1 <= outer.y1 + pad
  );
}

export function boxesOverlap(a: OverlayBox, b: OverlayBox, pad = 0.5) {
  return (
    a.x0 < b.x1 + pad &&
    a.x1 > b.x0 - pad &&
    a.y0 < b.y1 + pad &&
    a.y1 > b.y0 - pad
  );
}

export function pointInBox(x: number, y: number, box: OverlayBox) {
  return x >= box.x0 && x <= box.x1 && y >= box.y0 && y <= box.y1;
}

function sameIdSet(left: Set<string>, right: Set<string>) {
  if (left.size !== right.size) return false;
  for (const id of left) {
    if (!right.has(id)) return false;
  }
  return true;
}

/** Peek every overlay under the pointer, plus any box that shares pixels with it. */
export function peekOverlayIds(
  items: Array<{ id: string; rect: OverlayBox }>,
  x: number,
  y: number,
): string[] {
  const hits = items.filter((item) => pointInBox(x, y, item.rect));
  if (!hits.length) return [];
  const ids = new Set(hits.map((item) => item.id));
  for (const item of items) {
    if (ids.has(item.id)) continue;
    if (hits.some((hit) => boxesOverlap(hit.rect, item.rect))) {
      ids.add(item.id);
    }
  }
  return [...ids];
}

/** Join word-level PDF hits on the same visual line into one outline. */
function mergeLineRects(rects: OverlayBox[]): OverlayBox[] {
  if (rects.length <= 1) return rects.map((rect) => ({ ...rect }));
  const sorted = [...rects].sort(
    (left, right) => left.y0 - right.y0 || left.x0 - right.x0,
  );
  const merged: OverlayBox[] = [];
  for (const rect of sorted) {
    const last = merged[merged.length - 1];
    if (!last) {
      merged.push({ ...rect });
      continue;
    }
    const lastMid = (last.y0 + last.y1) / 2;
    const rectMid = (rect.y0 + rect.y1) / 2;
    const tol = Math.max(
      5,
      Math.max(last.y1 - last.y0, rect.y1 - rect.y0) * 0.7,
    );
    const sameLine = Math.abs(rectMid - lastMid) <= tol;
    const close = rect.x0 <= last.x1 + 28;
    if (sameLine && close) {
      last.x0 = Math.min(last.x0, rect.x0);
      last.y0 = Math.min(last.y0, rect.y0);
      last.x1 = Math.max(last.x1, rect.x1);
      last.y1 = Math.max(last.y1, rect.y1);
    } else {
      merged.push({ ...rect });
    }
  }
  return merged;
}

function unionBoxes(rects: OverlayBox[]): OverlayBox {
  return {
    x0: Math.min(...rects.map((rect) => rect.x0)),
    y0: Math.min(...rects.map((rect) => rect.y0)),
    x1: Math.max(...rects.map((rect) => rect.x1)),
    y1: Math.max(...rects.map((rect) => rect.y1)),
  };
}

function clipBox(box: OverlayBox, width: number, height: number): OverlayBox {
  return {
    x0: Math.max(0, box.x0),
    y0: Math.max(0, box.y0),
    x1: Math.min(width, box.x1),
    y1: Math.min(height, box.y1),
  };
}

const MARKS_ABOVE = "İĞÖÜÔŐŰÄËŶÂÎÛíğöüôőűäëŷâîû";
const MARKS_BELOW = "ÇŞçş";
const BREVE_ABOVE = "ĞğĜĝ";

export function hasBreveMark(text: string): boolean {
  if ([...text].some((char) => BREVE_ABOVE.includes(char))) return true;
  return text.normalize("NFD").includes("\u0306");
}

export function clipCoverToNeighbors(
  cover: OverlayBox,
  origin: OverlayBox,
  neighbors: OverlayBox[],
): OverlayBox {
  let y0 = cover.y0;
  let y1 = cover.y1;
  const center = (origin.y0 + origin.y1) / 2;
  const line = Math.max(origin.y1 - origin.y0, 8);
  for (const other of neighbors) {
    if (other.x1 < origin.x0 - 4 || other.x0 > origin.x1 + 4) continue;
    const otherCenter = (other.y0 + other.y1) / 2;
    if (Math.abs(otherCenter - center) < line * 0.45) continue;
    if (otherCenter < center) {
      y0 = Math.min(origin.y0, Math.max(y0, other.y1 + 0.3));
    } else {
      y1 = Math.max(origin.y1, Math.min(y1, other.y0 - 0.3));
    }
  }
  if (y1 <= y0 + 2) return origin;
  return { x0: cover.x0, y0, x1: cover.x1, y1 };
}

/** Cover İ/Ü/Ğ/Ö marks in the inter-line gap without entering the previous line. */
export function expandInitialsCoverRect(
  box: OverlayBox,
  pageWidth?: number,
  pageHeight?: number,
  text = "",
  neighbors: OverlayBox[] = [],
  tightHoriz = false,
): OverlayBox {
  const height = Math.max(box.y1 - box.y0, 8);
  const horiz = tightHoriz ? 0.45 : Math.max(1.6, Math.min(3.2, height * 0.22));
  let up = 2.4;
  let down = 1.4;
  if ([...text].some((char) => MARKS_ABOVE.includes(char)) || hasBreveMark(text)) {
    up = 4.0;
  }
  if (hasBreveMark(text)) up = 6.2;
  if ([...text].some((char) => MARKS_BELOW.includes(char))) down = 2.6;
  const expanded = clipCoverToNeighbors(
    {
      x0: box.x0 - horiz,
      y0: box.y0 - up,
      x1: box.x1 + horiz,
      y1: box.y1 + down,
    },
    box,
    neighbors,
  );
  if (pageWidth == null || pageHeight == null) return expanded;
  const clipped = clipBox(expanded, pageWidth, pageHeight);
  if (clipped.x1 - clipped.x0 < 1 || clipped.y1 - clipped.y0 < 1) return box;
  return clipped;
}

/** Tight cover for chamber "X": hide the old digit without inflating the line box. */
export function expandCourtOrdinalCoverRect(
  box: OverlayBox,
  pageWidth?: number,
  pageHeight?: number,
): OverlayBox {
  const height = Math.max(box.y1 - box.y0, 1);
  const padX = 0.4;
  const padY = Math.min(0.8, height * 0.08);
  const cover = {
    x0: box.x0 - padX,
    y0: box.y0 - padY,
    x1: box.x1 + padX,
    y1: box.y1 + padY,
  };
  if (pageWidth == null || pageHeight == null) return cover;
  const clipped = clipBox(cover, pageWidth, pageHeight);
  if (clipped.x1 - clipped.x0 < 1 || clipped.y1 - clipped.y0 < 1) return box;
  return clipped;
}

/** Keep replacement glyphs on the original ink box after the cover grows upward. */
export function initialsLabelInset(
  cover: OverlayBox,
  origin: OverlayBox,
): { top: string; height: string } {
  const coverH = Math.max(cover.y1 - cover.y0, 1);
  const top = Math.max(0, origin.y0 - cover.y0);
  const height = Math.max(1, origin.y1 - origin.y0);
  return {
    top: `${(top / coverH) * 100}%`,
    height: `${(height / coverH) * 100}%`,
  };
}

const STACKED_X_TOL = 14;
const STACKED_MIN_DY = 0.45;
const STACKED_MAX_DY = 2.4;

function isNextStackedRow(first: OverlayBox, second: OverlayBox): boolean {
  if (Math.abs(first.x0 - second.x0) > STACKED_X_TOL) return false;
  const line = Math.max(first.y1 - first.y0, second.y1 - second.y0, 8);
  const dy = Math.abs(
    (first.y0 + first.y1) / 2 - (second.y0 + second.y1) / 2,
  );
  if (dy < line * STACKED_MIN_DY) return false;
  return dy <= line * STACKED_MAX_DY;
}

export function stackedInitialsRuns(
  items: Array<{ id: string; rect: OverlayBox }>,
): Array<Array<{ id: string; rect: OverlayBox }>> {
  if (items.length < 2) return [];
  const ordered = [...items].sort(
    (left, right) =>
      (left.rect.y0 + left.rect.y1) / 2 - (right.rect.y0 + right.rect.y1) / 2,
  );
  const runs: Array<Array<{ id: string; rect: OverlayBox }>> = [];
  let current: Array<{ id: string; rect: OverlayBox }> = [];
  for (const item of ordered) {
    if (current.length && isNextStackedRow(current[current.length - 1].rect, item.rect)) {
      current.push(item);
      continue;
    }
    if (current.length >= 2) runs.push(current);
    current = [item];
  }
  if (current.length >= 2) runs.push(current);
  return runs;
}

export function stackedInitialsEntityIds(
  items: Array<{ id: string; rect: OverlayBox }>,
): Set<string> {
  const stacked = new Set<string>();
  for (const run of stackedInitialsRuns(items)) {
    for (const item of run) stacked.add(item.id);
  }
  return stacked;
}

function padBox(box: OverlayBox, xPad: number, yDown: number): OverlayBox {
  return {
    x0: box.x0 - xPad,
    y0: box.y0,
    x1: box.x1 + xPad,
    y1: box.y1 + yDown,
  };
}

/** Drop mapping crumbs so a leftover word box does not reprint the mask. */
export function dropTinySiblingRects(
  rects: OverlayBox[],
  minRatio = 0.35,
): OverlayBox[] {
  if (rects.length <= 1) return rects.map((rect) => ({ ...rect }));
  const areas = rects.map((rect) => boxArea(rect));
  const maxArea = Math.max(...areas);
  if (maxArea <= 0) return rects.map((rect) => ({ ...rect }));
  const kept = rects.filter((_, index) => areas[index] >= maxArea * minRatio);
  if (kept.length) return kept.map((rect) => ({ ...rect }));
  const largest = rects[areas.indexOf(maxArea)];
  return largest ? [{ ...largest }] : [];
}

function usesReplacementCover(
  strategy: ReturnType<typeof effectiveStrategy>,
  entityType: string,
) {
  return (
    strategy === "PLACEHOLDER" ||
    (strategy === "PARTIAL_MASK" && entityType !== "COURT_NAME")
  );
}

/** One opaque line box so a two-word fake name is not painted into each word. */
export function replacementCoverRects(
  rects: OverlayBox[],
  tightHoriz = false,
): OverlayBox[] {
  if (!rects.length) return [];
  return mergeLineRects(rects).map((rect) =>
    padBox(rect, tightHoriz ? 0.35 : 2.0, 0.45),
  );
}

export function fitPlaceholderCoverRect(
  rect: OverlayBox,
  _tag: string,
  original: string,
  preferredPt: number,
  layoutWidth: number,
  blockers: OverlayBox[] = [],
): OverlayBox {
  const glyphs = Math.max(original.replace(/\s+/g, "").length, 2);
  const expectedW = glyphs * Math.max(preferredPt, 8) * 0.62 + 10;
  const expectedH = Math.max(preferredPt, 8) * 1.45;
  const origW = rect.x1 - rect.x0;
  const origH = rect.y1 - rect.y0;
  const box = {
    ...rect,
    x1: origW > expectedW * 2.8 ? rect.x0 + expectedW : rect.x1,
    y1: origH > expectedH * 2.2 ? rect.y0 + expectedH : rect.y1,
  };
  const line = Math.max(box.y1 - box.y0, 8);
  const mid = (box.y0 + box.y1) / 2;
  let x1 = box.x1;
  for (const other of blockers) {
    const otherMid = (other.y0 + other.y1) / 2;
    if (Math.abs(otherMid - mid) > line * 0.45) continue;
    if (other.x1 <= box.x0 + 0.5) continue;
    if (other.x0 < box.x1 - 0.5) continue;
    x1 = Math.min(x1, other.x0 - 1.2);
  }
  x1 = Math.min(x1, layoutWidth - 3);
  if (x1 <= box.x0 + 2) return box;
  return { ...box, x1 };
}

function replacementFontPx(
  text: string,
  rect: OverlayBox,
  layoutWidth: number,
  pageWidth: number,
  preferredPt: number,
  allowOverflow = false,
): number {
  const scale = pageWidth / layoutWidth;
  const preferredPx = preferredPt * scale;
  const boxW = Math.max(1, (rect.x1 - rect.x0) * scale);
  const boxH = Math.max(1, (rect.y1 - rect.y0) * scale);
  const fitted = Math.min(preferredPx, boxH);
  const estimated = text.length * fitted * 0.58;
  const limit = allowOverflow ? Math.max(boxW, boxW * 2.4) : boxW;
  if (estimated <= limit) return fitted;
  return Math.max(3, limit / Math.max(1, text.length * 0.58));
}

function courtOrdinalFontPx(
  rect: OverlayBox,
  layoutWidth: number,
  pageWidth: number,
  preferredPt: number,
): number {
  const scale = pageWidth / layoutWidth;
  const preferredPx = preferredPt * scale;
  const boxH = Math.max(1, (rect.y1 - rect.y0) * scale);
  // Line boxes are taller than the em; size X like the surrounding letters, not the box.
  return Math.max(7, Math.min(preferredPx, boxH * 0.7));
}

function dropContainedBoxes(
  groups: Map<string, OverlayBox[]>,
  entityById: Map<string, Entity>,
): Map<string, OverlayBox[]> {
  const items = [...groups.entries()].flatMap(([id, rects]) =>
    rects.map((rect) => ({ id, rect, area: boxArea(rect) })),
  );
  const kept = new Map<string, OverlayBox[]>();
  items.forEach((item, index) => {
    const swallowed = items.some((other, otherIndex) => {
      if (otherIndex === index || other.id === item.id) return false;
      if (other.area + 1 < item.area) return false;
      if (!boxContained(item.rect, other.rect)) return false;
      const inner = entityById.get(item.id);
      const outer = entityById.get(other.id);
      if (inner && outer && inner.type !== outer.type) return false;
      if (other.area > item.area + 1) return true;
      return otherIndex < index;
    });
    if (swallowed) return;
    kept.set(item.id, [...(kept.get(item.id) ?? []), item.rect]);
  });
  return kept;
}

function overlayRectsByEntity(
  spans: Array<{
    entity_id: string;
    rectangles: OverlayBox[];
    mask_rectangles?: OverlayBox[];
  }>,
  entityById: Map<string, Entity>,
  decisions: Decisions,
  categoryDefaults: CategoryDefaults,
  entityStrategies: EntityStrategies,
  viewMode: DocumentViewMode,
  showPreserved = false,
): Map<string, OverlayBox[]> {
  const groups = new Map<string, OverlayBox[]>();
  for (const span of spans) {
    const entity = entityById.get(span.entity_id);
    if (!entity) continue;
    const strategy = effectiveStrategy(
      entity,
      decisions,
      categoryDefaults,
      entityStrategies,
    );
    if (!showDetectionOverlay(entity, strategy, viewMode, showPreserved)) continue;
    const courtOrdinalScope =
      viewMode === "preview" &&
      entity.type === "COURT_NAME" &&
      (strategy === "PARTIAL_MASK" || strategy === "PLACEHOLDER");
    if (courtOrdinalScope && !span.mask_rectangles?.length) continue;
    const raw =
      courtOrdinalScope && span.mask_rectangles
        ? span.mask_rectangles
        : span.rectangles;
    const combined = mergeLineRects([
      ...(groups.get(span.entity_id) ?? []),
      ...raw,
    ]);
    groups.set(span.entity_id, combined);
  }
  if (viewMode === "preview") {
    for (const [id, rects] of groups) {
      const entity = entityById.get(id);
      if (!entity) continue;
      const strategy = effectiveStrategy(
        entity,
        decisions,
        categoryDefaults,
        entityStrategies,
      );
      if (usesReplacementCover(strategy, entity.type)) {
        if (entity.type === "COURT_NAME") continue;
        const covers =
          strategy === "PARTIAL_MASK" ? dropTinySiblingRects(rects) : rects;
        groups.set(id, replacementCoverRects(covers, strategy === "PLACEHOLDER"));
      }
    }
  }
  return viewMode === "detections"
    ? dropContainedBoxes(groups, entityById)
    : groups;
}

type DrawRect = {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  clientX?: number;
  clientY?: number;
};

type Props = {
  jobId: string;
  pageCount: number;
  entities: Entity[];
  decisions: Decisions;
  categoryDefaults: CategoryDefaults;
  entityStrategies: EntityStrategies;
  manual: ManualRedaction[];
  selectedManualId?: string | null;
  activeId: string | null;
  flashEntityIds?: string[];
  focusId: string | null;
  focusRectIndex?: number;
  currentPage: number;
  viewMode: DocumentViewMode;
  showPreserved?: boolean;
  tool: EditorTool;
  pageWidth: number;
  language: string;
  initialsFontSize?: number;
  initialPages?: PdfPageSpans[];
  pagePreviews?: Array<{ page: number; image: string }>;
  pageLabel?: (current: number, total: number) => string;
  boxOverrides?: Record<string, OverlayBox[]>;
  entityFills?: Record<string, string>;
  onSelect: (id: string | null, rectIndex?: number) => void;
  onSelectManual?: (id: string | null) => void;
  onPageInView: (page: number) => void;
  heldDraft?: DrawRect | null;
  onDrawComplete: (rect: DrawRect) => void;
  onBoxResize?: (entityId: string, rectangles: OverlayBox[]) => void;
  onManualBoxResize?: (manualId: string, rectangles: OverlayBox[]) => void;
  onFindingContextMenu?: (
    entityId: string,
    clientX: number,
    clientY: number,
    rectIndex?: number,
  ) => void;
};

export function PdfPageViewer({
  jobId,
  pageCount,
  entities,
  decisions,
  categoryDefaults,
  entityStrategies,
  manual,
  selectedManualId,
  activeId,
  flashEntityIds = [],
  focusId,
  focusRectIndex = 0,
  currentPage,
  viewMode,
  showPreserved = false,
  tool,
  pageWidth,
  language,
  initialsFontSize = DEFAULT_TEXT_SIZE,
  initialPages,
  pagePreviews,
  pageLabel,
  boxOverrides,
  entityFills,
  onSelect,
  onSelectManual,
  onPageInView,
  heldDraft,
  onDrawComplete,
  onBoxResize,
  onManualBoxResize,
  onFindingContextMenu,
}: Props) {
  const [fetchedPages, setFetchedPages] = useState<PdfPageSpans[]>([]);
  const [loadedPages, setLoadedPages] = useState<Record<number, boolean>>({});
  const [failedPages, setFailedPages] = useState<Record<number, boolean>>({});
  const [hydratedPages, setHydratedPages] = useState<Set<number>>(
    () => new Set(hydratePdfPageIndexes(currentPage, pageCount)),
  );
  const [draft, setDraft] = useState<DrawRect | null>(null);
  const draftRef = useRef<DrawRect | null>(null);
  const [liveBoxes, setLiveBoxes] = useState<Record<string, OverlayBox[]>>({});
  const [peekIds, setPeekIds] = useState<Set<string>>(() => new Set());
  const overlayHitsRef = useRef<Record<number, Array<{ id: string; rect: OverlayBox }>>>({});
  const drawing = useRef<{
    page: number;
    x: number;
    y: number;
    width: number;
    height: number;
    canvas: HTMLElement;
  } | null>(null);
  const resizing = useRef<{
    kind: "entity" | "manual";
    entityId: string;
    liveKey: string;
    rectIndex: number;
    edge: ResizeEdge;
    originX: number;
    originY: number;
    start: OverlayBox;
    rects: OverlayBox[];
    current: OverlayBox[];
    width: number;
    height: number;
  } | null>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
  const skipPageScroll = useRef(true);
  const currentPageRef = useRef(currentPage);
  currentPageRef.current = currentPage;
  const pages =
    initialPages && initialPages.length > 0 ? initialPages : fetchedPages;
  const previewByPage = new Map(
    (pagePreviews ?? []).map((item) => [item.page, item.image]),
  );
  const entityById = new Map(entities.map((entity) => [entity.id, entity]));

  const scrollPageIntoView = (pageNumber: number) => {
    const page = document.getElementById(`pdf-page-${pageNumber}`);
    const canvas = page?.closest(".review-canvas");
    if (!page || !(canvas instanceof HTMLElement)) return;
    const pageBox = page.getBoundingClientRect();
    const canvasBox = canvas.getBoundingClientRect();
    const top = canvas.scrollTop + (pageBox.top - canvasBox.top) - 16;
    canvas.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  };

  const scrollOverlayIntoView = (entityId: string, rectIndex = 0) => {
    const root = viewerRef.current;
    const canvas = root?.closest(".review-canvas");
    if (!root || !(canvas instanceof HTMLElement)) return;
    const frames = [
      ...root.querySelectorAll<HTMLElement>(
        `[data-entity-id="${CSS.escape(entityId)}"]`,
      ),
    ];
    const frame =
      frames.find((item) => item.dataset.rectIndex === String(rectIndex)) ??
      frames[0];
    if (!frame) return;
    scrollElementIntoCanvas(canvas, frame);
  };

  useEffect(() => {
    if (initialPages && initialPages.length > 0) return;
    let cancelled = false;
    fetchJobSpans(jobId)
      .then((data) => {
        if (!cancelled) setFetchedPages(data.pages ?? []);
      })
      .catch(() => {
        if (!cancelled) setFetchedPages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, initialPages]);

  useEffect(() => {
    const nearby = hydratePdfPageIndexes(currentPage, pageCount);
    setHydratedPages((current) => {
      let changed = false;
      const next = new Set(current);
      for (const index of nearby) {
        if (!next.has(index)) {
          next.add(index);
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [currentPage, pageCount]);

  useEffect(() => {
    if (skipPageScroll.current) {
      skipPageScroll.current = false;
      return;
    }
    if (focusId) return;
    scrollPageIntoView(currentPage);
  }, [currentPage]);

  useEffect(() => {
    const root = viewerRef.current;
    const canvas = root?.closest(".review-canvas");
    if (!root || !(canvas instanceof HTMLElement)) return;
    let raf = 0;
    const report = () => {
      const canvasBox = canvas.getBoundingClientRect();
      const next = pageInViewFromRects(
        [...root.querySelectorAll<HTMLElement>(".pdf-page-wrap")].map(
          (page) => {
            const box = page.getBoundingClientRect();
            const match = /^pdf-page-(\d+)$/.exec(page.id);
            return {
              page: match ? Number(match[1]) : 0,
              top: box.top,
              bottom: box.bottom,
            };
          },
        ),
        { top: canvasBox.top, bottom: canvasBox.bottom },
      );
      if (next == null || next === currentPageRef.current) return;
      skipPageScroll.current = true;
      onPageInView(next);
    };
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        report();
      });
    };
    canvas.addEventListener("scroll", onScroll, { passive: true });
    report();
    return () => {
      canvas.removeEventListener("scroll", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [pageCount, pageWidth, onPageInView]);

  useEffect(() => {
    if (!focusId) return;
    let frame = 0;
    const run = () => {
      scrollOverlayIntoView(focusId, focusRectIndex);
    };
    run();
    frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(run);
    });
    return () => cancelAnimationFrame(frame);
  }, [focusId, focusRectIndex, pageWidth, pages.length]);

  useEffect(() => {
    if (!selectedManualId) return;
    const root = viewerRef.current;
    const canvas = root?.closest(".review-canvas");
    if (!root || !(canvas instanceof HTMLElement)) return;
    const frame = root.querySelector<HTMLElement>(
      `[data-entity-id="${CSS.escape(`manual:${selectedManualId}`)}"]`,
    );
    if (!frame) return;
    // Keep the current scroll after apply — the drawn box is already in view.
    // Only move when the user picks an off-screen manual item from the list.
    if (isElementVisibleInCanvas(canvas, frame)) return;
    scrollOverlayIntoView(`manual:${selectedManualId}`);
  }, [selectedManualId]);

  const startDraw = (
    page: number,
    event: PointerEvent<HTMLDivElement>,
    width: number,
    height: number,
  ) => {
    const target = event.target as HTMLElement;
    if (target.closest(".pdf-resize") && tool === "select") return;
    if (tool !== "redact-area" && tool !== "add-text") {
      onSelectManual?.(null);
      if (!target.closest(".pdf-entity")) onSelect(null);
      return;
    }
    if (drawing.current) return;
    event.preventDefault();
    event.stopPropagation();
    onSelectManual?.(null);
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * width;
    const y = ((event.clientY - bounds.top) / bounds.height) * height;
    drawing.current = { page, x, y, width, height, canvas };
    const next = { page, x0: x, y0: y, x1: x, y1: y };
    draftRef.current = next;
    setDraft(next);

    const pointOnPage = (clientX: number, clientY: number) => {
      const session = drawing.current;
      if (!session) return null;
      const box = session.canvas.getBoundingClientRect();
      return {
        x: Math.max(
          0,
          Math.min(
            ((clientX - box.left) / box.width) * session.width,
            session.width,
          ),
        ),
        y: Math.max(
          0,
          Math.min(
            ((clientY - box.top) / box.height) * session.height,
            session.height,
          ),
        ),
      };
    };

    const onMove = (moveEvent: globalThis.PointerEvent) => {
      const session = drawing.current;
      if (!session) return;
      const point = pointOnPage(moveEvent.clientX, moveEvent.clientY);
      if (!point) return;
      const updated = {
        page: session.page,
        x0: Math.min(session.x, point.x),
        y0: Math.min(session.y, point.y),
        x1: Math.max(session.x, point.x),
        y1: Math.max(session.y, point.y),
      };
      draftRef.current = updated;
      setDraft(updated);
    };

    const onUp = (upEvent: globalThis.PointerEvent) => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      const session = drawing.current;
      const rect = draftRef.current;
      drawing.current = null;
      draftRef.current = null;
      setDraft(null);
      if (!session || !rect) return;
      let { x0, y0, x1, y1 } = rect;
      if (x1 - x0 < 8) {
        x1 = Math.min(session.width, x0 + 28);
        x0 = Math.max(0, x1 - 28);
      }
      if (y1 - y0 < 8) {
        y1 = Math.min(session.height, y0 + 16);
        y0 = Math.max(0, y1 - 16);
      }
      onDrawComplete({
        page: rect.page,
        x0,
        y0,
        x1,
        y1,
        clientX: upEvent.clientX,
        clientY: upEvent.clientY,
      });
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  };

  const startResize = (
    event: PointerEvent<HTMLSpanElement>,
    entityId: string,
    rectIndex: number,
    edge: ResizeEdge,
    rect: OverlayBox,
    rects: OverlayBox[],
    width: number,
    height: number,
    canvas: HTMLElement | null,
    kind: "entity" | "manual" = "entity",
  ) => {
    if (viewMode !== "detections" || tool !== "select") return;
    event.preventDefault();
    event.stopPropagation();
    if (!canvas) return;
    const bounds = canvas.getBoundingClientRect();
    const initial = rects.map((item) => ({ ...item }));
    const liveKey = kind === "manual" ? `manual:${entityId}` : entityId;
    resizing.current = {
      kind,
      entityId,
      liveKey,
      rectIndex,
      edge,
      originX: ((event.clientX - bounds.left) / bounds.width) * width,
      originY: ((event.clientY - bounds.top) / bounds.height) * height,
      start: { ...rect },
      rects: initial,
      current: initial,
      width,
      height,
    };
    setLiveBoxes((current) => ({ ...current, [liveKey]: initial }));
    const handleMove = (moveEvent: globalThis.PointerEvent) => {
      const session = resizing.current;
      if (!session) return;
      const box = canvas.getBoundingClientRect();
      const x = ((moveEvent.clientX - box.left) / box.width) * session.width;
      const y = ((moveEvent.clientY - box.top) / box.height) * session.height;
      const next = applyOverlayResize(
        session.start,
        session.edge,
        x - session.originX,
        y - session.originY,
        { width: session.width, height: session.height },
      );
      session.current = replaceOverlayRect(
        session.rects,
        session.rectIndex,
        next,
      );
      setLiveBoxes((current) => ({
        ...current,
        [session.liveKey]: session.current,
      }));
    };
    const handleUp = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      const session = resizing.current;
      resizing.current = null;
      if (!session) return;
      if (session.kind === "manual") {
        onManualBoxResize?.(session.entityId, session.current);
      } else {
        onBoxResize?.(session.entityId, session.current);
      }
      setLiveBoxes((current) => {
        const next = { ...current };
        delete next[session.liveKey];
        return next;
      });
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
  };

  const applyPeek = (ids: string[]) => {
    const next = new Set(ids);
    setPeekIds((current) => (sameIdSet(current, next) ? current : next));
  };

  const peekFromPointer = (
    event: PointerEvent<HTMLDivElement>,
    pageIndex: number,
    width: number,
    height: number,
  ) => {
    if (viewMode !== "preview" || drawing.current || resizing.current) {
      applyPeek([]);
      return;
    }
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * width;
    const y = ((event.clientY - bounds.top) / bounds.height) * height;
    applyPeek(peekOverlayIds(overlayHitsRef.current[pageIndex] ?? [], x, y));
  };

  return (
    <div className="pdf-page-viewer" ref={viewerRef}>
      {Array.from({ length: pageCount }, (_, pageIndex) => {
        const layout = pages.find((page) => page.page === pageIndex);
        const loaded = Boolean(loadedPages[pageIndex]);
        const ratio =
          layout && layout.width > 0
            ? `${layout.width} / ${layout.height}`
            : "1 / 1.414";
        const width = layout?.width ?? 595;
        const height = layout?.height ?? 842;
        return (
          <div
            key={pageIndex}
            className="pdf-page-wrap"
            id={`pdf-page-${pageIndex + 1}`}
            style={{ width: pageWidth }}
          >
            <div className="pdf-page-label">
              {pageLabel?.(pageIndex + 1, pageCount) ??
                `Sayfa ${pageIndex + 1} / ${pageCount}`}
            </div>
            <div
              className={`pdf-page-canvas${tool === "redact-area" || tool === "add-text" ? " is-drawing" : ""}`}
              style={{ aspectRatio: ratio }}
              onPointerDownCapture={(event) =>
                startDraw(pageIndex, event, width, height)
              }
              onPointerMove={(event) =>
                peekFromPointer(event, pageIndex, width, height)
              }
              onPointerLeave={() => applyPeek([])}
            >
              {!loaded && !failedPages[pageIndex] && (
                <div className="pdf-page-skeleton" aria-hidden />
              )}
              {failedPages[pageIndex] && !previewByPage.get(pageIndex) ? (
                <p className="pdf-page-missing">
                  {language.startsWith("tr")
                    ? "Sayfa görüntüsü yüklenemedi. Belgeyi yeniden yükleyin."
                    : "The page image could not be loaded. Upload the document again."}
                </p>
              ) : hydratedPages.has(pageIndex) ? (
                <img
                  src={
                    previewByPage.get(pageIndex) ??
                    getPageImageUrl(jobId, pageIndex, PAGE_SCALE)
                  }
                  alt={
                    pageLabel?.(pageIndex + 1, pageCount) ??
                    `Sayfa ${pageIndex + 1}`
                  }
                  className={`pdf-page-img${loaded ? " is-ready" : ""}`}
                  loading={pageIndex < 2 ? "eager" : "lazy"}
                  draggable={false}
                  onLoad={() =>
                    setLoadedPages((current) =>
                      current[pageIndex]
                        ? current
                        : { ...current, [pageIndex]: true },
                    )
                  }
                  onError={() => {
                    if (previewByPage.get(pageIndex)) return;
                    setFailedPages((current) =>
                      current[pageIndex]
                        ? current
                        : { ...current, [pageIndex]: true },
                    );
                  }}
                />
              ) : null}
              {(() => {
                const overlayByEntity = overlayRectsByEntity(
                  layout?.spans ?? [],
                  entityById,
                  decisions,
                  categoryDefaults,
                  entityStrategies,
                  viewMode,
                  showPreserved,
                );
                for (const span of layout?.spans ?? []) {
                  const override =
                    liveBoxes[span.entity_id] ?? boxOverrides?.[span.entity_id];
                  if (override) overlayByEntity.set(span.entity_id, override);
                }
                let stackedIds = new Set<string>();
                const initialsOrigins = new Map<string, OverlayBox[]>();
                if (viewMode === "preview") {
                  const initialsItems: Array<{ id: string; rect: OverlayBox }> =
                    [];
                  for (const [id, rects] of overlayByEntity) {
                    const entity = entityById.get(id);
                    if (!entity || !rects.length) continue;
                    const strategy = effectiveStrategy(
                      entity,
                      decisions,
                      categoryDefaults,
                      entityStrategies,
                    );
                    if (
                      strategy === "INITIALS" ||
                      usesReplacementCover(strategy, entity.type)
                    ) {
                      initialsOrigins.set(id, rects);
                    }
                    if (strategy === "INITIALS") {
                      initialsItems.push({ id, rect: unionBoxes(rects) });
                    }
                  }
                  stackedIds = stackedInitialsEntityIds(initialsItems);
                  const stackedRuns = stackedInitialsRuns(initialsItems);
                  const lineNeighbors = layout?.line_rects ?? [];
                  for (const [id, rects] of overlayByEntity) {
                    const entity = entityById.get(id);
                    if (!entity) continue;
                    const strategy = effectiveStrategy(
                      entity,
                      decisions,
                      categoryDefaults,
                      entityStrategies,
                    );
                    if (
                      strategy !== "INITIALS" &&
                      !usesReplacementCover(strategy, entity.type)
                    )
                      continue;
                    const stackedNeighbors =
                      strategy === "INITIALS" && stackedIds.has(id)
                      ? stackedRuns
                          .find((run) => run.some((item) => item.id === id))
                          ?.filter((item) => item.id !== id)
                          .map((item) => item.rect) ?? []
                      : [];
                    overlayByEntity.set(
                      id,
                      rects.map((rect) =>
                        strategy === "PLACEHOLDER" && entity.type === "COURT_NAME"
                          ? expandCourtOrdinalCoverRect(rect, width, height)
                          : expandInitialsCoverRect(
                              rect,
                              width,
                              height,
                              entity.text,
                              [...stackedNeighbors, ...lineNeighbors],
                              strategy === "PLACEHOLDER",
                            ),
                      ),
                    );
                  }
                  const placeholderBlockers = [...overlayByEntity.entries()].flatMap(
                    ([id, rects]) => rects.map((rect) => ({ id, rect })),
                  );
                  for (const [id, rects] of overlayByEntity) {
                    const entity = entityById.get(id);
                    if (!entity) continue;
                    const strategy = effectiveStrategy(
                      entity,
                      decisions,
                      categoryDefaults,
                      entityStrategies,
                    );
                    if (strategy !== "PLACEHOLDER") continue;
                    const courtOrdinalPlaceholder = entity.type === "COURT_NAME";
                    const tag = courtOrdinalPlaceholder
                      ? COURT_ORDINAL_TAG
                      : previewEntityValue(
                          entity.text,
                          entity.type,
                          strategy,
                          language,
                          {
                            role: entity.role,
                            placeholderToken: entity.placeholder_token,
                            entity,
                            entities,
                          },
                        );
                    const others = placeholderBlockers
                      .filter((item) => item.id !== id)
                      .map((item) => item.rect);
                    overlayByEntity.set(
                      id,
                      rects.map((rect) =>
                        fitPlaceholderCoverRect(
                          rect,
                          tag,
                          courtOrdinalPlaceholder
                            ? COURT_ORDINAL_TAG
                            : entity.text,
                          initialsPointSize(entity, initialsFontSize),
                          width,
                          others,
                        ),
                      ),
                    );
                  }
                }
                const hitItems: Array<{ id: string; rect: OverlayBox }> = [];
                for (const [id, rects] of overlayByEntity) {
                  for (const rect of rects) hitItems.push({ id, rect });
                }
                manual.forEach((item, index) => {
                  if (item.page !== pageIndex + 1 || item.kept || !item.rectangles?.length)
                    return;
                  const itemId = manualItemId(item, index);
                  const rects = liveBoxes[`manual:${itemId}`] ?? item.rectangles;
                  for (const rect of rects) {
                    hitItems.push({ id: `manual:${itemId}`, rect });
                  }
                });
                overlayHitsRef.current[pageIndex] = hitItems;
                const renderedEntities = new Set<string>();
                return (layout?.spans ?? []).map((span) => {
                  if (renderedEntities.has(span.entity_id)) return null;
                  renderedEntities.add(span.entity_id);
                  const entity = entityById.get(span.entity_id);
                  if (!entity) return null;
                  const strategy = effectiveStrategy(
                    entity,
                    decisions,
                    categoryDefaults,
                    entityStrategies,
                  );
                  const preview = previewEntityValue(
                    entity.text,
                    entity.type,
                    strategy,
                    language,
                    {
                      role: entity.role,
                      placeholderToken: entity.placeholder_token,
                      entity,
                      entities,
                    },
                  );
                  const kept = strategy === "KEEP";
                  if (!showDetectionOverlay(entity, strategy, viewMode, showPreserved))
                    return null;
                  const focused = focusId === span.entity_id;
                  const courtOrdinalScope =
                    viewMode === "preview" &&
                    entity.type === "COURT_NAME" &&
                    (strategy === "PARTIAL_MASK" || strategy === "PLACEHOLDER");
                  const ordinalMask =
                    courtOrdinalScope &&
                    strategy === "PARTIAL_MASK" &&
                    Boolean(span.mask_rectangles?.length);
                  const courtOrdinalTag =
                    courtOrdinalScope &&
                    strategy === "PLACEHOLDER" &&
                    Boolean(span.mask_rectangles?.length);
                  const initialsCover =
                    viewMode === "preview" && strategy === "INITIALS" && !kept;
                  const columnInitials =
                    initialsCover && stackedIds.has(span.entity_id);
                  const placeholderCover =
                    viewMode === "preview" && strategy === "PLACEHOLDER" && !kept;
                  const partialCover =
                    viewMode === "preview" &&
                    strategy === "PARTIAL_MASK" &&
                    !kept &&
                    !ordinalMask;
                  const replacementCover = placeholderCover || partialCover;
                  const coverOriginal =
                    initialsCover || replacementCover;
                  const overlayRects =
                    overlayByEntity.get(span.entity_id) ?? [];
                  const originRects =
                    initialsOrigins.get(span.entity_id) ?? overlayRects;
                  const pointSize = initialsPointSize(entity, initialsFontSize);
                  const selected = activeId === span.entity_id;
                  const fillOverride = entityFills?.[span.entity_id];
                  const paperRedact =
                    strategy === "REDACT" &&
                    viewMode === "preview" &&
                    usesPaperRedaction(entity.type, entity.attributes) &&
                    !fillOverride;
                  const redactFill =
                    viewMode === "preview" &&
                    (strategy === "REDACT" || ordinalMask)
                      ? (fillOverride ??
                        defaultRedactFill(
                          usesPaperRedaction(entity.type, entity.attributes),
                        ))
                      : undefined;
                  const canResize =
                    selected &&
                    viewMode === "detections" &&
                    tool === "select" &&
                    Boolean(onBoxResize);
                  return overlayRects.map((rect, rectIndex) => {
                    const originRect = originRects[rectIndex] ?? rect;
                    const labelInset = initialsCover
                      ? initialsLabelInset(rect, originRect)
                      : null;
                    const originHeight = Math.max(originRect.y1 - originRect.y0, 1);
                    const initialsFontPx = Math.min(
                      (pointSize * pageWidth) / width,
                      (originHeight * pageWidth) / width,
                    );
                    const replacementPx = courtOrdinalTag
                      ? courtOrdinalFontPx(
                          originRect,
                          width,
                          pageWidth,
                          pointSize,
                        )
                      : replacementFontPx(
                          preview,
                          originRect,
                          width,
                          pageWidth,
                          pointSize,
                          false,
                        );
                    const peeking = peekIds.has(span.entity_id);
                    const stack =
                      2 +
                      hitItems.filter(
                        (other) => boxArea(other.rect) > boxArea(rect) + 1,
                      ).length;
                    return (
                    <div
                      key={`${span.entity_id}-${rectIndex}`}
                      className={[
                        "pdf-entity-frame",
                        initialsCover || replacementCover
                          ? "is-cover-clip"
                          : "",
                        peeking ? "is-peeking" : "",
                        flashEntityIds.includes(span.entity_id) ? "is-flash" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      data-entity-id={span.entity_id}
                      data-rect-index={rectIndex}
                      style={{
                        left: `${(rect.x0 / width) * 100}%`,
                        top: `${(rect.y0 / height) * 100}%`,
                        width: `${((rect.x1 - rect.x0) / width) * 100}%`,
                        height: `${((rect.y1 - rect.y0) / height) * 100}%`,
                        zIndex: peeking || selected ? 8 : stack,
                      }}
                    >
                      <button
                        type="button"
                        className={[
                          "pdf-entity",
                          `view-${viewMode}`,
                          kept ? "is-kept is-preserved" : categoryAccent(entity.type),
                          (strategy === "REDACT" || ordinalMask) &&
                          viewMode === "preview"
                            ? "is-redact"
                            : "",
                          paperRedact ? "is-paper-redact" : "",
                          initialsCover ? "is-initials" : "",
                          columnInitials ? "is-column-initials" : "",
                          placeholderCover ? "is-placeholder" : "",
                          courtOrdinalTag ? "is-court-ordinal" : "",
                          partialCover ? "is-partial" : "",
                          viewMode === "preview" && !kept ? "is-peekable" : "",
                          peeking ? "is-peek" : "",
                          selected ? "is-active" : "",
                          focused ? "is-focus" : "",
                          flashEntityIds.includes(span.entity_id) ? "is-flash" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        aria-pressed={selected}
                        aria-label={span.text}
                        style={
                          redactFill
                            ? { ["--pdf-fill" as string]: redactFill }
                            : undefined
                        }
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelect(span.entity_id, rectIndex);
                          onPageInView(pageIndex + 1);
                        }}
                        onContextMenu={(event) => {
                          if (!shouldOpenDocumentContextMenu(viewMode, tool) || !onFindingContextMenu) {
                            return;
                          }
                          event.preventDefault();
                          event.stopPropagation();
                          onFindingContextMenu(
                            span.entity_id,
                            event.clientX,
                            event.clientY,
                            rectIndex,
                          );
                        }}
                      >
                        {viewMode === "preview" &&
                          !kept &&
                          strategy !== "REDACT" &&
                          !ordinalMask && (
                            <span
                              className="pdf-entity-label"
                              style={
                                replacementCover
                                  ? {
                                      color: "#111318",
                                      background: "#ffffff",
                                      fontFamily: fontCss("times"),
                                      fontSize: `${replacementPx}px`,
                                      fontWeight: 400,
                                      letterSpacing: 0,
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      textAlign: "center",
                                      lineHeight: 1,
                                      padding: 0,
                                      whiteSpace: "nowrap",
                                      overflow: "hidden",
                                      width: "100%",
                                      height: "100%",
                                      maxWidth: "100%",
                                    }
                                  : coverOriginal
                                    ? {
                                        position: "absolute",
                                        left: 0,
                                        width: "100%",
                                        top: labelInset?.top ?? "0%",
                                        height: labelInset?.height ?? "100%",
                                        color: "#111318",
                                        background: "transparent",
                                        fontFamily: fontCss("times"),
                                        fontSize: `${initialsFontPx}px`,
                                        fontWeight: 400,
                                        letterSpacing: 0,
                                        display: "flex",
                                        alignItems: "flex-end",
                                        justifyContent: columnInitials
                                          ? "flex-start"
                                          : "center",
                                        textAlign: columnInitials
                                          ? "left"
                                          : "center",
                                        lineHeight: 1,
                                        padding: columnInitials ? "0 0 0 1px" : 0,
                                      }
                                    : undefined
                              }
                            >
                              {courtOrdinalTag ? COURT_ORDINAL_TAG : preview}
                            </span>
                          )}
                      </button>
                      {canResize &&
                        RESIZE_EDGES.map((edge) => (
                          <span
                            key={edge}
                            className={`pdf-resize is-${edge}`}
                            role="slider"
                            aria-label={
                              language.startsWith("tr")
                                ? `Çerçeveyi ${edge} yönünde boyutlandır`
                                : `Resize frame ${edge}`
                            }
                            onPointerDown={(event) =>
                              startResize(
                                event,
                                span.entity_id,
                                rectIndex,
                                edge,
                                rect,
                                overlayRects,
                                width,
                                height,
                                event.currentTarget.closest(".pdf-page-canvas"),
                              )
                            }
                          />
                        ))}
                    </div>
                  );
                  });
                });
              })()}
              {manual.map((item, index) => {
                if (item.page !== pageIndex + 1 || !item.rectangles?.length)
                  return null;
                const itemId = manualItemId(item, index);
                const selected = selectedManualId === itemId;
                const kept = Boolean(item.kept);
                if (kept) return null;
                const overlayRects =
                  liveBoxes[`manual:${itemId}`] ?? item.rectangles;
                const clearFill = item.fill === TRANSPARENT_FILL;
                const canResize =
                  selected &&
                  viewMode === "detections" &&
                  tool === "select" &&
                  Boolean(onManualBoxResize);
                return overlayRects.map((rect, rectIndex) => {
                  const peeking = peekIds.has(`manual:${itemId}`);
                  return (
                  <div
                    key={`manual-${itemId}-${rectIndex}`}
                    className={`pdf-entity-frame${peeking ? " is-peeking" : ""}`}
                    data-entity-id={`manual:${itemId}`}
                    data-rect-index={rectIndex}
                    style={{
                      left: `${(rect.x0 / width) * 100}%`,
                      top: `${(rect.y0 / height) * 100}%`,
                      width: `${((rect.x1 - rect.x0) / width) * 100}%`,
                      height: `${((rect.y1 - rect.y0) / height) * 100}%`,
                      zIndex: peeking || selected ? 8 : 2,
                    }}
                  >
                    <button
                      type="button"
                      className={[
                        "pdf-entity",
                        `view-${viewMode}`,
                        categoryAccent(item.category ?? "OTHER_IDENTIFIER"),
                        "is-manual",
                        !kept && viewMode === "preview" && !clearFill
                          ? "is-redact"
                          : "",
                        !kept && viewMode === "preview" && clearFill
                          ? "is-clear-fill"
                          : "",
                        viewMode === "preview" && !kept ? "is-peekable" : "",
                        peeking ? "is-peek" : "",
                        selected ? "is-active" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      style={
                        !kept && viewMode === "preview" && !clearFill
                          ? { ["--pdf-fill" as string]: item.fill ?? defaultRedactFill() }
                          : undefined
                      }
                      aria-pressed={selected}
                      aria-label={item.replacement || item.text}
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelectManual?.(itemId);
                        onPageInView(pageIndex + 1);
                      }}
                      onPointerDown={(event) => event.stopPropagation()}
                    >
                      {viewMode === "preview" && !kept && item.replacement && (
                        <span
                          className="pdf-entity-label"
                          style={{
                            color: item.textColor ?? "#111318",
                            background: "transparent",
                            fontFamily: fontCss(item.font),
                            fontSize: `${((item.fontSize ?? DEFAULT_TEXT_SIZE) * pageWidth) / width}px`,
                            fontWeight: 400,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            textAlign: "center",
                          }}
                        >
                          {item.replacement}
                        </span>
                      )}
                    </button>
                    {canResize &&
                      RESIZE_EDGES.map((edge) => (
                        <span
                          key={edge}
                          className={`pdf-resize is-${edge}`}
                          role="slider"
                          aria-label={
                            language.startsWith("tr")
                              ? `Çerçeveyi ${edge} yönünde boyutlandır`
                              : `Resize frame ${edge}`
                          }
                          onPointerDown={(event) =>
                            startResize(
                              event,
                              itemId,
                              rectIndex,
                              edge,
                              rect,
                              overlayRects,
                              width,
                              height,
                              event.currentTarget.closest(".pdf-page-canvas"),
                              "manual",
                            )
                          }
                        />
                      ))}
                  </div>
                  );
                });
              })}
              {(draft ?? heldDraft)?.page === pageIndex &&
                (draft ?? heldDraft) && (
                  <div
                    className="pdf-draw-rect"
                    style={{
                      left: `${((draft ?? heldDraft)!.x0 / width) * 100}%`,
                      top: `${((draft ?? heldDraft)!.y0 / height) * 100}%`,
                      width: `${(((draft ?? heldDraft)!.x1 - (draft ?? heldDraft)!.x0) / width) * 100}%`,
                      height: `${(((draft ?? heldDraft)!.y1 - (draft ?? heldDraft)!.y0) / height) * 100}%`,
                    }}
                  />
                )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
