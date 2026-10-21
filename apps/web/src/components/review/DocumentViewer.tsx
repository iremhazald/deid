import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject,
} from "react";
import {
  categoryAccent,
  effectiveStrategy,
  initialsPointSize,
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
  UserDefinedTerm,
} from "../../state/types";
import { PdfPageViewer } from "./PdfPageViewer";
import { DEFAULT_TEXT_SIZE, defaultRedactFill, fontCss } from "./documentFonts";
import {
  flowTextLines,
  pageIndexAt,
  pdfSourcePageTexts,
  textDocumentEntityStyle,
  textDocumentPageStyle,
  textFlowPageStyle,
  textPageBoundaries,
  textWorkspaceCanvasStyle,
  usablePdfTextLayout,
  type FlowPiece,
  type PdfTextLayout,
} from "./textWorkspacePages";
import { spanStepOverlaps } from "../../state/findingSpan";
import { applyPaperHeaderMasks, type TextPart } from "./paperHeader";
import { suggestSelectionCategory } from "./selectionCategory";
import {
  presentationGroupForEntityType,
  presentationGroupLabelKey,
  presentationTypeOptions,
} from "../../state/presentationTaxonomy";
import {
  offsetsForSelectedSource,
  showsPdfPageViewer,
} from "../../state/workspaceMode";

type SelectionPopup = {
  text: string;
  x: number;
  y: number;
  noteY: number;
  place: "above" | "below";
  start?: number;
  category: string;
  categoryOpen: boolean;
  saving: boolean;
  error: string | null;
};

type Props = {
  jobId: string;
  documentKind?: string;
  workspaceMode?: string | null;
  pageCount?: number;
  pageTexts?: string[];
  pageLayouts?: import("./textWorkspacePages").PdfTextLayout[] | null;
  pageSpans?: import("../../api/client").PdfPageSpans[];
  pagePreviews?: Array<{ page: number; image: string }>;
  text: string;
  entities: Entity[];
  decisions: Decisions;
  categoryDefaults: CategoryDefaults;
  entityStrategies: EntityStrategies;
  manual: ManualRedaction[];
  selectedManualId?: string | null;
  activeId: string | null;
  focusId: string | null;
  focusRectIndex?: number;
  currentPage: number;
  viewMode: DocumentViewMode;
  showPreserved?: boolean;
  tool: EditorTool;
  pageWidth: number;
  language: string;
  initialsFontSize?: number;
  t: (key: string, options?: Record<string, unknown>) => string;
  onSelect: (id: string | null, rectIndex?: number) => void;
  onSelectManual?: (id: string | null) => void;
  onPageInView: (page: number) => void;
  onManualAdd: (
    item: Omit<ManualRedaction, "page"> & { page?: number },
  ) => void;
  boxOverrides?: Record<string, { x0: number; y0: number; x1: number; y1: number }[]>;
  entityFills?: Record<string, string>;
  onBoxResize?: (
    entityId: string,
    rectangles: Array<{ x0: number; y0: number; x1: number; y1: number }>,
  ) => void;
  onManualBoxResize?: (
    manualId: string,
    rectangles: Array<{ x0: number; y0: number; x1: number; y1: number }>,
  ) => void;
  heldDraft?: {
    page: number;
    x0: number;
    y0: number;
    x1: number;
    y1: number;
  } | null;
  onAreaDrawn: (rect: {
    page: number;
    x0: number;
    y0: number;
    x1: number;
    y1: number;
    clientX?: number;
    clientY?: number;
  }) => void;
  onAddCustomTerm?: (term: UserDefinedTerm) => void | Promise<void>;
  flashEntityIds?: string[];
  onFindingContextMenu?: (
    entityId: string,
    clientX: number,
    clientY: number,
    rectIndex?: number,
  ) => void;
  onEditSpan?: (entityId: string, start: number, end: number) => Promise<void>;
};

