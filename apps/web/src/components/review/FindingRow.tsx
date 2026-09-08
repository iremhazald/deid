import { useEffect, useId, useRef, useState } from "react";
import {
  outputStrategyLabelKey,
  relatedEntityIds,
  strategyResultExample,
} from "../../state/helpers";
import type {
  DecisionScope,
  Entity,
  TransformationStrategy,
} from "../../state/types";
import { ChoiceSelect } from "./ChoiceSelect";

type Props = {
  entity: Entity;
  entities: Entity[];
  selected: boolean;
  active: boolean;
  strategy: TransformationStrategy;
  allowedStrategies: TransformationStrategy[];
  language: string;
  t: (key: string, options?: Record<string, unknown>) => string;
  onSelect: () => void;
  onToggle: (checked: boolean) => void;
  onStrategyChange: (
    strategy: TransformationStrategy,
    scope: DecisionScope,
  ) => void;
  onOccurrenceSelect?: (id: string) => void;
  onOccurrenceToggle?: (id: string, checked: boolean) => void;
  occurrenceHidden?: (id: string) => boolean;
  activeOccurrenceId?: string | null;
  menuOpen?: boolean;
  onMenuOpenChange?: (open: boolean) => void;
  typeOptions?: string[];
  onTypeChange?: (entityType: string) => void;
};

