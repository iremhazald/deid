import { useEffect, useMemo, useState } from "react";
import { presentationTypeOptions } from "../../state/presentationTaxonomy";
import {
  outputStrategyLabelKey,
  findDocumentPhraseHits,
  userOutputStrategiesFor,
} from "../../state/helpers";
import type {
  TransformationStrategy,
  TransformCatalog,
  UserDefinedTerm,
} from "../../state/types";
import { ChoiceSelect } from "./ChoiceSelect";

export type CustomTermHistoryItem = {
  value: string;
  category: UserDefinedTerm["category"];
  count: number;
  strategy?: TransformationStrategy;
};

type Props = {
  t: (key: string, options?: Record<string, unknown>) => string;
  busy?: boolean;
  pageTexts?: string[];
  catalog?: TransformCatalog | null;
  history?: CustomTermHistoryItem[];
  onAdd: (term: UserDefinedTerm) => void | Promise<void>;
  onAdded?: (record: CustomTermHistoryItem) => void;
  onHistoryStrategy?: (
    item: CustomTermHistoryItem,
    strategy: TransformationStrategy,
  ) => void;
  embedded?: boolean;
};

const CATEGORIES = presentationTypeOptions();

const STRATEGIES: TransformationStrategy[] = [
  "REDACT",
  "PLACEHOLDER",
  "PARTIAL_MASK",
  "KEEP",
];

function categoryLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  category: string,
) {
  const override = t(`workspace.customTermCategories.${category}`);
  if (override !== `workspace.customTermCategories.${category}`) return override;
  return t(`categories.${category}`);
}

