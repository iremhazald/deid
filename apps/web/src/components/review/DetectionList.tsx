import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  collapseForList,
  effectiveStrategy,
  groupCollapsedByFamily,
  listRowId,
  manualItemId,
  manualKindKey,
  outputStrategyLabelKey,
  partitionFindingsByAction,
  relatedEntityIds,
  strategyResultExample,
  tallyActionableFindings,
  userOutputStrategiesFor,
  type TypeGroup,
} from "../../state/helpers";
import {
  presentationGroupForEntityType,
  presentationGroupLabelKey,
  presentationTypeOptions,
  subcategoryForEntityType,
  subcategoryLabelKey,
} from "../../state/presentationTaxonomy";
import type {
  CategoryDefaults,
  DecisionAction,
  DecisionScope,
  Decisions,
  Entity,
  EntityStrategies,
  ManualRedaction,
  PossibleMatch,
  TransformationStrategy,
  TransformCatalog,
  UserDefinedTerm,
} from "../../state/types";
import { CategorySection } from "./CategorySection";
import { CustomTerms, type CustomTermHistoryItem } from "./CustomTerms";
import { FindingRow } from "./FindingRow";
import { ManualMergePanel } from "./ManualMergePanel";
import { MethodSelect } from "./MethodSelect";
import { ReviewPaneTabs, type ReviewPane } from "./ReviewPaneTabs";

type Pane = ReviewPane;

type Props = {
  entities: Entity[];
  decisions: Decisions;
  categoryDefaults: CategoryDefaults;
  entityStrategies: EntityStrategies;
  catalog: TransformCatalog | null;
  language: string;
  activeId: string | null;
  showPreserved?: boolean;
  onShowPreservedChange?: (show: boolean) => void;
  beforeList?: ReactNode;
  t: (key: string, options?: Record<string, unknown>) => string;
  manual?: ManualRedaction[];
  selectedManualId?: string | null;
  onSelect: (id: string) => void;
  onSelectManual?: (id: string) => void;
  onManualToggle?: (id: string, hide: boolean) => void;
  onManualRemove?: (id: string) => void;
  onDecision: (
    id: string,
    action: DecisionAction,
    scope?: DecisionScope,
  ) => void;
  onBulkDecision: (ids: string[], action: DecisionAction) => void;
  onEntityStrategy: (
    id: string,
    strategy: TransformationStrategy,
    scope?: DecisionScope,
  ) => void;
  onCategoryDefault: (type: string, strategy: TransformationStrategy) => void;
  pageTexts?: string[];
  busy?: boolean;
  onAddCustomTerm?: (term: UserDefinedTerm) => void | Promise<void>;
  possibleMatches?: PossibleMatch[];
  onMergeMatch?: (entityIds: string[]) => void | Promise<void>;
  onKeepSeparateMatch?: (entityIds: string[]) => void | Promise<void>;
  manualMergeSourceId?: string | null;
  onCancelManualMerge?: () => void;
  onManualMerge?: (entityIds: string[]) => void | Promise<void>;
  mergeNotice?: string | null;
  onReclassify?: (entityId: string, entityType: string) => void | Promise<void>;
};

