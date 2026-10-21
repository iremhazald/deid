import { useCallback, useEffect, useRef, useState } from "react";
import {
  analysisStatusOf,
  effectiveStrategy,
  findManualById,
  isActionableFinding,
  manualItemId,
  relatedEntityIds,
  restoreStrategyFor,
  usesPaperRedaction,
} from "../../state/helpers";
import {
  DEFAULT_TEXT_SIZE,
  defaultRedactFill,
  TRANSPARENT_FILL,
} from "./documentFonts";
import type {
  Analysis,
  CategoryDefaults,
  DecisionAction,
  DecisionScope,
  Decisions,
  DocumentViewMode,
  EditorTool,
  EntityStrategies,
  ManualRect,
  ManualRedaction,
  OutputFormat,
  PrivacyProfile,
  TransformationStrategy,
  TransformCatalog,
  UserDefinedTerm,
} from "../../state/types";
import { DocumentViewer } from "./DocumentViewer";
import { FindingContextMenu } from "./FindingContextMenu";
import { ManualAreaPopover } from "./ManualAreaPopover";
import { placePopoverNearBox } from "./overlayScroll";
import { ReviewEditorToolbar } from "./ReviewEditorToolbar";
import { ReviewPanel } from "./ReviewPanel";
import { clampZoom, ZOOM_MAX, ZOOM_STEP } from "./zoom";
import {
  isMergeType,
  selectFindingOnContextClick,
  shouldOpenDocumentContextMenu,
} from "../../state/findingContextMenu";
import { personMergeRoleConflict } from "../../state/manualMerge";
import { showsPdfPageViewer } from "../../state/workspaceMode";

function newManualId() {
  return crypto.randomUUID();
}

const DETECTION_FOCUS_ZOOM = ZOOM_MAX;

type Snapshot = {
  decisions: Decisions;
  entityStrategies: EntityStrategies;
  categoryDefaults: CategoryDefaults;
  manual: ManualRedaction[];
  boxOverrides: Record<string, ManualRect[]>;
  entityFills: Record<string, string>;
  removedEntityIds: string[];
};

type Props = {
  analysis: Analysis;
  decisions: Decisions;
  categoryDefaults: CategoryDefaults;
  entityStrategies: EntityStrategies;
  catalog: TransformCatalog | null;
  previewText: string;
  activeId: string | null;
  profile: PrivacyProfile;
  outputFormat: OutputFormat;
  manual: ManualRedaction[];
  busy: boolean;
  language: string;
  initialsFontSize?: number;
  onInitialsFontSizeChange?: (size: number) => void;
  t: (key: string, options?: Record<string, unknown>) => string;
  onSelect: (id: string | null) => void;
  onDecision: (
    id: string,
    action: DecisionAction,
    scope?: DecisionScope,
  ) => void;
  onBulk: (ids: string[], action: DecisionAction) => void;
  onProfileChange: (profile: PrivacyProfile) => void;
  onCategoryDefault: (type: string, strategy: TransformationStrategy) => void;
  onEntityStrategy: (
    id: string,
    strategy: TransformationStrategy,
    scope?: DecisionScope,
  ) => void;
  onOutputFormatChange: (format: OutputFormat) => void;
  onManualChange: (items: ManualRedaction[]) => void;
  onRestoreState: (snapshot: Snapshot) => void;
  onAddCustomTerm?: (term: UserDefinedTerm) => void | Promise<void>;
  onMergeMatch?: (entityIds: string[]) => void | Promise<void>;
  onKeepSeparateMatch?: (entityIds: string[]) => void | Promise<void>;
  onReclassify?: (entityId: string, entityType: string) => void | Promise<void>;
  onEditSpan?: (entityId: string, start: number, end: number) => Promise<void>;
  flashEntityIds?: string[];
  boxOverrides?: Record<string, ManualRect[]>;
  entityFills?: Record<string, string>;
  onBoxResize?: (entityId: string, rectangles: ManualRect[]) => void;
  onEntityFill?: (entityId: string, fill: string) => void;
  removedEntityIds?: string[];
  onRemovedEntityIdsChange?: (ids: string[]) => void;
};

