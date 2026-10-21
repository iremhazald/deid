import {
  analysisStatusOf,
  manualItemId,
  needsInitialsSizeControl,
} from "../../state/helpers";
import { DOCUMENT_FONT_SIZES } from "./documentFonts";
import type {
  Analysis,
  CategoryDefaults,
  DecisionAction,
  DecisionScope,
  Decisions,
  EntityStrategies,
  ManualRedaction as ManualItem,
  OutputFormat,
  PrivacyProfile,
  TransformationStrategy,
  TransformCatalog,
  UserDefinedTerm,
} from "../../state/types";
import { DetectionList } from "./DetectionList";

type Props = {
  analysis: Analysis;
  decisions: Decisions;
  categoryDefaults: CategoryDefaults;
  entityStrategies: EntityStrategies;
  catalog: TransformCatalog | null;
  activeId: string | null;
  profile: PrivacyProfile;
  outputFormat: OutputFormat;
  manual: ManualItem[];
  busy: boolean;
  language: string;
  initialsFontSize?: number;
  onInitialsFontSizeChange?: (size: number) => void;
  t: (key: string, options?: Record<string, unknown>) => string;
  onSelect: (id: string | null) => void;
  onSelectManual?: (id: string) => void;
  selectedManualId?: string | null;
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
  onManualChange: (items: ManualItem[]) => void;
  onAddCustomTerm?: (term: UserDefinedTerm) => void | Promise<void>;
  showPreserved?: boolean;
  onShowPreservedChange?: (show: boolean) => void;
  onMergeMatch?: (entityIds: string[]) => void | Promise<void>;
  onKeepSeparateMatch?: (entityIds: string[]) => void | Promise<void>;
  manualMergeSourceId?: string | null;
  onCancelManualMerge?: () => void;
  onManualMerge?: (entityIds: string[]) => void | Promise<void>;
  mergeNotice?: string | null;
  onReclassify?: (entityId: string, entityType: string) => void | Promise<void>;
  onRemoveFindings?: (entityIds: string[]) => void;
};

export function ReviewPanel({
  analysis,
  decisions,
  categoryDefaults,
  entityStrategies,
  catalog,
  activeId,
  manual,
  busy,
  language,
  initialsFontSize = 11,
  onInitialsFontSizeChange,
  t,
  onSelect,
  onSelectManual,
  selectedManualId = null,
  onDecision,
  onBulk,
  onCategoryDefault,
  onEntityStrategy,
  onManualChange,
  onAddCustomTerm,
  showPreserved = false,
  onShowPreservedChange,
  onMergeMatch,
  onKeepSeparateMatch,
  manualMergeSourceId = null,
  onCancelManualMerge,
  onManualMerge,
  mergeNotice = null,
  onReclassify,
  onRemoveFindings,
}: Props) {
  const analysisStatus = analysisStatusOf(analysis);
  const empty = analysis.entities.length === 0 && manual.length === 0;
  const showInitialsSize = needsInitialsSizeControl(
    analysis.entities,
    decisions,
    categoryDefaults,
    entityStrategies,
  );

  const notices = (
    <>
      {empty && (
        <div className="empty-detections">
          <p>{t("emptyDetections")}</p>
          <p className="panel-help">
            {analysisStatus === "COMPLETE"
              ? t("emptyCompleteHint")
              : t("emptyPartialHint")}
          </p>
        </div>
      )}
    </>
  );

  const initialsControl =
    showInitialsSize && onInitialsFontSizeChange ? (
      <div className="initials-size-control">
        <label className="output-format-row">
          <span>{t("workspace.initialsFontSize")}</span>
          <select
            value={initialsFontSize}
            onChange={(event) =>
              onInitialsFontSizeChange(Number(event.target.value))
            }
          >
            {DOCUMENT_FONT_SIZES.map((size) => (
              <option key={size} value={size}>
                {t("workspace.fontSizeUnit", { size })}
              </option>
            ))}
          </select>
        </label>
        <p className="panel-help">{t("workspace.initialsFontSizeHelp")}</p>
      </div>
    ) : null;

  return (
    <aside className="review-panel">
      <DetectionList
        entities={analysis.entities}
        decisions={decisions}
        categoryDefaults={categoryDefaults}
        entityStrategies={entityStrategies}
        catalog={catalog}
        language={language}
        activeId={activeId}
        showPreserved={showPreserved}
        onShowPreservedChange={onShowPreservedChange}
        beforeList={
          <>
            {initialsControl}
            {notices}
          </>
        }
        t={t}
        manual={manual}
        selectedManualId={selectedManualId}
        onSelect={(id) => onSelect(id)}
        onSelectManual={onSelectManual}
        onManualToggle={(id, hide) => {
          onManualChange(
            manual.map((item, index) =>
              manualItemId(item, index) === id
                ? { ...item, kept: !hide }
                : item,
            ),
          );
        }}
        onManualRemove={(id) => {
          onManualChange(
            manual.filter((item, index) => manualItemId(item, index) !== id),
          );
        }}
        onDecision={onDecision}
        onBulkDecision={onBulk}
        onEntityStrategy={onEntityStrategy}
        onCategoryDefault={onCategoryDefault}
        pageTexts={
          analysis.page_texts?.length ? analysis.page_texts : [analysis.text]
        }
        busy={busy}
        onAddCustomTerm={onAddCustomTerm}
        possibleMatches={analysis.possible_matches ?? []}
        onMergeMatch={onMergeMatch}
        onKeepSeparateMatch={onKeepSeparateMatch}
        manualMergeSourceId={manualMergeSourceId}
        onCancelManualMerge={onCancelManualMerge}
        onManualMerge={onManualMerge}
        mergeNotice={mergeNotice}
        onReclassify={onReclassify}
        onRemoveFindings={onRemoveFindings}
      />
    </aside>
  );
}