export function DetectionList({
  entities,
  decisions,
  categoryDefaults,
  entityStrategies,
  catalog,
  language,
  activeId,
  showPreserved = false,
  onShowPreservedChange,
  beforeList,
  t,
  manual = [],
  selectedManualId = null,
  onSelect,
  onSelectManual,
  onManualToggle,
  onManualRemove,
  onDecision,
  onBulkDecision,
  onEntityStrategy,
  onCategoryDefault,
  pageTexts = [],
  busy = false,
  onAddCustomTerm,
  possibleMatches = [],
  onMergeMatch,
  onKeepSeparateMatch,
  manualMergeSourceId = null,
  onCancelManualMerge,
  onManualMerge,
  mergeNotice = null,
  onReclassify,
}: Props) {
  const { preserved } = useMemo(
    () =>
      partitionFindingsByAction(
        entities,
        decisions,
        categoryDefaults,
        entityStrategies,
      ),
    [entities, decisions, categoryDefaults, entityStrategies],
  );
  const families = useMemo(
    () => groupCollapsedByFamily(entities),
    [entities],
  );
  const preservedRows = useMemo(() => collapseForList(preserved), [preserved]);
  const counts = useMemo(
    () =>
      tallyActionableFindings(
        entities,
        decisions,
        categoryDefaults,
        entityStrategies,
        manual,
      ),
    [entities, decisions, categoryDefaults, entityStrategies, manual],
  );
  const reclassifyTypes = useMemo(() => presentationTypeOptions(), []);
  const [pane, setPane] = useState<Pane>(showPreserved ? "kept" : "detections");
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const [openSubcategory, setOpenSubcategory] = useState<string | null>(null);
  const [customHistory, setCustomHistory] = useState<CustomTermHistoryItem[]>([]);
  const [methodsDismissed, setMethodsDismissed] = useState(false);

  useEffect(() => {
    setMethodsDismissed(false);
  }, [activeId]);

  useEffect(() => {
    if (!activeId) return;
    const rowId = listRowId(activeId, entities);
    const entity = entities.find((item) => item.id === rowId);
    if (!entity) return;
    setPane("detections");
    onShowPreservedChange?.(false);
    const groupId = presentationGroupForEntityType(entity.type);
    const family = families.find((item) => item.id === groupId);
    setOpenGroup(groupId);
    setOpenSubcategory(
      family && !family.flattened
        ? subcategoryForEntityType(entity.type)
        : null,
    );
    return scheduleReviewPanelRowReveal(`entity-row-${rowId}`);
  }, [activeId, entities, families, onShowPreservedChange]);

  useEffect(() => {
    if (!selectedManualId) return;
    setPane("detections");
    setOpenGroup("manual");
    setOpenSubcategory(null);
    return scheduleReviewPanelRowReveal(`manual-row-${selectedManualId}`);
  }, [selectedManualId]);

  useEffect(() => {
    if (!manualMergeSourceId) return;
    setPane("detections");
    onShowPreservedChange?.(false);
  }, [manualMergeSourceId, onShowPreservedChange]);

  const visibleManual = manual.map((item, index) => ({ item, index }));
  const hasDetections = families.length > 0 || visibleManual.length > 0;
  const hasSource = entities.length > 0 || manual.length > 0;
  const activeRowId = listRowId(activeId ?? "", entities);
  const mergeSource = manualMergeSourceId
    ? entities.find((item) => item.id === manualMergeSourceId)
    : undefined;

  const toggleGroup = (id: string) => {
    setOpenGroup((current) => (current === id ? null : id));
    setOpenSubcategory(null);
  };

  const toggleSubcategory = (groupId: string, subId: string) => {
    setOpenGroup(groupId);
    setOpenSubcategory((current) => (current === subId ? null : subId));
  };

  const selectPane = (next: Pane) => {
    setPane(next);
    onShowPreservedChange?.(next === "kept");
    if (next === "detections") {
      setOpenGroup(null);
      setOpenSubcategory(null);
    }
  };

  const rowMenu = (id: string) => ({
    menuOpen: activeRowId === id && !methodsDismissed,
    onMenuOpenChange: (open: boolean) => setMethodsDismissed(!open),
  });

  const selectAndDecide = (
    id: string,
    checked: boolean,
    scope: DecisionScope = "entity",
  ) => {
    onSelect(id);
    setMethodsDismissed(false);
    onDecision(id, checked ? "REDACT" : "KEEP", scope);
  };

  const typeMethod = (group: TypeGroup) => {
    const backendTypes =
      group.backendTypes.length > 0
        ? group.backendTypes
        : [...new Set(group.rows.map((entity) => entity.type))];
    const allowed = userOutputStrategiesFor(group.type, catalog);
    const current =
      backendTypes
        .map((type) => categoryDefaults[type])
        .find((item) => item != null) ??
      categoryDefaults[group.type] ??
      allowed.find((item) => item !== "KEEP") ??
      "REDACT";
    const sampleEntity =
      group.rows.find((entity) => activeRowId === entity.id) ?? group.rows[0];
    const methodOptions = allowed.map((item) => ({
      value: item,
      label: t(outputStrategyLabelKey(item)),
      example: sampleEntity
        ? strategyResultExample(
            sampleEntity.text,
            sampleEntity.type,
            item,
            language,
            {
              role: sampleEntity.role,
              placeholderToken:
                item === "PLACEHOLDER"
                  ? sampleEntity.placeholder_token
                  : undefined,
              entity: sampleEntity,
              entities,
            },
          )
        : "",
    }));
    return { backendTypes, current, methodOptions };
  };

  const methodToolbar = (
    group: TypeGroup,
    method: ReturnType<typeof typeMethod>,
  ) => {
    const ids = group.rows.map((entity) => entity.id);
    const hideInType = group.rows.reduce(
      (sum, entity) =>
        sum +
        relatedEntityIds(entity.id, entities).filter(
          (id) => decisions[id] === "REDACT",
        ).length,
      0,
    );
    return (
      <div className="type-row">
        <MethodSelect
          label={t("workspace.howFindingsAppear")}
          value={method.current}
          options={method.methodOptions}
          onChange={(strategy) => {
            for (const type of method.backendTypes) {
              onCategoryDefault(type, strategy);
            }
          }}
        />
        <div className="type-bulk">
          <button
            type="button"
            className="type-bulk-btn"
            disabled={hideInType === group.mentionCount}
            onClick={() => onBulkDecision(ids, "REDACT")}
          >
            {t("workspace.hideAllInCategory")}
          </button>
          <button
            type="button"
            className="type-bulk-btn"
            disabled={hideInType === 0}
            onClick={() => onBulkDecision(ids, "KEEP")}
          >
            {t("workspace.keepAllInCategory")}
          </button>
        </div>
      </div>
    );
  };

  const findingList = (group: TypeGroup) => (
    <ul className="finding-rows">
      {group.rows.map((entity) => (
        <FindingRow
          key={entity.id}
          entity={entity}
          entities={entities}
          selected={decisions[entity.id] === "REDACT"}
          active={activeRowId === entity.id}
          strategy={effectiveStrategy(
            entity,
            decisions,
            categoryDefaults,
            entityStrategies,
          )}
          allowedStrategies={userOutputStrategiesFor(entity.type, catalog)}
          language={language}
          t={t}
          onSelect={() => onSelect(entity.id)}
          onToggle={(checked) => selectAndDecide(entity.id, checked, "entity")}
          onStrategyChange={(strategy, scope) =>
            onEntityStrategy(entity.id, strategy, scope)
          }
          typeOptions={reclassifyTypes}
          onTypeChange={
            onReclassify
              ? (type) => void onReclassify(entity.id, type)
              : undefined
          }
          onOccurrenceSelect={onSelect}
          onOccurrenceToggle={(id, checked) =>
            selectAndDecide(id, checked, "occurrence")
          }
          occurrenceHidden={(id) => decisions[id] === "REDACT"}
          activeOccurrenceId={activeId}
          {...rowMenu(entity.id)}
        />
      ))}
    </ul>
  );

  const possibleMatchList =
    possibleMatches.length > 0 ? (
      <ul className="possible-matches">
        {possibleMatches.map((match) => (
          <PossibleMatchCard
            key={match.id}
            match={match}
            t={t}
            onMerge={onMergeMatch}
            onKeepSeparate={onKeepSeparateMatch}
            onSelect={onSelect}
          />
        ))}
      </ul>
    ) : null;

  return (
    <>
      <header
        className="review-panel-head"
        aria-label={t("workspace.actionableCount", {
          count: counts.actionable,
        })}
      >
        <ReviewPaneTabs
          pane={pane}
          ariaLabel={t("workspace.filterCategory")}
          onSelect={selectPane}
          tabs={[
            {
              id: "detections",
              label: t("workspace.paneDetections"),
              count: counts.actionable,
            },
            {
              id: "kept",
              label: t("workspace.paneKept"),
              count: counts.preserved,
            },
            {
              id: "custom",
              label: t("workspace.paneCustom"),
            },
          ]}
        />
      </header>

      <div className="review-panel-scroll">
        {mergeSource && onManualMerge ? (
          <ManualMergePanel
            sourceEntity={mergeSource}
            entities={entities}
            possibleMatches={possibleMatches}
            t={t}
            onMerge={onManualMerge}
            onCancel={() => onCancelManualMerge?.()}
            notice={mergeNotice}
          />
        ) : (
          <>
        {beforeList}
        {pane === "custom" ? (
          onAddCustomTerm ? (
            <>
              {possibleMatchList}
              <CustomTerms
                embedded
                t={t}
                busy={busy}
                pageTexts={pageTexts}
                catalog={catalog}
                history={customHistory}
                onAdd={onAddCustomTerm}
                onHistoryStrategy={(item, strategy) => {
                  const query = item.value.trim().toLocaleLowerCase("tr");
                  for (const entity of entities) {
                    if (entity.detector !== "USER_DEFINED_TERM") continue;
                    const text = entity.text.toLocaleLowerCase("tr");
                    const attr = String(
                      entity.attributes?.term ?? "",
                    ).toLocaleLowerCase("tr");
                    if (
                      attr === query ||
                      text === query ||
                      (query.length >= 2 && text.startsWith(query))
                    ) {
                      onEntityStrategy(entity.id, strategy, "entity");
                    }
                  }
                  setCustomHistory((current) =>
                    current.map((record) =>
                      record.value === item.value &&
                      record.category === item.category
                        ? { ...record, strategy }
                        : record,
                    ),
                  );
                }}
                onAdded={(record) => {
                  setCustomHistory((current) => [...current, record]);
                  setPane("detections");
                  const groupId = presentationGroupForEntityType(record.category);
                  const family = families.find((item) => item.id === groupId);
                  setOpenGroup(groupId);
                  setOpenSubcategory(
                    family && !family.flattened
                      ? subcategoryForEntityType(record.category)
                      : null,
                  );
                  onShowPreservedChange?.(false);
                }}
              />
            </>
          ) : (
            <p className="review-panel-empty">
              {t("workspace.customSearchUnavailable")}
            </p>
          )
        ) : pane === "kept" ? (
          preservedRows.length === 0 ? (
            <p className="review-panel-empty">{t("workspace.keptEmpty")}</p>
          ) : (
            <ul className="detection-nav family-nav is-flat">
              <li className="family-block family-block-preserved open">
                <ul className="finding-rows" id="category-panel-preserved">
                  {preservedRows.map((entity) => (
                    <FindingRow
                      key={entity.id}
                      entity={entity}
                      entities={entities}
                      selected={decisions[entity.id] === "REDACT"}
                      active={activeRowId === entity.id}
                      strategy={effectiveStrategy(
                        entity,
                        decisions,
                        categoryDefaults,
                        entityStrategies,
                      )}
                      allowedStrategies={userOutputStrategiesFor(
                        entity.type,
                        catalog,
                      )}
                      language={language}
                      t={t}
                      onSelect={() => onSelect(entity.id)}
                      onToggle={(checked) =>
                        selectAndDecide(entity.id, checked, "entity")
                      }
                      onStrategyChange={(strategy, scope) =>
                        onEntityStrategy(entity.id, strategy, scope)
                      }
                      typeOptions={reclassifyTypes}
                      onTypeChange={
                        onReclassify
                          ? (type) => void onReclassify(entity.id, type)
                          : undefined
                      }
                      onOccurrenceSelect={onSelect}
                      onOccurrenceToggle={(id, checked) =>
                        selectAndDecide(id, checked, "occurrence")
                      }
                      occurrenceHidden={(id) => decisions[id] === "REDACT"}
                      activeOccurrenceId={activeId}
                      {...rowMenu(entity.id)}
                    />
                  ))}
                </ul>
              </li>
            </ul>
          )
        ) : (
          <>
            {possibleMatchList}
            {!hasDetections && hasSource ? (
              <p className="review-panel-empty">{t("workspace.noFilterResults")}</p>
            ) : !hasDetections ? null : (
          <ul className="detection-nav family-nav">
            {visibleManual.length > 0 && (
              <CategorySection
                id="manual"
                type="OTHER_IDENTIFIER"
                title={t("workspace.family.manual")}
                count={visibleManual.length}
                open={openGroup === "manual"}
                active={Boolean(selectedManualId)}
                manual
                onToggle={() => toggleGroup("manual")}
              >
                <ul className="finding-rows">
                  {visibleManual.map(({ item, index }) => {
                    const itemId = manualItemId(item, index);
                    const kind = manualKindKey(item);
                    const title =
                      kind === "text"
                        ? (item.replacement ??
                          t("workspace.manualTextLabelShort"))
                        : kind === "mask"
                          ? t("workspace.manualMaskLabel")
                          : item.text;
                    const kindLabel =
                      kind === "text"
                        ? t("workspace.toolAddText")
                        : kind === "mask"
                          ? t("workspace.toolRedactArea")
                          : t("manualAdded");
                    const category = item.category
                      ? t(`categories.${item.category}`, {
                          defaultValue: item.category,
                        })
                      : kindLabel;
                    return (
                      <li
                        key={itemId}
                        className={`finding-row${selectedManualId === itemId ? " on" : ""}${item.kept ? " is-kept" : ""}`}
                        id={`manual-row-${itemId}`}
                      >
                        <label className="finding-check">
                          <input
                            type="checkbox"
                            checked={!item.kept}
                            onChange={(event) =>
                              onManualToggle?.(itemId, event.target.checked)
                            }
                            aria-label={t("workspace.hideCheckbox", {
                              name: title,
                            })}
                          />
                        </label>
                        <div className="finding-main">
                          <button
                            type="button"
                            className="finding-identity"
                            onClick={() => onSelectManual?.(itemId)}
                          >
                            <strong>{title}</strong>
                            <span>
                              {category}
                              <span aria-hidden> · </span>
                              {t("page")} {item.page}
                            </span>
                          </button>
                        </div>
                        <button
                          type="button"
                          className="finding-remove"
                          aria-label={t("remove")}
                          onClick={() => onManualRemove?.(itemId)}
                        >
                          ×
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </CategorySection>
            )}
            {families.map((family) => {
              const groupActive = family.rows.some(
                (entity) => activeRowId === entity.id,
              );
              if (family.flattened) {
                const group = family.types[0];
                if (!group) return null;
                const method = typeMethod(group);
                return (
                  <CategorySection
                    key={family.id}
                    id={family.id}
                    type={group.type}
                    title={t(presentationGroupLabelKey(family.id), {
                      defaultValue: t(subcategoryLabelKey(group.type), {
                        defaultValue: group.type,
                      }),
                    })}
                    count={family.mentionCount}
                    open={openGroup === family.id}
                    active={groupActive}
                    methodLabel={t(outputStrategyLabelKey(method.current))}
                    onToggle={() => toggleGroup(family.id)}
                    toolbar={methodToolbar(group, method)}
                  >
                    {findingList(group)}
                  </CategorySection>
                );
              }
              return (
                <CategorySection
                  key={family.id}
                  id={family.id}
                  type={family.types[0]?.type ?? family.id}
                  title={t(presentationGroupLabelKey(family.id), {
                    defaultValue: family.id,
                  })}
                  count={family.mentionCount}
                  open={openGroup === family.id}
                  active={groupActive}
                  onToggle={() => toggleGroup(family.id)}
                >
                  <ul className="subcategory-list">
                    {family.types.map((group) => {
                      const method = typeMethod(group);
                      const open = openSubcategory === group.type;
                      const active = group.rows.some(
                        (entity) => activeRowId === entity.id,
                      );
                      const panelId = `subcategory-panel-${family.id}-${group.type}`;
                      return (
                        <li
                          key={group.type}
                          className={`subcategory-item${open ? " open" : ""}${active ? " has-active" : ""}`}
                        >
                          <button
                            type="button"
                            className="subcategory-toggle"
                            aria-expanded={open}
                            aria-controls={panelId}
                            onClick={() =>
                              toggleSubcategory(family.id, group.type)
                            }
                          >
                            <span className="subcategory-toggle-copy">
                              <span className="subcategory-toggle-title">
                                {t(subcategoryLabelKey(group.type), {
                                  defaultValue: group.type,
                                })}
                              </span>
                              <span className="subcategory-toggle-method">
                                {t(outputStrategyLabelKey(method.current))}
                              </span>
                            </span>
                            <span className="subcategory-toggle-count">
                              {group.mentionCount}
                            </span>
                            <span className="family-chevron" aria-hidden="true">
                              <SubcategoryChevron />
                            </span>
                          </button>
                          <div
                            className="subcategory-panel"
                            id={panelId}
                            hidden={!open}
                            role="region"
                            aria-label={t(subcategoryLabelKey(group.type), {
                              defaultValue: group.type,
                            })}
                          >
                            {methodToolbar(group, method)}
                            {findingList(group)}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </CategorySection>
              );
            })}
          </ul>
            )}
          </>
        )}
          </>
        )}
      </div>
    </>
  );
}

function scheduleReviewPanelRowReveal(elementId: string) {
  let cancelled = false;
  let frames = 0;

  const reveal = () => {
    if (cancelled) return;
    const row = document.getElementById(elementId);
    const scroller = row?.closest(".review-panel-scroll");
    if (
      !row ||
      !(scroller instanceof HTMLElement) ||
      row.closest("[hidden]") ||
      row.getBoundingClientRect().height === 0
    ) {
      if (frames++ < 30) window.requestAnimationFrame(reveal);
      return;
    }
    const rowBox = row.getBoundingClientRect();
    const box = scroller.getBoundingClientRect();
    const topGap = 8;
    const bottomGap = 8;
    const available = box.height - topGap - bottomGap;
    if (rowBox.height >= available) {
      scroller.scrollTo({
        top: Math.max(0, scroller.scrollTop + (rowBox.top - box.top) - topGap),
        behavior: "auto",
      });
      return;
    }
    if (rowBox.top >= box.top + topGap && rowBox.bottom <= box.bottom - bottomGap) {
      return;
    }
    if (rowBox.bottom > box.bottom - bottomGap) {
      scroller.scrollTo({
        top: scroller.scrollTop + (rowBox.bottom - (box.bottom - bottomGap)),
        behavior: "auto",
      });
      return;
    }
    scroller.scrollTo({
      top: Math.max(0, scroller.scrollTop + (rowBox.top - box.top) - topGap),
      behavior: "auto",
    });
  };

  const start = window.requestAnimationFrame(reveal);
  const followUp = window.setTimeout(reveal, 160);
  return () => {
    cancelled = true;
    window.cancelAnimationFrame(start);
    window.clearTimeout(followUp);
  };
}

function displayPages(
  pages: number[],
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  const numbered = pages.map((page) => page + 1);
  if (numbered.length <= 1) {
    return t("workspace.possibleMatchPage", { page: numbered[0] ?? 1 });
  }
  return t("workspace.possibleMatchPages", { pages: numbered.join(", ") });
}

function matchEntityIds(match: PossibleMatch) {
  return match.members.flatMap((member) => member.entity_ids.slice(0, 1));
}

function PossibleMatchCard({
  match,
  t,
  onMerge,
  onKeepSeparate,
  onSelect,
}: {
  match: PossibleMatch;
  t: (key: string, options?: Record<string, unknown>) => string;
  onMerge?: (entityIds: string[]) => void | Promise<void>;
  onKeepSeparate?: (entityIds: string[]) => void | Promise<void>;
  onSelect: (id: string) => void;
}) {
  const ids = matchEntityIds(match);
  return (
    <li className="possible-match">
      <p className="possible-match-title">{t("workspace.possibleMatchTitle")}</p>
      {match.members.map((member) => (
        <button
          key={member.canonical_id}
          type="button"
          className="possible-match-member"
          onClick={() => {
            const first = member.entity_ids[0];
            if (first) onSelect(first);
          }}
        >
          <strong>{member.text}</strong>
          <span>{displayPages(member.pages, t)}</span>
        </button>
      ))}
      <p className="possible-match-hint">
        {t(
          match.kind === "address"
            ? "workspace.possibleMatchHintAddress"
            : "workspace.possibleMatchHint",
        )}
      </p>
      <div className="possible-match-actions">
        <button
          type="button"
          className="possible-match-merge"
          onClick={() => void onMerge?.(ids)}
          disabled={!onMerge || ids.length < 2}
        >
          {t("workspace.possibleMatchMerge")}
        </button>
        <button
          type="button"
          className="possible-match-keep"
          onClick={() => void onKeepSeparate?.(ids)}
          disabled={!onKeepSeparate || ids.length < 2}
        >
          {t("workspace.possibleMatchKeepSeparate")}
        </button>
      </div>
    </li>
  );
}

function SubcategoryChevron() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path
        d="M3 4.6 6 7.6l3-3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