export function CustomTerms({
  t,
  busy,
  pageTexts = [],
  catalog = null,
  history = [],
  onAdd,
  onAdded,
  onHistoryStrategy,
  embedded = false,
}: Props) {
  const [open, setOpen] = useState(embedded);
  const [value, setValue] = useState("");
  const [category, setCategory] = useState<UserDefinedTerm["category"]>(
    "PERSON_NAME",
  );
  const [strategy, setStrategy] = useState<TransformationStrategy>("REDACT");
  const [selectedStarts, setSelectedStarts] = useState<number[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hits = useMemo(
    () => findDocumentPhraseHits(pageTexts, value),
    [pageTexts, value],
  );
  const query = value.trim();
  const searched = embedded ? query.length >= 2 : selectedStarts !== null;
  const chosen = selectedStarts ?? hits.map((hit) => hit.start);
  const pages = [...new Set(hits.map((hit) => hit.page + 1))];
  const pending = busy || saving;
  const methodOptions = useMemo(
    () =>
      embedded
        ? userOutputStrategiesFor(category, catalog).filter((item) => item !== "KEEP")
        : STRATEGIES,
    [embedded, category, catalog],
  );

  useEffect(() => {
    setStrategy((current) =>
      methodOptions.includes(current) ? current : "REDACT",
    );
  }, [methodOptions]);

  const search = () => {
    if (query.length < 2) return;
    setError(null);
    setSelectedStarts(hits.map((hit) => hit.start));
  };

  const apply = async () => {
    if (query.length < 2 || chosen.length === 0) return;
    setError(null);
    setSaving(true);
    try {
      await onAdd({
        value: query,
        category,
        strategy,
        starts: chosen,
      });
        onAdded?.({ value: query, category, count: chosen.length, strategy });
      setValue("");
      setSelectedStarts(null);
    } catch {
      setError(t("workspace.customSearchApplyFailed"));
    } finally {
      setSaving(false);
    }
  };

  const categoryOptions = CATEGORIES.map((item) => ({
    value: item,
    label: categoryLabel(t, item),
  }));
  const strategyOptions = methodOptions.map((item) => ({
    value: item,
    label: t(outputStrategyLabelKey(item)),
  }));

  const form = (
    <form
      className={`custom-terms-form${embedded ? " is-embedded" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        if (embedded) void apply();
        else if (selectedStarts === null) search();
        else void apply();
      }}
    >
      <label className="custom-search-field">
        <span className={embedded ? "visually-hidden" : undefined}>
          {t("workspace.customTermValue")}
        </span>
        <input
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setSelectedStarts(null);
            setError(null);
          }}
          maxLength={200}
          placeholder={t("workspace.customSearchHint")}
          disabled={pending}
        />
      </label>
      {embedded && (
        <div className="custom-search-controls">
          <ChoiceSelect
            label={t("workspace.customTermType")}
            value={category}
            options={categoryOptions}
            disabled={pending}
            onChange={setCategory}
          />
          <ChoiceSelect
            label={t("workspace.categoryMethod")}
            value={strategy}
            options={strategyOptions}
            disabled={pending}
            onChange={setStrategy}
          />
        </div>
      )}
      {!embedded && (
        <div className="custom-search-controls">
          <ChoiceSelect
            label={t("workspace.customTermType")}
            value={category}
            options={categoryOptions}
            disabled={pending}
            onChange={setCategory}
          />
          <ChoiceSelect
            label={t("customTermStrategy")}
            value={strategy}
            options={strategyOptions}
            disabled={pending}
            onChange={setStrategy}
          />
        </div>
      )}
      {searched && (
        <div className="phrase-hits">
          <p className="custom-search-summary">
            {hits.length === 0
              ? t("workspace.phraseHitEmpty")
              : t("workspace.customSearchSummary", {
                  count: hits.length,
                  pages: pages.join(", "),
                })}
          </p>
          {hits.length > 0 && (
            <fieldset className="phrase-hit-list">
              <legend className="visually-hidden">
                {t("workspace.phraseHitsTitle", { count: hits.length })}
              </legend>
              {hits.map((hit) => (
                <label key={`${hit.page}-${hit.start}`}>
                  <input
                    type="checkbox"
                    checked={chosen.includes(hit.start)}
                    disabled={pending}
                    onChange={() => {
                      setSelectedStarts((current) => {
                        const present = current ?? hits.map((item) => item.start);
                        return present.includes(hit.start)
                          ? present.filter((start) => start !== hit.start)
                          : [...present, hit.start];
                      });
                    }}
                  />
                  <span>
                    {t("page")} {hit.page + 1}
                    {hit.line ? ` · ${hit.line}` : ""}
                  </span>
                </label>
              ))}
            </fieldset>
          )}
        </div>
      )}
      {!embedded && (
        <p className="panel-help">{t("customTermHomonymHint")}</p>
      )}
      {error && <p className="custom-search-error">{error}</p>}
      <button
        type="submit"
        className={embedded ? "btn primary" : undefined}
        disabled={pending || query.length < 2 || (searched && chosen.length === 0)}
      >
        {saving
          ? t("workspace.customSearchSaving")
          : embedded
            ? t("workspace.customSearchMask", { count: chosen.length })
            : selectedStarts === null
              ? t("workspace.customTermApply")
              : t("workspace.phraseHitAdd", { count: selectedStarts.length })}
      </button>
    </form>
  );

  if (embedded) {
    return (
      <section className="custom-terms is-embedded">
        <p className="custom-search-lead">{t("workspace.customSearchLead")}</p>
        {form}
        {history.length > 0 && (
          <div className="custom-search-history">
            <h3>{t("workspace.customSearchHistory")}</h3>
            <ul>
              {history.map((item, index) => {
                const historyMethods: TransformationStrategy[] =
                  userOutputStrategiesFor(item.category, catalog).filter(
                    (method) => method !== "KEEP",
                  );
                const current =
                  item.strategy && historyMethods.includes(item.strategy)
                    ? item.strategy
                    : (historyMethods[0] ?? "REDACT");
                return (
                  <li
                    key={`${item.value}-${item.category}-${index}`}
                    className="custom-search-history-item"
                  >
                    <span>
                      {t("workspace.customSearchHistoryItem", {
                        value: item.value,
                        category: categoryLabel(t, item.category),
                        count: item.count,
                      })}
                    </span>
                    {onHistoryStrategy && historyMethods.length > 0 && (
                      <ChoiceSelect
                        label={t("workspace.categoryMethod")}
                        value={current}
                        options={historyMethods.map((method) => ({
                          value: method,
                          label: t(outputStrategyLabelKey(method)),
                        }))}
                        disabled={pending}
                        onChange={(strategy) =>
                          onHistoryStrategy(item, strategy)
                        }
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="custom-terms">
      <button
        type="button"
        className="custom-terms-toggle"
        onClick={() => setOpen((current) => !current)}
      >
        {t("workspace.addCustomTerm")}
      </button>
      {open && form}
    </section>
  );
}