export function DocumentViewer({
  jobId,
  documentKind,
  workspaceMode,
  pageCount = 1,
  pageTexts,
  pageLayouts,
  pageSpans,
  pagePreviews,
  text,
  entities,
  decisions,
  categoryDefaults,
  entityStrategies,
  manual,
  selectedManualId,
  activeId,
  focusId,
  focusRectIndex,
  currentPage,
  viewMode,
  showPreserved = false,
  tool,
  pageWidth,
  language,
  initialsFontSize = DEFAULT_TEXT_SIZE,
  t,
  onSelect,
  onSelectManual,
  onPageInView,
  onAreaDrawn,
  onAddCustomTerm,
  flashEntityIds = [],
  boxOverrides,
  entityFills,
  onBoxResize,
  onManualBoxResize,
  heldDraft,
  onFindingContextMenu,
  onEditSpan,
}: Props) {
  const isPdf = showsPdfPageViewer(documentKind, workspaceMode);
  const [popup, setPopup] = useState<SelectionPopup | null>(null);
  const [addedNote, setAddedNote] = useState<{ text: string; x: number; y: number } | null>(null);
  const [liveSpan, setLiveSpan] = useState<{ id: string; start: number; end: number } | null>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const selectMode = tool === "select-text";
  const shownEntities = useMemo(() => {
    if (!liveSpan) return entities;
    return entities.map((entity) =>
      entity.id === liveSpan.id
        ? { ...entity, start: liveSpan.start, end: liveSpan.end, text: text.slice(liveSpan.start, liveSpan.end) }
        : entity,
    );
  }, [entities, liveSpan, text]);

  const parts = useMemo(() => {
    const result: Array<{ text: string; entity?: Entity }> = [];
    let cursor = 0;
    const sorted = [...shownEntities].sort(
      (a, b) => a.start - b.start || b.end - a.end,
    );
    for (const entity of sorted) {
      if (entity.start < cursor) continue;
      if (cursor < entity.start)
        result.push({ text: text.slice(cursor, entity.start) });
      result.push({ text: text.slice(entity.start, entity.end), entity });
      cursor = entity.end;
    }
    if (cursor < text.length) result.push({ text: text.slice(cursor) });
    return result;
  }, [text, shownEntities]);

  const shownParts = useMemo(
    () => applyPaperHeaderMasks(parts, text, shownEntities, viewMode),
    [parts, text, shownEntities, viewMode],
  );

  useEffect(() => {
    if (!activeId || isPdf) return;
    document.getElementById(`entity-${activeId}`)?.scrollIntoView({
      block: "nearest",
      behavior: "smooth",
    });
  }, [activeId, isPdf]);

  const textPageRef = useRef(currentPage);
  useEffect(() => {
    if (isPdf || !pdfSourcePageTexts(documentKind, text, pageTexts)) return;
    if (textPageRef.current === currentPage) return;
    textPageRef.current = currentPage;
    document.getElementById(`pdf-page-${currentPage}`)?.scrollIntoView({
      block: "start",
    });
  }, [currentPage, isPdf, documentKind, text, pageTexts]);

  useEffect(() => {
    if (!popup) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest(".selection-popup")) return;
      setPopup(null);
      window.getSelection()?.removeAllRanges();
    };
    window.addEventListener("pointerdown", onPointerDown, true);
    return () => window.removeEventListener("pointerdown", onPointerDown, true);
  }, [popup]);

  useEffect(() => {
    if (selectMode) return;
    setPopup(null);
  }, [selectMode]);

  useEffect(() => {
    if (!addedNote) return;
    const timer = window.setTimeout(() => setAddedNote(null), 1600);
    return () => window.clearTimeout(timer);
  }, [addedNote]);

  const handleMouseUp = useCallback((event: MouseEvent) => {
    const target = event.target;
    if (target instanceof Element && target.closest(".selection-popup")) return;
    if (!selectMode) return;
    const sel = window.getSelection();
    const selected = sel?.toString().trim();
    if (!selected || selected.length < 2) {
      setPopup(null);
      return;
    }
    const range = sel?.getRangeAt(0);
    if (!range || !sheetRef.current?.contains(range.commonAncestorContainer)) {
      setPopup(null);
      return;
    }
    const rect = range.getBoundingClientRect();
    const sheetRect = sheetRef.current.getBoundingClientRect();
    const start = selectionStartInDocument(sheetRef.current, range, text, selected);
    const place = window.innerHeight - rect.bottom < 280 ? "above" : "below";
    setPopup({
      text: selected,
      x: rect.left - sheetRect.left + rect.width / 2,
      y: place === "above" ? rect.top - sheetRect.top - 8 : rect.bottom - sheetRect.top + 8,
      noteY: rect.bottom - sheetRect.top + 8,
      place,
      category: suggestSelectionCategory(selected),
      categoryOpen: false,
      saving: false,
      error: null,
      ...(start != null ? { start } : {}),
    });
  }, [selectMode, text]);

  const addSelectedFinding = async () => {
    if (!popup || !onAddCustomTerm) return;
    const current = popup;
    setPopup({ ...current, saving: true, error: null });
    try {
      await onAddCustomTerm({
        value: current.text,
        category: current.category,
        strategy: "PLACEHOLDER",
        ...(current.start != null ? { starts: [current.start] } : {}),
      });
      setAddedNote({ text: current.text, x: current.x, y: current.noteY });
      setPopup(null);
      window.getSelection()?.removeAllRanges();
    } catch {
      setPopup({ ...current, saving: false, error: t("workspace.addFindingFailed") });
    }
  };

  if (isPdf) {
    return (
      <div className="document-viewer">
        <PdfPageViewer
          jobId={jobId}
          pageCount={pageCount}
            entities={entities}
          decisions={decisions}
          categoryDefaults={categoryDefaults}
          entityStrategies={entityStrategies}
          manual={manual}
          selectedManualId={selectedManualId}
          activeId={activeId}
          flashEntityIds={flashEntityIds}
          focusId={focusId}
          focusRectIndex={focusRectIndex}
          currentPage={currentPage}
          viewMode={viewMode}
          showPreserved={showPreserved}
          tool={tool}
          pageWidth={pageWidth}
          language={language}
          initialsFontSize={initialsFontSize}
          initialPages={pageSpans}
          pagePreviews={pagePreviews}
          pageLabel={(current, total) =>
            t("reviewPageLabel", { current, total })
          }
          onSelect={onSelect}
          onSelectManual={onSelectManual}
          onPageInView={onPageInView}
          onDrawComplete={onAreaDrawn}
          boxOverrides={boxOverrides}
          entityFills={entityFills}
          onBoxResize={onBoxResize}
          onManualBoxResize={onManualBoxResize}
          heldDraft={heldDraft}
          onFindingContextMenu={onFindingContextMenu}
        />
      </div>
    );
  }

  const sourcePages = pdfSourcePageTexts(documentKind, text, pageTexts);
  const pageBodies = renderPreview({
    parts: shownParts,
    decisions,
    categoryDefaults,
    entityStrategies,
    viewMode,
    showPreserved,
    language,
    t,
    activeId,
    flashEntityIds,
    onSelect,
    boundaries: textPageBoundaries(text, sourcePages),
    initialsFontSize,
    entityFills,
    onFindingContextMenu,
  });

  return (
    <div className="document-viewer document-viewer-text">
      <div
        ref={sheetRef}
        className={`text-workspace${selectMode ? " is-selecting" : ""}`}
        style={textWorkspaceCanvasStyle}
        onMouseUp={handleMouseUp}
      >
        {pageBodies.map((nodes, index) => {
          const pageText = (sourcePages ?? [text])[index] ?? "";
          const layout = usablePdfTextLayout(
            documentKind,
            pageText,
            pageLayouts?.find((item) => item.page === index),
          );
          return (
            <article
              key={sourcePages ? `source-page-${index}` : "text-document"}
              id={sourcePages ? `pdf-page-${index + 1}` : undefined}
              className={`sheet text-doc-page${layout ? " is-flow" : ""}${selectMode ? " select-mode" : ""}`}
              style={layout ? textFlowPageStyle : textDocumentPageStyle}
              data-pdf-source-page={sourcePages ? index + 1 : undefined}
              data-text-flow={layout ? "true" : undefined}
              aria-label={t("documentViewLabel")}
            >
              {layout
                ? flowingPageNodes({
                    pageText,
                    pageOffset: textPageBoundaries(text, sourcePages)[index] ?? 0,
                    layout,
                    parts: shownParts,
                    decisions,
                    categoryDefaults,
                    entityStrategies,
                    viewMode,
                    showPreserved,
                    language,
                    t,
                    activeId,
                    flashEntityIds,
                    onSelect,
                    initialsFontSize,
                    entityFills,
                    onFindingContextMenu,
                  })
                : nodes}
            </article>
          );
        })}
        {viewMode === "detections" && onEditSpan && activeId && (
          <TextSpanHandles
            sheetRef={sheetRef}
            entity={shownEntities.find((item) => item.id === activeId) ?? null}
            others={entities}
            text={text}
            labelStart={t("workspace.spanDragStart")}
            labelEnd={t("workspace.spanDragEnd")}
            onPreview={setLiveSpan}
            onCommit={async (span) => {
              const current = entities.find((item) => item.id === span.id);
              if (!current || (current.start === span.start && current.end === span.end)) {
                setLiveSpan(null);
                return;
              }
              try {
                await onEditSpan(span.id, span.start, span.end);
              } finally {
                setLiveSpan(null);
              }
            }}
          />
        )}
        {popup && (
            <div
              className={`selection-popup selection-popup-compact${popup.place === "above" ? " is-above" : ""}`}
              style={{ left: popup.x, top: popup.y }}
              onMouseDown={(event) => {
                const target = event.target;
                if (target instanceof Element && target.closest("button")) return;
                event.preventDefault();
              }}
            >
              <p className="selection-popup-text">
                «
                {popup.text.length > 40
                  ? `${popup.text.slice(0, 40)}…`
                  : popup.text}
                »
              </p>
              <div className="selection-popup-actions">
                <button
                  type="button"
                  className="selection-popup-category-btn"
                  aria-expanded={popup.categoryOpen}
                  aria-label={t("category")}
                  disabled={popup.saving}
                  onClick={() =>
                    setPopup((current) =>
                      current ? { ...current, categoryOpen: !current.categoryOpen } : current,
                    )
                  }
                >
                  <span>{t(`categories.${popup.category}`, { defaultValue: popup.category })}</span>
                  <span aria-hidden="true">{popup.categoryOpen ? "▴" : "▾"}</span>
                </button>
                <button
                  type="button"
                  className="selection-popup-add"
                  disabled={popup.saving || !onAddCustomTerm}
                  onClick={() => void addSelectedFinding()}
                >
                  {popup.saving ? t("workspace.customSearchSaving") : t("workspace.addSelectionFinding")}
                </button>
              </div>
              {popup.categoryOpen && (
                <div className="selection-popup-types" role="listbox" aria-label={t("category")}>
                  {presentationTypeOptions().reduce<Array<{ id: string; types: string[] }>>((groups, type) => {
                    const id = presentationGroupForEntityType(type);
                    const last = groups[groups.length - 1];
                    if (last?.id === id) last.types.push(type);
                    else groups.push({ id, types: [type] });
                    return groups;
                  }, []).map((group) => (
                    <div key={group.id}>
                      <p className="selection-popup-family">{t(presentationGroupLabelKey(group.id))}</p>
                      {group.types.map((type) => (
                        <button
                          key={type}
                          type="button"
                          role="option"
                          aria-selected={popup.category === type}
                          className={popup.category === type ? "is-selected" : undefined}
                          onClick={() =>
                            setPopup((current) =>
                              current
                                ? { ...current, category: type, categoryOpen: false, error: null }
                                : current,
                            )
                          }
                        >
                          {t(`categories.${type}`, { defaultValue: type })}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
              {popup.error && <p className="selection-popup-error">{popup.error}</p>}
            </div>
        )}
        {addedNote && (
          <p className="selection-added-note" style={{ left: addedNote.x, top: addedNote.y }}>
            {t("workspace.findingAddedOnDocument")}
          </p>
        )}
      </div>
    </div>
  );
}

/** A click selects the finding. Right-click still opens its menu. */
function textFindingHandlers(
  entityId: string,
  onSelect: (id: string | null) => void,
  onFindingContextMenu?: (entityId: string, clientX: number, clientY: number) => void,
) {
  return {
    onClick: () => onSelect(entityId),
    onContextMenu: (event: MouseEvent<HTMLButtonElement>) => {
      if (!onFindingContextMenu) return;
      event.preventDefault();
      event.stopPropagation();
      onSelect(entityId);
      onFindingContextMenu(entityId, event.clientX, event.clientY);
    },
  };
}

function renderPreview({
  parts,
  decisions,
  categoryDefaults,
  entityStrategies,
  viewMode,
  showPreserved = false,
  language,
  t,
  activeId,
  flashEntityIds = [],
  onSelect,
  boundaries,
  initialsFontSize,
  entityFills,
  onFindingContextMenu,
}: {
  parts: TextPart[];
  decisions: Decisions;
  categoryDefaults: CategoryDefaults;
  entityStrategies: EntityStrategies;
  viewMode: DocumentViewMode;
  showPreserved?: boolean;
  language: string;
  t: (key: string, options?: Record<string, unknown>) => string;
  activeId: string | null;
  flashEntityIds?: string[];
  onSelect: (id: string | null) => void;
  boundaries: number[];
  initialsFontSize: number;
  entityFills?: Record<string, string>;
  onFindingContextMenu?: (
    entityId: string,
    clientX: number,
    clientY: number,
    rectIndex?: number,
  ) => void;
}) {
  const entities = parts
    .map((part) => part.entity)
    .filter((item): item is Entity => Boolean(item));
  const pageCount = Math.max(1, boundaries.length - 1);
  const buckets: ReactNode[][] = Array.from({ length: pageCount }, () => []);
  let globalOffset = 0;

  const pushPlain = (start: number, value: string, key: string) => {
    let cursor = 0;
    while (cursor < value.length) {
      const absolute = start + cursor;
      const page = pageIndexAt(boundaries, absolute);
      const pageEnd = boundaries[page + 1] ?? start + value.length;
      const take = Math.min(value.length - cursor, pageEnd - absolute);
      if (take <= 0) break;
      buckets[page].push(
        <span key={`${key}-${cursor}`}>{value.slice(cursor, cursor + take)}</span>,
      );
      cursor += take;
    }
  };

  const pushPaper = (start: number, value: string, key: string, entityId?: string) => {
    let cursor = 0;
    let labeled = false;
    while (cursor < value.length) {
      const absolute = start + cursor;
      const page = pageIndexAt(boundaries, absolute);
      const pageEnd = boundaries[page + 1] ?? start + value.length;
      const take = Math.min(value.length - cursor, pageEnd - absolute);
      if (take <= 0) break;
      const slice = value.slice(cursor, cursor + take);
      const mark = !labeled && Boolean(entityId);
      labeled = labeled || mark;
      buckets[page].push(
        <button
          key={`${key}-${cursor}`}
          id={mark ? `entity-${entityId}` : undefined}
          type="button"
          className={[
            "doc-entity",
            "view-preview",
            "is-redact",
            "is-paper-redact",
            entityId && activeId === entityId ? "is-active" : "",
            entityId && flashEntityIds.includes(entityId) ? "is-flash" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          style={textDocumentEntityStyle}
          title={slice}
          {...(entityId
            ? textFindingHandlers(entityId, onSelect, onFindingContextMenu)
            : { onClick: () => undefined })}
        >
          <span className="doc-redact-bar" aria-label={t("strategies.REDACT")}>
            <span className="doc-redact-mask" aria-hidden>
              {slice}
            </span>
            <span className="doc-redact-reveal">{slice}</span>
          </span>
        </button>,
      );
      cursor += take;
    }
  };

  parts.forEach((part, i) => {
    if (part.paperHeader) {
      pushPaper(globalOffset, part.text, `paper-${i}`, part.entity?.id);
      globalOffset += part.text.length;
      return;
    }
    const partStart = part.entity ? part.entity.start : globalOffset;
    if (!part.entity) {
      pushPlain(partStart, part.text, `t-${i}`);
    } else {
      const strategy = effectiveStrategy(
        part.entity,
        decisions,
        categoryDefaults,
        entityStrategies,
      );
      const kept = strategy === "KEEP";
      if (!showDetectionOverlay(part.entity, strategy, viewMode, showPreserved)) {
        pushPlain(part.entity.start, part.text, `t-${i}`);
      } else {
      const preview = previewEntityValue(
        part.text,
        part.entity.type,
        strategy,
        language,
        {
          role: part.entity.role,
          placeholderToken: part.entity.placeholder_token,
          entity: part.entity,
          entities,
        },
      );
      const initialsPreview =
        viewMode === "preview" &&
        strategy === "INITIALS" &&
        !kept;
      const pointSize = initialsPointSize(part.entity, initialsFontSize);
      const fillOverride = entityFills?.[part.entity.id];
      const paperRedact =
        strategy === "REDACT" &&
        viewMode === "preview" &&
        usesPaperRedaction(part.entity.type, part.entity.attributes) &&
        !fillOverride;
      const redactFill =
        strategy === "REDACT" && viewMode === "preview"
          ? (fillOverride ??
            defaultRedactFill(
              usesPaperRedaction(part.entity.type, part.entity.attributes),
            ))
          : undefined;
      buckets[pageIndexAt(boundaries, part.entity.start)].push(
        <button
          key={part.entity.id}
          id={`entity-${part.entity.id}`}
          type="button"
          className={[
            "doc-entity",
            `view-${viewMode}`,
            kept ? "is-kept is-preserved" : categoryAccent(part.entity.type),
            strategy === "REDACT" && viewMode === "preview" ? "is-redact" : "",
            paperRedact ? "is-paper-redact" : "",
            initialsPreview ? "is-initials" : "",
            activeId === part.entity.id ? "is-active" : "",
            flashEntityIds.includes(part.entity.id) ? "is-flash" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          style={
            redactFill
              ? {
                  ...textDocumentEntityStyle,
                  background: redactFill,
                  color: redactFill,
                }
              : textDocumentEntityStyle
          }
          title={
            viewMode === "preview" && !kept
              ? part.text
              : t("workspace.toggleMaskHint")
          }
          {...textFindingHandlers(part.entity.id, onSelect, onFindingContextMenu)}
        >
          {viewMode === "preview" && !kept ? (
            strategy === "REDACT" ? (
              <span
                className="doc-redact-bar"
                aria-label={t("strategies.REDACT")}
                style={
                  redactFill
                    ? { background: redactFill, color: redactFill }
                    : undefined
                }
              >
                <span className="doc-redact-mask" aria-hidden>
                  {preview}
                </span>
                <span className="doc-redact-reveal">{part.text}</span>
              </span>
            ) : (
              <span className="doc-mask-pair">
                <span className="doc-mask-face">
                  {initialsPreview ? (
                    <span
                      className="doc-initials-label"
                      style={{
                        fontFamily: fontCss("times"),
                        fontSize: `${pointSize}pt`,
                      }}
                    >
                      {preview}
                    </span>
                  ) : (
                    preview || t("workspace.suppressed")
                  )}
                </span>
                <span className="doc-redact-reveal">{part.text}</span>
              </span>
            )
          ) : (
            part.text
          )}
        </button>,
      );
      }
    }
    globalOffset += part.text.length;
  });

  return buckets;
}

function flowingPageNodes({
  pageText,
  pageOffset,
  layout,
  parts,
  decisions,
  categoryDefaults,
  entityStrategies,
  viewMode,
  showPreserved = false,
  language,
  t,
  activeId,
  flashEntityIds = [],
  onSelect,
  initialsFontSize,
  entityFills,
  onFindingContextMenu,
}: {
  pageText: string;
  pageOffset: number;
  layout: PdfTextLayout;
  parts: TextPart[];
  decisions: Decisions;
  categoryDefaults: CategoryDefaults;
  entityStrategies: EntityStrategies;
  viewMode: DocumentViewMode;
  showPreserved?: boolean;
  language: string;
  t: (key: string, options?: Record<string, unknown>) => string;
  activeId: string | null;
  flashEntityIds?: string[];
  onSelect: (id: string | null) => void;
  initialsFontSize: number;
  entityFills?: Record<string, string>;
  onFindingContextMenu?: (
    entityId: string,
    clientX: number,
    clientY: number,
    rectIndex?: number,
  ) => void;
}) {
  const entities = parts
    .map((part) => part.entity)
    .filter((item): item is Entity => Boolean(item));
  const seenEntities = new Set<string>();
  const lines = flowTextLines(pageText, layout);

  const renderPiece = (piece: FlowPiece, key: string) => {
    if (piece.kind !== "text") {
      return (
        <span key={key} className={piece.kind === "join" ? "text-flow-join" : "text-flow-break"}>
          {piece.text}
        </span>
      );
    }
    const absStart = pageOffset + piece.localStart;
    const absEnd = pageOffset + piece.localEnd;
    const nodes: ReactNode[] = [];
    let cursor = absStart;
    let offset = 0;
    for (const part of parts) {
      const partStart = offset;
      const partEnd = offset + part.text.length;
      offset = partEnd;
      const from = Math.max(partStart, absStart);
      const to = Math.min(partEnd, absEnd);
      if (to <= from) continue;
      const slice = part.text.slice(from - partStart, to - partStart);
      if (part.paperHeader) {
        const entityId = part.entity?.id;
        const first = entityId ? !seenEntities.has(entityId) : false;
        if (entityId && first) seenEntities.add(entityId);
        nodes.push(
          <button
            key={`${key}-${from}`}
            id={first && entityId ? `entity-${entityId}` : undefined}
            type="button"
            className={[
              "doc-entity",
              "view-preview",
              "is-redact",
              "is-paper-redact",
              entityId && activeId === entityId ? "is-active" : "",
              entityId && flashEntityIds.includes(entityId) ? "is-flash" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={textDocumentEntityStyle}
            title={slice}
            {...(entityId
              ? textFindingHandlers(entityId, onSelect, onFindingContextMenu)
              : { onClick: () => undefined })}
          >
            <span className="doc-redact-bar" aria-label={t("strategies.REDACT")}>
              <span className="doc-redact-mask" aria-hidden>
                {slice}
              </span>
              <span className="doc-redact-reveal">{slice}</span>
            </span>
          </button>,
        );
        cursor = to;
        continue;
      }
      if (!part.entity || !showDetectionOverlay(
        part.entity,
        effectiveStrategy(part.entity, decisions, categoryDefaults, entityStrategies),
        viewMode,
        showPreserved,
      )) {
        nodes.push(
          <span key={`${key}-${from}`} className="text-flow-text">
            {slice}
          </span>,
        );
        cursor = to;
        continue;
      }
      const entity = part.entity;
      const strategy = effectiveStrategy(entity, decisions, categoryDefaults, entityStrategies);
      const kept = strategy === "KEEP";
      const first = !seenEntities.has(entity.id);
      seenEntities.add(entity.id);
      const preview = first
        ? previewEntityValue(entity.text, entity.type, strategy, language, {
            role: entity.role,
            placeholderToken: entity.placeholder_token,
            entity,
            entities,
          })
        : "";
      const initialsPreview = viewMode === "preview" && strategy === "INITIALS" && !kept && first;
      const pointSize = initialsPointSize(entity, initialsFontSize);
      const fillOverride = entityFills?.[entity.id];
      const paperRedact =
        strategy === "REDACT" &&
        viewMode === "preview" &&
        usesPaperRedaction(entity.type, entity.attributes) &&
        !fillOverride;
      const redactFill =
        strategy === "REDACT" && viewMode === "preview"
          ? (fillOverride ?? defaultRedactFill(usesPaperRedaction(entity.type, entity.attributes)))
          : undefined;
      nodes.push(
        <button
          key={`${key}-${from}`}
          id={first ? `entity-${entity.id}` : undefined}
          type="button"
          className={[
            "doc-entity",
            `view-${viewMode}`,
            kept ? "is-kept is-preserved" : categoryAccent(entity.type),
            strategy === "REDACT" && viewMode === "preview" ? "is-redact" : "",
            paperRedact ? "is-paper-redact" : "",
            initialsPreview ? "is-initials" : "",
            activeId === entity.id ? "is-active" : "",
            flashEntityIds.includes(entity.id) ? "is-flash" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          style={
            redactFill
              ? { ...textDocumentEntityStyle, background: redactFill, color: redactFill }
              : textDocumentEntityStyle
          }
          title={viewMode === "preview" && !kept ? slice : t("workspace.toggleMaskHint")}
          {...textFindingHandlers(entity.id, onSelect, onFindingContextMenu)}
        >
          {viewMode === "preview" && !kept ? (
            strategy === "REDACT" ? (
              <span
                className="doc-redact-bar"
                aria-label={t("strategies.REDACT")}
                style={redactFill ? { background: redactFill, color: redactFill } : undefined}
              >
                <span className="doc-redact-mask" aria-hidden>
                  {preview}
                </span>
                <span className="doc-redact-reveal">{slice}</span>
              </span>
            ) : (
              <span className="doc-mask-pair">
                <span className="doc-mask-face">{
                  initialsPreview ? (
                    <span
                      className="doc-initials-label"
                      style={{ fontFamily: fontCss("times"), fontSize: `${pointSize}pt` }}
                    >
                      {preview}
                    </span>
                  ) : (
                    preview || (first ? t("workspace.suppressed") : "")
                  )
                }</span>
                <span className="doc-redact-reveal">{slice}</span>
              </span>
            )
          ) : (
            slice
          )}
        </button>,
      );
      cursor = to;
    }
    if (cursor < absEnd) {
      nodes.push(
        <span key={`${key}-rest`} className="text-flow-text">
          {pageText.slice(cursor - pageOffset, piece.localEnd)}
        </span>,
      );
    }
    return nodes;
  };

  return lines.map((line, lineIndex) => {
    const className = [
      "text-flow-line",
      line.align === "center" ? "is-center" : "",
      line.align === "form" ? "is-form" : "",
      line.align === "blank" ? "is-blank" : "",
    ]
      .filter(Boolean)
      .join(" ");
    if (line.align === "form" && line.valueFrom > 0) {
      return (
        <div key={`flow-${lineIndex}`} className={className}>
          <span className="text-flow-label">
            {line.pieces.slice(0, line.valueFrom).map((piece, index) =>
              renderPiece(piece, `${lineIndex}-l-${index}`),
            )}
          </span>
          <span className="text-flow-value">
            {line.pieces.slice(line.valueFrom).map((piece, index) =>
              renderPiece(piece, `${lineIndex}-v-${index}`),
            )}
          </span>
        </div>
      );
    }
    return (
      <div key={`flow-${lineIndex}`} className={className}>
        {line.pieces.map((piece, index) => renderPiece(piece, `${lineIndex}-${index}`))}
      </div>
    );
  });
}

type LiveSpan = { id: string; start: number; end: number }

function TextSpanHandles({
  sheetRef,
  entity,
  others,
  text,
  labelStart,
  labelEnd,
  onPreview,
  onCommit,
}: {
  sheetRef: RefObject<HTMLDivElement | null>
  entity: Entity | null
  others: Entity[]
  text: string
  labelStart: string
  labelEnd: string
  onPreview: (span: LiveSpan) => void
  onCommit: (span: LiveSpan) => void
}) {
  const [edges, setEdges] = useState<{ start: { x: number; y: number }; end: { x: number; y: number } } | null>(null)
  const liveRef = useRef<LiveSpan | null>(null)

  const measure = useCallback(() => {
    const sheet = sheetRef.current
    const node = entity ? document.getElementById(`entity-${entity.id}`) : null
    if (!sheet || !node || !sheet.contains(node)) {
      setEdges(null)
      return
    }
    const rects = [...node.getClientRects()].filter((rect) => rect.width > 0 || rect.height > 0)
    const first = rects[0]
    const last = rects[rects.length - 1]
    if (!first || !last) {
      setEdges(null)
      return
    }
    setEdges({
      start: { x: first.left, y: first.top + first.height / 2 },
      end: { x: last.right, y: last.top + last.height / 2 },
    })
  }, [entity, sheetRef])

  useLayoutEffect(() => {
    measure()
    window.addEventListener("scroll", measure, true)
    window.addEventListener("resize", measure)
    return () => {
      window.removeEventListener("scroll", measure, true)
      window.removeEventListener("resize", measure)
    }
  }, [measure, entity?.start, entity?.end, entity?.text])

  if (!entity || !edges) return null

  const begin = (edge: "start" | "end", event: ReactPointerEvent<HTMLSpanElement>) => {
    event.preventDefault()
    event.stopPropagation()
    const origin = { start: entity.start, end: entity.end }
    liveRef.current = { id: entity.id, ...origin }
    document.body.classList.add("is-span-dragging")
    const move = (moveEvent: PointerEvent) => {
      const sheet = sheetRef.current
      if (!sheet) return
      const offset = sourceOffsetAtPoint(sheet, moveEvent.clientX, moveEvent.clientY)
      if (offset == null) return
      const next = edge === "end"
        ? { start: origin.start, end: offset }
        : { start: offset, end: origin.end }
      if (next.start < 0 || next.end > text.length || next.start >= next.end) return
      if (spanStepOverlaps(next, entity.id, others)) return
      const span = { id: entity.id, ...next }
      liveRef.current = span
      onPreview(span)
    }
    const up = () => {
      window.removeEventListener("pointermove", move)
      window.removeEventListener("pointerup", up)
      document.body.classList.remove("is-span-dragging")
      const span = liveRef.current
      if (span) onCommit(span)
    }
    window.addEventListener("pointermove", move)
    window.addEventListener("pointerup", up)
  }

  return (
    <>
      {(["start", "end"] as const).map((edge) => (
        <span
          key={edge}
          className={`text-span-resize is-${edge}`}
          role="slider"
          aria-label={edge === "start" ? labelStart : labelEnd}
          style={{ left: edges[edge].x - 5, top: edges[edge].y - 5 }}
          onPointerDown={(event) => begin(edge, event)}
        />
      ))}
    </>
  )
}

function sourceOffsetForRange(sheet: HTMLElement, range: Range): number | null {
  const walker = document.createTreeWalker(sheet, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = (node as Text).parentElement;
      if (!parent || parent.closest(".selection-popup, .doc-mask-face, .doc-redact-mask, .text-span-resize")) {
        return NodeFilter.FILTER_REJECT;
      }
      if (
        parent.classList.contains("text-doc-page") ||
        parent.classList.contains("text-workspace")
      ) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let offset = 0;
  let node = walker.nextNode();
  while (node) {
    if (node === range.startContainer) return offset + range.startOffset;
    offset += node.textContent?.length ?? 0;
    node = walker.nextNode();
  }
  return null;
}

function caretRangeAt(clientX: number, clientY: number): Range | null {
  const doc = document as Document & {
    caretRangeFromPoint?: (x: number, y: number) => Range | null
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null
  }
  const direct = doc.caretRangeFromPoint?.(clientX, clientY)
  if (direct) return direct
  const position = doc.caretPositionFromPoint?.(clientX, clientY)
  if (!position) return null
  const range = document.createRange()
  range.setStart(position.offsetNode, position.offset)
  range.collapse(true)
  return range
}

function sourceOffsetAtPoint(sheet: HTMLElement, clientX: number, clientY: number): number | null {
  const range = caretRangeAt(clientX, clientY)
  if (!range || !sheet.contains(range.startContainer)) return null
  return sourceOffsetForRange(sheet, range)
}

function selectionStartInDocument(
  sheet: HTMLElement,
  range: Range,
  documentText: string,
  selected: string,
): number | null {
  return offsetsForSelectedSource(documentText, selected, sourceOffsetForRange(sheet, range))?.start ?? null
}