export function FindingRow({
  entity,
  entities,
  selected,
  active,
  strategy,
  allowedStrategies,
  language,
  t,
  onSelect,
  onToggle,
  onStrategyChange,
  onOccurrenceSelect,
  onOccurrenceToggle,
  occurrenceHidden,
  activeOccurrenceId = null,
  menuOpen = false,
  onMenuOpenChange,
  typeOptions = [],
  onTypeChange,
}: Props) {
  const related = relatedEntityIds(entity.id, entities)
    .map((id) => entities.find((item) => item.id === id))
    .filter((item): item is Entity => Boolean(item))
    .sort((a, b) => a.page - b.page || a.start - b.start);
  const occurrenceCount = related.length;
  const [openOccurrences, setOpenOccurrences] = useState(
    () => active && occurrenceCount > 1,
  );
  const occurrenceText =
    occurrenceCount > 1
      ? t("workspace.occurrenceCount", { count: occurrenceCount })
      : `${t("page")} ${entity.page + 1}`;
  const needsCheck = entity.needs_review === true;
  const methods = allowedStrategies.includes("KEEP")
    ? allowedStrategies
    : (["KEEP", ...allowedStrategies] as TransformationStrategy[]);
  const rootRef = useRef<HTMLLIElement>(null);
  const menuId = useId();

  const openMethods = () => onMenuOpenChange?.(true);
  const closeMethods = () => onMenuOpenChange?.(false);

  const relatedIds = related.map((item) => item.id).join("|");

  useEffect(() => {
    setOpenOccurrences(active && occurrenceCount > 1);
  }, [active, occurrenceCount]);

  useEffect(() => {
    if (!menuOpen) return;
    const ids = new Set(relatedIds ? relatedIds.split("|") : [entity.id]);
    ids.add(entity.id);
    const onPointer = (event: PointerEvent) => {
      const target = event.target;
      if (rootRef.current?.contains(target as Node)) return;
      const el =
        target instanceof Element
          ? target
          : target instanceof Node
            ? target.parentElement
            : null;
      if (el instanceof Element) {
        const overlay = el.closest("[data-entity-id]");
        const overlayId = overlay?.getAttribute("data-entity-id");
        if (overlayId && ids.has(overlayId)) return;
        const docHit = el.closest("[id^='entity-']");
        const docId = docHit?.id.replace(/^entity-(?:row-)?/, "");
        if (docId && ids.has(docId)) return;
      }
      closeMethods();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeMethods();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen, relatedIds, entity.id]);

  return (
    <li
      ref={rootRef}
      className={`finding-row${active ? " on" : ""}${selected ? "" : " is-kept"}${strategy === "KEEP" ? " is-preserved" : ""}${menuOpen ? " is-methods-open" : ""}`}
      id={`entity-row-${entity.id}`}
    >
      <label className="finding-check">
        <input
          type="checkbox"
          checked={selected}
          onChange={(event) => {
            const checked = event.target.checked;
            onSelect();
            openMethods();
            onToggle(checked);
          }}
          aria-label={t("workspace.hideCheckbox", { name: entity.text })}
        />
      </label>
      <div className="finding-main">
        <button
          type="button"
          className="finding-identity"
          onClick={() => {
            if (active && menuOpen) {
              closeMethods();
              return;
            }
            onSelect();
            openMethods();
          }}
        >
          <strong>{entity.text}</strong>
          {occurrenceCount === 1 && <span>{occurrenceText}</span>}
          {needsCheck && (
            <em className="finding-check-hint">{t("workspace.reviewHint")}</em>
          )}
        </button>
        {occurrenceCount > 1 && (
          <button
            type="button"
            className="finding-occ-toggle"
            aria-expanded={active && openOccurrences}
            onClick={() => {
              if (!active) {
                onSelect();
                openMethods();
                return;
              }
              setOpenOccurrences((value) => !value);
            }}
          >
            {occurrenceText}
          </button>
        )}
      </div>
      {methods.length > 0 && active && (
        <button
          type="button"
          className={`finding-method-toggle${menuOpen ? " is-open" : ""}`}
          aria-expanded={menuOpen}
          aria-controls={menuId}
          aria-label={t("workspace.moreActions")}
          onClick={(event) => {
            event.stopPropagation();
            if (menuOpen) closeMethods();
            else {
              onSelect();
              openMethods();
            }
          }}
        >
          <MethodChevron />
        </button>
      )}
      {menuOpen && methods.length > 0 && (
        <FindingMethodPanel
          id={menuId}
          entity={entity}
          entities={entities}
          strategy={strategy}
          allowed={methods}
          occurrenceCount={occurrenceCount}
          language={language}
          t={t}
          typeOptions={typeOptions}
          onTypeChange={onTypeChange}
          onStrategyChange={(next, scope) => {
            onSelect();
            onStrategyChange(next, scope);
          }}
        />
      )}
      {active && openOccurrences && occurrenceCount > 1 && (
        <ul className="occurrence-list">
          {related.map((item) => (
            <li key={item.id}>
              <label>
                <input
                  type="checkbox"
                  checked={
                    occurrenceHidden ? occurrenceHidden(item.id) : selected
                  }
                  onChange={(event) => {
                    const checked = event.target.checked;
                    onOccurrenceSelect?.(item.id);
                    openMethods();
                    onOccurrenceToggle?.(item.id, checked);
                  }}
                  aria-label={t("workspace.hideOccurrence", {
                    page: item.page + 1,
                  })}
                />
              </label>
              <button
                type="button"
                className={activeOccurrenceId === item.id ? "on" : ""}
                onClick={() => {
                  onOccurrenceSelect?.(item.id);
                  openMethods();
                }}
              >
                {t("page")} {item.page + 1}
              </button>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function FindingMethodPanel({
  id,
  entity,
  entities,
  strategy,
  allowed,
  occurrenceCount,
  language,
  t,
  typeOptions = [],
  onTypeChange,
  onStrategyChange,
}: {
  id: string;
  entity: Entity;
  entities: Entity[];
  strategy: TransformationStrategy;
  allowed: TransformationStrategy[];
  occurrenceCount: number;
  language: string;
  t: (key: string, options?: Record<string, unknown>) => string;
  typeOptions?: string[];
  onTypeChange?: (entityType: string) => void;
  onStrategyChange: (
    strategy: TransformationStrategy,
    scope: DecisionScope,
  ) => void;
}) {
  const [scope, setScope] = useState<DecisionScope>("entity");
  const types = typeOptions.includes(entity.type)
    ? typeOptions
    : [entity.type, ...typeOptions];

  return (
    <div
      id={id}
      className="finding-method-panel"
      role="menu"
      aria-label={t("workspace.moreActions")}
    >
      {onTypeChange && (
        <ChoiceSelect
          className="finding-method-category"
          label={t("workspace.changeCategory")}
          value={entity.type}
          options={types.map((type) => ({
            value: type,
            label: t(`categories.${type}`),
          }))}
          onChange={onTypeChange}
        />
      )}
      {allowed.map((item) => {
        const example = strategyResultExample(
          entity.text,
          entity.type,
          item,
          language,
          {
            role: entity.role,
            placeholderToken:
              item === "PLACEHOLDER" ? entity.placeholder_token : undefined,
            entity,
            entities,
          },
        );
        const { title, detail } = choiceCopy(item, example, t);
        return (
          <button
            key={item}
            type="button"
            role="menuitem"
            className={strategy === item ? "on" : ""}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onStrategyChange(item, scope);
            }}
          >
            <strong>{title}</strong>
            {detail && <span>{detail}</span>}
          </button>
        );
      })}
      {occurrenceCount > 1 && (
        <div
          className="finding-method-scope"
          role="group"
          aria-label={t("workspace.occurrenceHelp", {
            count: occurrenceCount,
          })}
        >
          <button
            type="button"
            className={scope === "entity" ? "on" : ""}
            aria-pressed={scope === "entity"}
            onClick={() => setScope("entity")}
          >
            {t("workspace.applyAllOccurrences")}
          </button>
          <button
            type="button"
            className={scope === "occurrence" ? "on" : ""}
            aria-pressed={scope === "occurrence"}
            onClick={() => setScope("occurrence")}
          >
            {t("workspace.thisOccurrenceOnly")}
          </button>
        </div>
      )}
    </div>
  );
}

function choiceCopy(
  strategy: TransformationStrategy,
  example: string,
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  const title = t(outputStrategyLabelKey(strategy));
  if (example && example !== title) return { title, detail: example };
  return { title, detail: undefined };
}

function MethodChevron() {
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
