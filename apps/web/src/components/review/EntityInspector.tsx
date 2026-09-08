import { useState } from "react";
import {
  allowedStrategiesFor,
  detectionSource,
  effectiveStrategy,
  previewEntityValue,
  relatedEntityIds,
  sourceLabelKey,
} from "../../state/helpers";
import { subcategoryLabelKey } from "../../state/presentationTaxonomy";
import type {
  CategoryDefaults,
  DecisionAction,
  DecisionScope,
  Decisions,
  Entity,
  EntityStrategies,
  TransformationStrategy,
  TransformCatalog,
} from "../../state/types";

type Props = {
  entity: Entity;
  entities: Entity[];
  decisions: Decisions;
  categoryDefaults: CategoryDefaults;
  entityStrategies: EntityStrategies;
  catalog: TransformCatalog | null;
  language: string;
  t: (key: string, options?: Record<string, unknown>) => string;
  onBack: () => void;
  onDecision: (
    id: string,
    action: DecisionAction,
    scope?: DecisionScope,
  ) => void;
  onEntityStrategy: (
    id: string,
    strategy: TransformationStrategy,
    scope?: DecisionScope,
  ) => void;
  onApplyRelated: () => void;
};

export function EntityInspector({
  entity,
  entities,
  decisions,
  categoryDefaults,
  entityStrategies,
  catalog,
  language,
  t,
  onBack,
  onDecision,
  onEntityStrategy,
  onApplyRelated,
}: Props) {
  const strategy = effectiveStrategy(
    entity,
    decisions,
    categoryDefaults,
    entityStrategies,
  );
  const allowed = allowedStrategiesFor(entity.type, catalog);
  const related = relatedEntityIds(entity.id, entities);
  const occurrenceCount = related.length;
  const source = detectionSource(entity);
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
  const kept = strategy === "KEEP" || decisions[entity.id] === "KEEP";
  const [scope, setScope] = useState<DecisionScope>("entity");

  const choose = (next: TransformationStrategy) => {
    if (next === "KEEP") {
      onDecision(entity.id, "KEEP", scope);
      onEntityStrategy(entity.id, "KEEP", scope);
      return;
    }
    onEntityStrategy(entity.id, next, scope);
  };

  return (
    <section className="entity-inspector" aria-label={t("workspace.inspector")}>
      <button type="button" className="inspector-back" onClick={onBack}>
        ← {t("workspace.backToDetections")}
      </button>

      <header className="inspector-hero">
        <p className="inspector-kicker">
          {t(subcategoryLabelKey(entity.type), {
            defaultValue: entity.type,
          })}
        </p>
        <h2>{entity.text}</h2>
        <p className="inspector-meta">
          {t("page")} {entity.page + 1}
          {occurrenceCount > 1 && (
            <>
              <span aria-hidden> · </span>
              {t("workspace.occurrenceCount", { count: occurrenceCount })}
            </>
          )}
        </p>
        <p className="inspector-meta subtle">
          {t(sourceLabelKey(source))}
          {entity.role ? ` · ${t("role")}: ${entity.role}` : ""}
        </p>
      </header>

      <div
        className="decision-toggle"
        role="group"
        aria-label={t("workspace.decision")}
      >
        <button
          type="button"
          className={!kept ? "on" : ""}
          aria-pressed={!kept}
          onClick={() => onDecision(entity.id, "REDACT", scope)}
        >
          {t("workspace.transform")}
        </button>
        <button
          type="button"
          className={kept ? "on" : ""}
          aria-pressed={kept}
          onClick={() => onDecision(entity.id, "KEEP", scope)}
        >
          {t("workspace.keep")}
        </button>
      </div>

      <div className="live-preview">
        <div>
          <span>{t("workspace.original")}</span>
          <strong>{entity.text}</strong>
        </div>
        <span className="live-preview-arrow" aria-hidden>
          →
        </span>
        <div>
          <span>{t("workspace.output")}</span>
          <strong className={kept ? "is-keep" : ""}>
            {kept ? entity.text : preview || t("workspace.suppressed")}
          </strong>
        </div>
      </div>

      {!kept && (
        <fieldset className="strategy-choices">
          <legend>{t("howToAppear")}</legend>
          {allowed
            .filter((item) => item !== "KEEP")
            .map((item) => {
              const sample = previewEntityValue(
                entity.text,
                entity.type,
                item,
                language,
                {
                  role: entity.role,
                  placeholderToken: item === "PLACEHOLDER" ? entity.placeholder_token : undefined,
                  entity,
                  entities,
                },
              );
              return (
                <label
                  key={item}
                  className={`strategy-choice${strategy === item ? " on" : ""}`}
                >
                  <input
                    type="radio"
                    name={`strategy-${entity.id}`}
                    checked={strategy === item}
                    onChange={() => choose(item)}
                  />
                  <span>
                    <em>{t(`strategies.${item}`, { defaultValue: item })}</em>
                    <small>{sample || t("workspace.suppressed")}</small>
                  </span>
                </label>
              );
            })}
        </fieldset>
      )}

      {occurrenceCount > 1 && (
        <div className="occurrence-actions">
          <p>{t("workspace.occurrenceHelp", { count: occurrenceCount })}</p>
          <div
            className="decision-toggle"
            role="group"
            aria-label={t("workspace.occurrenceHelp", {
              count: occurrenceCount,
            })}
          >
            <button
              type="button"
              className={scope === "entity" ? "on" : ""}
              aria-pressed={scope === "entity"}
              onClick={() => {
                setScope("entity");
                onApplyRelated();
              }}
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
        </div>
      )}
    </section>
  );
}
