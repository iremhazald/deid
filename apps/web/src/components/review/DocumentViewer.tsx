import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  categoryAccent,
  effectiveStrategy,
  initialsPointSize,
  previewEntityValue,
  showDetectionOverlay,
  usesPaperRedaction,
} from "../../state/helpers";
import { shouldOpenDocumentContextMenu } from "../../state/findingContextMenu";
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

type SelectionPopup = {
  text: string;
  x: number;
  y: number;
  step: "actions" | "label";
  customLabel: string;
  start?: number;
};

type Props = {
  jobId: string;
  documentKind?: string;
  pageCount?: number;
  pageTexts?: string[];
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
};

export function DocumentViewer({
  jobId,
  documentKind,
  pageCount = 1,
  pageTexts,
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
  onManualAdd,
  onAreaDrawn,
  onAddCustomTerm,
  flashEntityIds = [],
  boxOverrides,
  entityFills,
  onBoxResize,
  onManualBoxResize,
  heldDraft,
  onFindingContextMenu,
}: Props) {
  const isPdf = documentKind === "PDF";
  const [popup, setPopup] = useState<SelectionPopup | null>(null);
  const sheetRef = useRef<HTMLElement>(null);
  const selectMode = tool === "select-text";

  const parts = useMemo(() => {
    const result: Array<{ text: string; entity?: Entity }> = [];
    let cursor = 0;
    const sorted = [...entities].sort(
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
  }, [text, entities]);

  useEffect(() => {
    if (!activeId || isPdf) return;
    document.getElementById(`entity-${activeId}`)?.scrollIntoView({
      block: "nearest",
      behavior: "smooth",
    });
  }, [activeId, isPdf]);

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

  const handleMouseUp = useCallback(() => {
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
    setPopup({
      text: selected,
      x: rect.left - sheetRect.left + rect.width / 2,
      y: rect.bottom - sheetRect.top + 6,
      step: "actions",
      customLabel: "",
      ...(start != null ? { start } : {}),
    });
  }, [selectMode, text]);

  const hideSelection = (replacement?: string, scope: "occurrence" | "all" = "all") => {
    if (!popup) return;
    const occurrenceStart = scope === "occurrence" ? popup.start : undefined;
    onManualAdd({
      text: popup.text,
      page: currentPage,
      replacement,
      ...(occurrenceStart != null
        ? { start: occurrenceStart, end: occurrenceStart + popup.text.length }
        : {}),
    });
    setPopup(null);
    window.getSelection()?.removeAllRanges();
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

  return (
    <div className="document-viewer">
      {selectMode && <p className="select-mode-hint">{t("selectModeHint")}</p>}
      <div className="sheet-wrapper">
        <article
          ref={sheetRef}
          className={`sheet${selectMode ? " select-mode" : ""}`}
          aria-label={t("documentViewLabel")}
          onMouseUp={handleMouseUp}
        >
          {renderPreview({
            parts,
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
            pageTexts,
            initialsFontSize,
            entityFills,
            onFindingContextMenu,
          })}
          {popup && (
            <div
              className="selection-popup selection-popup-compact"
              style={{ left: popup.x, top: popup.y }}
            >
              <p className="selection-popup-text">
                «
                {popup.text.length > 40
                  ? `${popup.text.slice(0, 40)}…`
                  : popup.text}
                »
              </p>
              {popup.step === "actions" ? (
                <div className="selection-popup-actions-stack">
                  <button type="button" onClick={() => hideSelection(undefined, "occurrence")}>
                    {t("workspace.hideThisPhrase")}
                  </button>
                  <button type="button" onClick={() => hideSelection()}>
                    {t("workspace.hideAllMatches")}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      hideSelection(
                        previewEntityValue(popup.text, "PERSON_NAME", "INITIALS", language),
                      )
                    }
                  >
                    {t("workspace.showInitials")}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPopup((current) =>
                        current ? { ...current, step: "label" } : current,
                      )
                    }
                  >
                    {t("workspace.replaceWithLabel")}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPopup((current) =>
                        current ? { ...current, step: "label" } : current,
                      )
                    }
                  >
                    {t("workspace.replaceWithCustom")}
                  </button>
                  {onAddCustomTerm && (
                    <button
                      type="button"
                      onClick={() => {
                        onAddCustomTerm({
                          value: popup.text,
                          category: "PERSON_NAME",
                          strategy: "PLACEHOLDER",
                        })
                        setPopup(null)
                        window.getSelection()?.removeAllRanges()
                      }}
                    >
                      {t("workspace.addAsCustomTerm")}
                    </button>
                  )}
                </div>
              ) : (
                <div className="selection-popup-label">
                  {["[KİŞİ_1]", "[KURUM_1]", "[ÖZEL_1]"].map((token) => (
                    <button
                      key={token}
                      type="button"
                      onClick={() => hideSelection(token)}
                    >
                      {token}
                    </button>
                  ))}
                  <input
                    type="text"
                    value={popup.customLabel}
                    placeholder={t("workspace.customLabelHint")}
                    onChange={(event) =>
                      setPopup((current) =>
                        current
                          ? { ...current, customLabel: event.target.value }
                          : current,
                      )
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && popup.customLabel.trim()) {
                        hideSelection(popup.customLabel.trim());
                      }
                    }}
                  />
                  <button
                    type="button"
                    className="btn primary"
                    disabled={!popup.customLabel.trim()}
                    onClick={() => hideSelection(popup.customLabel.trim())}
                  >
                    {t("workspace.applyArea")}
                  </button>
                </div>
              )}
            </div>
          )}
        </article>
      </div>
    </div>
  );
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
  pageTexts,
  initialsFontSize,
  entityFills,
  onFindingContextMenu,
}: {
  parts: Array<{ text: string; entity?: Entity }>;
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
  pageTexts?: string[];
  initialsFontSize: number;
  entityFills?: Record<string, string>;
  onFindingContextMenu?: (
    entityId: string,
    clientX: number,
    clientY: number,
    rectIndex?: number,
  ) => void;
}) {
  const nodes: ReactNode[] = [];
  const entities = parts
    .map((part) => part.entity)
    .filter((item): item is Entity => Boolean(item));
  const pageOffsets: number[] = [];
  if (pageTexts && pageTexts.length > 1) {
    let off = 0;
    for (const pageText of pageTexts) {
      pageOffsets.push(off);
      off += pageText.length;
    }
  }
  let pageIdx = 0;
  let globalOffset = 0;

  parts.forEach((part, i) => {
    const partStart = part.entity ? part.entity.start : globalOffset;
    while (
      pageIdx + 1 < pageOffsets.length &&
      partStart >= pageOffsets[pageIdx + 1]
    ) {
      pageIdx++;
      nodes.push(
        <div
          key={`page-sep-${pageIdx}`}
          className="page-separator"
          id={`pdf-page-${pageIdx + 1}`}
        >
          <span>
            {t("page")} {pageIdx + 1}
          </span>
        </div>,
      );
    }

    if (!part.entity) {
      nodes.push(<span key={`t-${i}`}>{part.text}</span>);
    } else {
      const strategy = effectiveStrategy(
        part.entity,
        decisions,
        categoryDefaults,
        entityStrategies,
      );
      const kept = strategy === "KEEP";
      if (!showDetectionOverlay(part.entity, strategy, viewMode, showPreserved)) {
        nodes.push(<span key={`t-${i}`}>{part.text}</span>);
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
      nodes.push(
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
              ? { background: redactFill, color: redactFill }
              : undefined
          }
          title={
            viewMode === "preview" && !kept
              ? part.text
              : t("workspace.toggleMaskHint")
          }
          onClick={() => onSelect(part.entity!.id)}
          onContextMenu={(event) => {
            if (!shouldOpenDocumentContextMenu(viewMode, "select") || !onFindingContextMenu) {
              return;
            }
            event.preventDefault();
            event.stopPropagation();
            onFindingContextMenu(part.entity!.id, event.clientX, event.clientY);
          }}
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

  return nodes;
}

function selectionStartInDocument(
  sheet: HTMLElement,
  range: Range,
  documentText: string,
  selected: string,
): number | null {
  const walker = document.createTreeWalker(sheet, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = (node as Text).parentElement;
      if (parent?.closest(".page-separator, .selection-popup")) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let offset = 0;
  let node = walker.nextNode();
  while (node) {
    if (node === range.startContainer) {
      const start = offset + range.startOffset;
      if (documentText.slice(start, start + selected.length) === selected) {
        return start;
      }
      break;
    }
    offset += node.textContent?.length ?? 0;
    node = walker.nextNode();
  }
  const first = documentText.indexOf(selected);
  if (first < 0) return null;
  if (documentText.indexOf(selected, first + 1) < 0) return first;
  return null;
}