export function ReviewWorkspace(props: Props) {
  const {
    analysis,
    decisions,
    categoryDefaults,
    entityStrategies,
    catalog,
    activeId,
    manual,
    t,
    onSelect,
    onManualChange,
    onRestoreState,
    onDecision,
    onEntityStrategy,
    onCategoryDefault,
    onBulk,
  } = props;

  const textWorkspace = analysis.workspace_mode === "TEXT";
  const [tool, setTool] = useState<EditorTool>("select");
  const [viewMode, setViewMode] = useState<DocumentViewMode>("detections");
  const [showPreserved, setShowPreserved] = useState(false);
  const viewPinned = useRef(false);
  const [customZoom, setCustomZoom] = useState(1.2);
  const [pageWidth, setPageWidth] = useState(595);
  const [currentPage, setCurrentPage] = useState(1);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [focusRectIndex, setFocusRectIndex] = useState(0);
  const [selectedManualId, setSelectedManualId] = useState<string | null>(null);
  const [draftArea, setDraftArea] = useState<
    | ({
        page: number;
        mode: "redact" | "text";
        anchorX?: number;
        anchorY?: number;
        maxHeight?: number;
      } & ManualRect)
    | null
  >(null);
  const [contextMenu, setContextMenu] = useState<{
    entityId: string;
    x: number;
    y: number;
  } | null>(null);
  const [manualMergeSourceId, setManualMergeSourceId] = useState<string | null>(
    null,
  );
  const [mergeNotice, setMergeNotice] = useState<string | null>(null);
  const [removedToast, setRemovedToast] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const skipPopoverDismiss = useRef(0);
  const past = useRef<Snapshot[]>([]);
  const future = useRef<Snapshot[]>([]);
  const [, setHistoryTick] = useState(0);
  const flashEntityIds = props.flashEntityIds ?? [];
  const [panelFlashId, setPanelFlashId] = useState<string | null>(null);

  useEffect(() => {
    if (flashEntityIds.length === 0) return;
    setViewMode("detections");
    viewPinned.current = false;
  }, [flashEntityIds]);

  useEffect(() => {
    if (!panelFlashId) return;
    const timer = window.setTimeout(() => setPanelFlashId(null), 720);
    return () => window.clearTimeout(timer);
  }, [panelFlashId]);

  useEffect(() => {
    document.body.classList.toggle("is-finding-focus", tool === "select-text");
    return () => document.body.classList.remove("is-finding-focus");
  }, [tool]);

  useEffect(() => {
    viewPinned.current = false;
    setViewMode("detections");
    setShowPreserved(false);
    setContextMenu(null);
    setManualMergeSourceId(null);
    setMergeNotice(null);
    setRemovedToast(false);
    setTool("select");
  }, [analysis.job_id, analysis.workspace_mode]);

  const analysisStatus = analysisStatusOf(analysis);
  const extraWarnings = analysis.warnings.filter(
    (warning) => !warning.startsWith("AI_"),
  );
  const pdfDocumentWorkspace = showsPdfPageViewer(
    analysis.document_kind,
    analysis.workspace_mode,
  );
  const textSelectAvailable = !pdfDocumentWorkspace;

  const snapshot = useCallback(
    (): Snapshot => ({
      decisions,
      entityStrategies,
      categoryDefaults,
      manual,
      boxOverrides: props.boxOverrides ?? {},
      entityFills: props.entityFills ?? {},
      removedEntityIds: props.removedEntityIds ?? [],
    }),
    [
      decisions,
      entityStrategies,
      categoryDefaults,
      manual,
      props.boxOverrides,
      props.entityFills,
      props.removedEntityIds,
    ],
  );

  const record = useCallback(() => {
    past.current = [...past.current.slice(-199), snapshot()];
    future.current = [];
    setHistoryTick((value) => value + 1);
  }, [snapshot]);

  const undo = () => {
    const previous = past.current.pop();
    if (!previous) return;
    future.current.push(snapshot());
    onRestoreState(previous);
    setRemovedToast(false);
    setHistoryTick((value) => value + 1);
  };

  const redo = () => {
    const next = future.current.pop();
    if (!next) return;
    past.current.push(snapshot());
    onRestoreState(next);
    setHistoryTick((value) => value + 1);
  };

  const dismissManual = useCallback(() => {
    setTool("select");
    setDraftArea(null);
    setSelectedManualId(null);
    setFocusId(null);
    onSelect(null);
  }, [onSelect]);

  const clearDocumentSelection = useCallback(() => {
    setDraftArea(null);
    setSelectedManualId(null);
    setFocusId(null);
    onSelect(null);
  }, [onSelect]);

  const removeSelectedManual = useCallback(() => {
    if (!selectedManualId) return;
    record();
    onManualChange(
      manual.filter(
        (item, index) => manualItemId(item, index) !== selectedManualId,
      ),
    );
    setSelectedManualId(null);
  }, [manual, onManualChange, record, selectedManualId]);

  const markInspected = (id: string | null, rectIndex = 0) => {
    setSelectedManualId(null);
    if (!id) {
      setFocusId(null);
      onSelect(null);
      return;
    }
    onSelect(id);
    setFocusRectIndex(rectIndex);
    setFocusId(id);
    setCustomZoom(DETECTION_FOCUS_ZOOM);
    const entity = analysis.entities.find((item) => item.id === id);
    if (entity) setCurrentPage(entity.page + 1);
  };

  const selectFromPanel = (id: string | null, rectIndex = 0) => {
    markInspected(id, rectIndex);
    if (!id) return;
    setViewMode("detections");
    const entity = analysis.entities.find((item) => item.id === id);
    if (
      entity &&
      !isActionableFinding(entity, decisions, categoryDefaults, entityStrategies)
    ) {
      setShowPreserved(true);
    }
    setPanelFlashId(null);
    window.setTimeout(() => setPanelFlashId(id), 30);
  };

  const selectManualFromList = (id: string) => {
    setSelectedManualId(id);
    onSelect(null);
    const item = findManualById(manual, id);
    if (item) setCurrentPage(item.page);
  };

  const toggleDetectedMask = (id: string) => {
    const entity = analysis.entities.find((item) => item.id === id);
    if (!entity) return;
    const kept =
      effectiveStrategy(
        entity,
        decisions,
        categoryDefaults,
        entityStrategies,
      ) === "KEEP";
    wrap(onDecision)(id, kept ? "REDACT" : "KEEP");
  };

  const setManualKept = (id: string, kept: boolean) => {
    record();
    onManualChange(
      manual.map((item, index) =>
        manualItemId(item, index) === id ? { ...item, kept } : item,
      ),
    );
  };

  const removeSelectedMask = () => {
    if (selectedManualId) {
      setManualKept(selectedManualId, true);
      return;
    }
    if (activeId) wrap(onDecision)(activeId, "KEEP");
  };

  const restoreSelectedMask = () => {
    if (selectedManualId) {
      setManualKept(selectedManualId, false);
      return;
    }
    if (!activeId) return;
    const entity = analysis.entities.find((item) => item.id === activeId);
    if (!entity) return;
    const last = past.current[past.current.length - 1];
    const previousStrategy = last
      ? effectiveStrategy(
          entity,
          last.decisions,
          last.categoryDefaults,
          last.entityStrategies,
        )
      : "KEEP";
    const next =
      previousStrategy !== "KEEP"
        ? previousStrategy
        : restoreStrategyFor(entity, categoryDefaults, entityStrategies);
    record();
    onEntityStrategy(activeId, next);
  };

  const selectedManual = selectedManualId
    ? findManualById(manual, selectedManualId)
    : undefined;
  const selectedEntity = activeId
    ? analysis.entities.find((item) => item.id === activeId)
    : undefined;
  const selectedStrategy = selectedEntity
    ? effectiveStrategy(
        selectedEntity,
        decisions,
        categoryDefaults,
        entityStrategies,
      )
    : null;
  const selectedManualCurtain =
    Boolean(selectedManual) &&
    !selectedManual?.kept &&
    !selectedManual?.replacement &&
    selectedManual?.fill !== TRANSPARENT_FILL;
  const showFillPicker =
    viewMode === "preview" &&
    (selectedStrategy === "REDACT" || selectedManualCurtain);
  const selectedFill = selectedManualCurtain
    ? (selectedManual?.fill ?? defaultRedactFill())
    : selectedEntity
      ? (props.entityFills?.[selectedEntity.id] ??
        defaultRedactFill(
          usesPaperRedaction(selectedEntity.type, selectedEntity.attributes),
        ))
      : defaultRedactFill();

  const applySelectedFill = (color: string) => {
    if (selectedManualId && selectedManualCurtain) {
      record();
      onManualChange(
        manual.map((item, index) =>
          manualItemId(item, index) === selectedManualId
            ? { ...item, fill: color }
            : item,
        ),
      );
      return;
    }
    if (!activeId || selectedStrategy !== "REDACT") return;
    if ((props.entityFills?.[activeId] ?? selectedFill) === color) return;
    record();
    props.onEntityFill?.(activeId, color);
  };

  const handleUndo = () => {
    undo();
  };

  const handleRedo = () => {
    redo();
  };

  function wrap<Args extends unknown[]>(fn: (...args: Args) => void) {
    return (...args: Args) => {
      record();
      fn(...args);
    };
  }

  useEffect(() => {
    if (viewMode !== "preview") setContextMenu(null);
  }, [viewMode]);

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  const selectFindingQuietly = (id: string) => {
    setSelectedManualId(null);
    onSelect(selectFindingOnContextClick(activeId, id));
  };

  const openFindingContextMenu = (
    entityId: string,
    clientX: number,
    clientY: number,
    _rectIndex = 0,
  ) => {
    if (!textWorkspace && !shouldOpenDocumentContextMenu(viewMode, tool)) return;
    selectFindingQuietly(entityId);
    setManualMergeSourceId(null);
    setContextMenu({ entityId, x: clientX, y: clientY });
  };

  const contextEntity = contextMenu
    ? analysis.entities.find((item) => item.id === contextMenu.entityId)
    : undefined;

  const removeFindings = (entityIds: string[]) => {
    if (entityIds.length === 0) return;
    record();
    const removed = new Set(entityIds);
    const next = [...new Set([...(props.removedEntityIds ?? []), ...entityIds])];
    props.onRemovedEntityIdsChange?.(next);
    setContextMenu(null);
    if (activeId && removed.has(activeId)) onSelect(null);
    if (focusId && removed.has(focusId)) setFocusId(null);
    if (manualMergeSourceId && removed.has(manualMergeSourceId)) {
      setManualMergeSourceId(null);
    }
    setRemovedToast(true);
  };

  const removeFinding = (entityId: string) => removeFindings([entityId]);

  const startManualMerge = (entityId: string) => {
    const entity = analysis.entities.find((item) => item.id === entityId);
    if (!entity || !isMergeType(entity.type)) return;
    setContextMenu(null);
    selectFindingQuietly(entityId);
    setMergeNotice(null);
    setManualMergeSourceId(entityId);
  };

  const cancelManualMerge = useCallback(() => {
    setManualMergeSourceId(null);
    setMergeNotice(null);
  }, []);

  const mergeFromPanel = async (entityIds: string[]) => {
    const source = analysis.entities.find((item) => item.id === entityIds[0]);
    const target = analysis.entities.find((item) => item.id === entityIds[1]);
    const typesOf = (id: string) =>
      relatedEntityIds(id, analysis.entities)
        .map(
          (related) =>
            analysis.entities.find((item) => item.id === related)?.type,
        )
        .filter((type): type is string => Boolean(type));
    const conflict =
      source && target && isMergeType(source.type) && source.type !== "ADDRESS"
        ? personMergeRoleConflict(typesOf(source.id), typesOf(target.id))
        : false;
    await props.onMergeMatch?.(entityIds);
    setManualMergeSourceId(null);
    setMergeNotice(conflict ? t("workspace.manualMergeRoleConflict") : null);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const measure = () => {
      const first = analysis.page_spans?.[0];
      const nativeWidth = first && first.width > 0 ? first.width : 595;
      setPageWidth(Math.max(200, nativeWidth * customZoom));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [customZoom, analysis.page_spans]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.matches("input, textarea, select")) return;
      const meta = event.metaKey || event.ctrlKey;
      if (event.key === "r" || event.key === "R") {
        setTool((current) =>
          current === "redact-area" ? "select" : "redact-area",
        );
        return;
      }
      if (event.key === "t" || event.key === "T") {
        setTool((current) => (current === "add-text" ? "select" : "add-text"));
        return;
      }
      if (event.key === "Escape") {
        if (contextMenu) {
          setContextMenu(null);
          return;
        }
        if (manualMergeSourceId) {
          cancelManualMerge();
          return;
        }
        dismissManual();
        return;
      }
      if (
        (event.key === "Delete" || event.key === "Backspace") &&
        selectedManualId
      ) {
        event.preventDefault();
        removeSelectedManual();
        return;
      }
      if (event.key === "Enter" && (activeId || selectedManualId)) {
        event.preventDefault();
        if (selectedManualId) {
          const current = manual.find(
            (item, index) => manualItemId(item, index) === selectedManualId,
          );
          if (current?.kept) restoreSelectedMask();
          else removeSelectedMask();
          return;
        }
        toggleDetectedMask(activeId!);
        return;
      }
      if (meta && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) handleRedo();
        else handleUndo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  useEffect(() => {
    const exitFindingFocus = () => {
      setTool((current) => (current === "select-text" ? "select" : current));
      window.getSelection()?.removeAllRanges();
    };
    const onPointerDown = (event: PointerEvent) => {
      const raw = event.target;
      const target =
        raw instanceof Element
          ? raw
          : raw instanceof Node
            ? raw.parentElement
            : null;
      if (!target) return;
      if (tool === "select-text") {
        const onPage =
          target.closest(".text-doc-page") != null ||
          target.closest(".selection-popup") != null;
        const onToolbar = target.closest(".review-editor-toolbar") != null;
        if (event.button === 2 || (!onPage && !onToolbar)) exitFindingFocus();
      }
      if (Date.now() < skipPopoverDismiss.current) return;
      if (target.closest(".manual-area-pop")) return;
      if (target.closest(".selection-popup")) return;
      if (target.closest(".finding-context-menu")) return;
      if (target.closest(".manual-merge-panel")) return;
      if (target.closest(".toast.is-undo")) return;
      if (target.closest(".review-editor-toolbar")) return;
      const drawing =
        tool === "redact-area" || tool === "add-text" || Boolean(draftArea);
      if (drawing) {
        if (target.closest(".pdf-page-canvas") || target.closest(".sheet"))
          return;
        event.preventDefault();
        dismissManual();
        return;
      }
      if (target.closest(".pdf-resize") || target.closest(".text-span-resize")) return;
      if (target.closest(".pdf-entity") || target.closest(".doc-entity"))
        return;
      if (target.closest(".entity-mark") || target.closest(".is-manual"))
        return;
      if (
        target.closest(".finding-row") ||
        target.closest(".finding-identity") ||
        target.closest(".entity-main")
      )
        return;
      if (target.closest(".occurrence-list button")) return;
      clearDocumentSelection();
    };

    const onContextMenu = () => {
      if (tool === "select-text") exitFindingFocus();
    };
    window.addEventListener("pointerdown", onPointerDown, true);
    window.addEventListener("contextmenu", onContextMenu, true);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown, true);
      window.removeEventListener("contextmenu", onContextMenu, true);
    };
  }, [draftArea, tool, dismissManual, clearDocumentSelection]);

  const zoomPercent = Math.round(customZoom * 100);

  return (
    <div className="workspace">
      <ReviewEditorToolbar
        fileName={analysis.file_name}
        tool={tool}
        viewMode={viewMode}
        zoomPercent={zoomPercent}
        page={currentPage}
        pageCount={analysis.page_count}
        textSelectAvailable={textSelectAvailable}
        geometryTools={analysis.workspace_mode !== "TEXT"}
        t={t}
        onTool={(next) =>
          setTool((current) => (current === next ? "select" : next))
        }
        onViewMode={(mode) => {
          viewPinned.current = true;
          setViewMode(mode);
        }}
        hasSelectedDetection={Boolean(activeId)}
        showFillPicker={showFillPicker}
        selectedFill={selectedFill}
        onFillChange={applySelectedFill}
        canUndo={past.current.length > 0}
        canRedo={future.current.length > 0}
        onUndo={handleUndo}
        onRedo={handleRedo}
        onZoomOut={() => setCustomZoom((value) => clampZoom(value - ZOOM_STEP))}
        onZoomIn={() => setCustomZoom((value) => clampZoom(value + ZOOM_STEP))}
        onZoomReset={() => setCustomZoom(1)}
        onPageChange={setCurrentPage}
      />

      {extraWarnings.map((warning) => (
        <p className="notice toolbar-notice" key={warning}>
          {t("warning")}: {t(`messages.${warning}`, { defaultValue: warning })}
        </p>
      ))}

      <div className="review-body">
        <section
          className="review-canvas"
          ref={canvasRef}
          style={{ ["--page-width" as string]: `${pageWidth}px` }}
        >
          <DocumentViewer
            jobId={analysis.job_id}
            documentKind={analysis.document_kind}
            workspaceMode={analysis.workspace_mode}
            pageCount={analysis.page_count}
            pageTexts={analysis.page_texts}
            pageLayouts={analysis.page_layouts}
            pageSpans={analysis.page_spans}
            pagePreviews={analysis.page_previews}
            text={analysis.text}
            entities={analysis.entities}
            decisions={decisions}
            categoryDefaults={categoryDefaults}
            entityStrategies={entityStrategies}
            manual={manual}
            selectedManualId={selectedManualId}
            activeId={activeId}
            flashEntityIds={
              panelFlashId
                ? [...new Set([...flashEntityIds, panelFlashId])]
                : flashEntityIds
            }
            focusId={focusId}
            focusRectIndex={focusRectIndex}
            currentPage={currentPage}
            viewMode={viewMode}
            showPreserved={showPreserved}
            tool={tool}
            pageWidth={pageWidth}
            language={props.language}
            initialsFontSize={props.initialsFontSize ?? DEFAULT_TEXT_SIZE}
            t={t}
            onSelect={markInspected}
            onFindingContextMenu={openFindingContextMenu}
            onEditSpan={props.onEditSpan}
            onSelectManual={(id) => {
              setSelectedManualId(id);
              if (id) onSelect(null);
            }}
            onPageInView={setCurrentPage}
            onManualAdd={(item) => {
              record();
              onManualChange([
                ...manual,
                {
                  id: item.id ?? newManualId(),
                  text: item.text,
                  page: item.page ?? currentPage,
                  replacement: item.replacement,
                  start: item.start,
                  end: item.end,
                  fill: item.fill,
                  textColor: item.textColor,
                  font: item.font,
                  fontSize: item.fontSize,
                },
              ]);
              setTool(textSelectAvailable ? "select-text" : "select");
            }}
            heldDraft={
              draftArea
                ? {
                    page: draftArea.page,
                    x0: draftArea.x0,
                    y0: draftArea.y0,
                    x1: draftArea.x1,
                    y1: draftArea.y1,
                  }
                : null
            }
            onAddCustomTerm={props.onAddCustomTerm}
            boxOverrides={props.boxOverrides}
            entityFills={props.entityFills}
            onBoxResize={(entityId, rectangles) => {
              record();
              props.onBoxResize?.(entityId, rectangles);
            }}
            onManualBoxResize={(manualId, rectangles) => {
              record();
              onManualChange(
                manual.map((item, index) =>
                  manualItemId(item, index) === manualId
                    ? { ...item, rectangles }
                    : item,
                ),
              );
            }}
            onAreaDrawn={(rect) => {
              const mode = tool === "add-text" ? "text" : "redact";
              const popW = 320;
              const popH = 520;
              const vw = window.innerWidth;
              const vh = window.innerHeight;
              const layout = analysis.page_spans?.find(
                (page) => page.page === rect.page,
              );
              const pageEl = document.getElementById(
                `pdf-page-${rect.page + 1}`,
              );
              const canvas = pageEl?.querySelector(".pdf-page-canvas");
              const bounds = canvas?.getBoundingClientRect();
              const width =
                layout?.width && layout.width > 0 ? layout.width : 595;
              const height =
                layout?.height && layout.height > 0 ? layout.height : 842;
              const box = bounds
                ? {
                    left: bounds.left + (rect.x0 / width) * bounds.width,
                    top: bounds.top + (rect.y0 / height) * bounds.height,
                    right: bounds.left + (rect.x1 / width) * bounds.width,
                    bottom: bounds.top + (rect.y1 / height) * bounds.height,
                  }
                : {
                    left: (rect.clientX ?? 24) - 40,
                    top: (rect.clientY ?? 24) - 16,
                    right: rect.clientX ?? 80,
                    bottom: rect.clientY ?? 40,
                  };
              const place = placePopoverNearBox(
                box,
                { width: popW, height: popH },
                { width: vw, height: vh },
              );
              skipPopoverDismiss.current = Date.now() + 600;
              setDraftArea({
                ...rect,
                mode,
                anchorX: place.x,
                anchorY: place.y,
                maxHeight: place.maxHeight,
              });
            }}
          />
          {draftArea && (
            <ManualAreaPopover
              key={`${draftArea.mode}-${draftArea.page}-${draftArea.x0}-${draftArea.y0}`}
              page={draftArea.page + 1}
              rect={draftArea}
              left={draftArea.anchorX}
              top={draftArea.anchorY}
              maxHeight={draftArea.maxHeight}
              t={t}
              initialMode={draftArea.mode}
              onCancel={dismissManual}
              onConfirm={({
                replacement,
                category,
                fill,
                textColor,
                font,
                fontSize,
              }) => {
                const id = newManualId();
                record();
                onManualChange([
                  ...manual,
                  {
                    id,
                    text: `[AREA ${draftArea.page + 1}-${Math.round(draftArea.x0)}-${Math.round(draftArea.y0)}]`,
                    page: draftArea.page + 1,
                    replacement,
                    rectangles: [
                      {
                        x0: draftArea.x0,
                        y0: draftArea.y0,
                        x1: draftArea.x1,
                        y1: draftArea.y1,
                      },
                    ],
                    category,
                    fill,
                    textColor,
                    font,
                    fontSize,
                  },
                ]);
                setSelectedManualId(id);
                onSelect(null);
                setDraftArea(null);
                setTool("select");
              }}
            />
          )}
        </section>

        <ReviewPanel
          analysis={analysis}
          decisions={decisions}
          categoryDefaults={categoryDefaults}
          entityStrategies={entityStrategies}
          catalog={catalog}
          activeId={activeId}
          profile={props.profile}
          outputFormat={props.outputFormat}
          manual={manual}
          busy={props.busy}
          language={props.language}
          initialsFontSize={props.initialsFontSize ?? DEFAULT_TEXT_SIZE}
          onInitialsFontSizeChange={props.onInitialsFontSizeChange}
          t={t}
          onSelect={selectFromPanel}
          onSelectManual={selectManualFromList}
          selectedManualId={selectedManualId}
          onDecision={wrap(onDecision)}
          onBulk={wrap(onBulk)}
          onProfileChange={props.onProfileChange}
          onCategoryDefault={wrap(onCategoryDefault)}
          onEntityStrategy={wrap(onEntityStrategy)}
          onOutputFormatChange={props.onOutputFormatChange}
          onManualChange={(items) => {
            record();
            onManualChange(items);
          }}
          onAddCustomTerm={props.onAddCustomTerm}
          onMergeMatch={props.onMergeMatch}
          onKeepSeparateMatch={props.onKeepSeparateMatch}
          onReclassify={props.onReclassify}
          onRemoveFindings={removeFindings}
          showPreserved={showPreserved}
          onShowPreservedChange={(show) => {
            setShowPreserved(show);
            setViewMode("detections");
          }}
          manualMergeSourceId={manualMergeSourceId}
          onCancelManualMerge={cancelManualMerge}
          onManualMerge={mergeFromPanel}
          mergeNotice={mergeNotice}
        />
      </div>

      {contextMenu && contextEntity && (
        <FindingContextMenu
          entity={contextEntity}
          catalog={catalog}
          currentStrategy={effectiveStrategy(
            contextEntity,
            decisions,
            categoryDefaults,
            entityStrategies,
          )}
          x={contextMenu.x}
          y={contextMenu.y}
          t={t}
          onStrategy={(strategy) => {
            wrap(onEntityStrategy)(contextEntity.id, strategy, "entity");
            closeContextMenu();
          }}
          onMerge={
            isMergeType(contextEntity.type)
              ? () => startManualMerge(contextEntity.id)
              : undefined
          }
          onRemove={() => removeFinding(contextEntity.id)}
          onClose={closeContextMenu}
        />
      )}

      {removedToast && (
        <div className="toast is-undo" role="status">
          <p>
            {t("workspace.findingRemoved")}
            {" · "}
            <button
              type="button"
              className="toast-undo-action"
              onClick={() => {
                handleUndo();
                setRemovedToast(false);
              }}
            >
              {t("workspace.undo")}
            </button>
          </p>
        </div>
      )}

      {mergeNotice && !manualMergeSourceId && (
        <div className="toast is-undo" role="status">
          <p>{mergeNotice}</p>
          <button
            type="button"
            onClick={() => setMergeNotice(null)}
            aria-label={t("close")}
          >
            ×
          </button>
        </div>
      )}

      <span className="visually-hidden">{analysisStatus}</span>
    </div>
  );
}
