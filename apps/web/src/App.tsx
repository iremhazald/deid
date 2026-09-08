import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  addCustomTerms,
  analyzeDocument,
  deleteJob,
  fetchTransformCatalog,
  mergeEntityMatch,
  reclassifyEntities,
  rejectEntityMatch,
  updateJobProfile,
  previewJob,
  redactJob,
} from "./api/client";
import { ExportResult } from "./components/export/ExportResult";
import { Header } from "./components/layout/Header";
import { UploadFooter } from "./components/layout/UploadFooter";
import { WorkflowProgress } from "./components/layout/WorkflowProgress";
import { ProcessingStatus } from "./components/processing/ProcessingStatus";
import { ReviewWorkspace } from "./components/review/ReviewWorkspace";
import { DEFAULT_TEXT_SIZE } from "./components/review/documentFonts";
import { UploadHero } from "./components/upload/UploadHero";
import { ValidationProgress } from "./components/validation/ValidationProgress";
import { githubUrl } from "./config/project";
import {
  mergeCategoryDefaults,
  mergeProfileDecisions,
  previewTransformLocal,
  relatedEntityIds,
  expandRelatedIds,
  exportRectanglesForEntity,
  seedCategoryDefaults,
  seedDecisions,
  customTermTargetIds,
  seedEntityStrategies,
  tallyDecisions,
  canApplyRedactions,
} from "./state/helpers";
import { analysisWithoutRemovedFindings } from "./state/findingContextMenu";
import type {
  Analysis,
  CategoryDefaults,
  DecisionAction,
  DecisionScope,
  Decisions,
  EntityStrategies,
  ManualRect,
  ManualRedaction,
  OutputFormat,
  PrivacyProfile,
  PurposePreset,
  Result,
  TransformationStrategy,
  TransformCatalog,
  UserDefinedTerm,
  WorkflowPhase,
} from "./state/types";
import { isAcceptedUpload, MAX_FILE_MB } from "./state/types";
import {
  analyzeLanguagePayload,
  documentTagLanguage,
  nextDocumentLanguageAfterUiSwitch,
  type DocumentLanguage,
} from "./state/documentLanguage";
import {
  analyzeModeForNormalScan,
} from "./state/scanFlow";

function languagePath(language?: string) {
  const code = language ?? (window.location.pathname.startsWith("/en") ? "en" : "tr");
  return code === "en" ? "/en" : "/";
}

function setAppHash(hash: "upload" | "workspace" | "") {
  const next = hash ? `${languagePath()}#${hash}` : languagePath();
  const current = `${window.location.pathname}${window.location.hash}`;
  if (current === next) return;
  window.history.replaceState(null, "", next);
}

function App() {
  const { t, i18n } = useTranslation();
  const [phase, setPhase] = useState<WorkflowPhase>("upload");
  const [profile, setProfile] = useState<PrivacyProfile>("GENERAL");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [decisions, setDecisions] = useState<Decisions>({});
  const [categoryDefaults, setCategoryDefaults] = useState<CategoryDefaults>(
    {},
  );
  const [entityStrategies, setEntityStrategies] = useState<EntityStrategies>(
    {},
  );
  const [catalog, setCatalog] = useState<TransformCatalog | null>(null);
  const [serverPreview, setServerPreview] = useState<string | null>(null);
  const [tokenOverrides, setTokenOverrides] = useState<Record<string, string>>(
    {},
  );
  const [initialsFontSize, setInitialsFontSize] = useState(DEFAULT_TEXT_SIZE);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [manual, setManual] = useState<ManualRedaction[]>([]);
  const [boxOverrides, setBoxOverrides] = useState<
    Record<string, ManualRect[]>
  >({});
  const [entityFills, setEntityFills] = useState<Record<string, string>>({});
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("TXT");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [processStep, setProcessStep] = useState(0);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [customTerms, setCustomTerms] = useState<UserDefinedTerm[]>([]);
  const [flashEntityIds, setFlashEntityIds] = useState<string[]>([]);
  const [removedEntityIds, setRemovedEntityIds] = useState<string[]>([]);
  const [documentLanguage, setDocumentLanguage] = useState<DocumentLanguage>(null);
  const [purposePreset, setPurposePreset] = useState<PurposePreset>("ANONYMIZED");

  const locale = (i18n.language.startsWith("tr") ? "tr" : "en") as "tr" | "en";
  const tagLanguage = analysis ? documentTagLanguage(analysis) : locale;

  useEffect(() => {
    void fetchTransformCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  const workflowIndex =
    result || phase === "export"
      ? 2
      : analysis || phase === "review" || phase === "processing" || phase === "validating"
        ? 1
        : 0;

  const localizeMessage = (code: string) => {
    if (code === "Failed to fetch" || code === "API_UNREACHABLE") {
      return t("messages.API_UNREACHABLE");
    }
    if (code.startsWith("RESIDUAL_STRUCTURED:")) {
      const types = code
        .slice("RESIDUAL_STRUCTURED:".length)
        .split(",")
        .filter(Boolean)
        .map((type) => t(`categories.${type}`, { defaultValue: type }))
        .join(", ");
      return t("messages.RESIDUAL_STRUCTURED", { types });
    }
    return t(`messages.${code}`, { defaultValue: code });
  };

  const switchLanguage = async (language: "tr" | "en") => {
    await i18n.changeLanguage(language);
    document.documentElement.lang = language;
    document.title = "DeID";
    const hash = window.location.hash;
    window.history.replaceState(null, "", `${languagePath(language)}${hash}`);
    setDocumentLanguage((current) =>
      nextDocumentLanguageAfterUiSwitch(current, language),
    );
  };

  useEffect(() => {
    document.title = "DeID";
  }, [i18n.language]);

  useEffect(() => {
    if (flashEntityIds.length === 0) return;
    const timer = window.setTimeout(() => setFlashEntityIds([]), 900);
    return () => window.clearTimeout(timer);
  }, [flashEntityIds]);

  useEffect(() => {
    if (
      phase === "review" ||
      phase === "processing" ||
      phase === "validating" ||
      phase === "export"
    ) {
      setAppHash("workspace");
      return;
    }
    if (phase === "upload" && window.location.hash === "#workspace") {
      setAppHash("");
    }
  }, [phase]);

  useEffect(() => {
    if (phase !== "processing" && phase !== "validating") {
      setProcessStep(0);
      return;
    }
    setProcessStep(0);
    const timers = [400, 1100, 1900].map((delay, index) =>
      window.setTimeout(() => setProcessStep(index + 1), delay),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [phase]);

  const receive = (
    data: Analysis,
    nextCatalog: TransformCatalog | null = catalog,
    preset: PurposePreset = purposePreset,
  ) => {
    setAnalysis(data);
    setTokenOverrides({});
    setProfile(data.profile ?? "GENERAL");
    setDecisions(seedDecisions(data.entities, preset));
    setCategoryDefaults(seedCategoryDefaults(data.entities, nextCatalog, preset));
    setEntityStrategies(seedEntityStrategies(data.entities, nextCatalog, preset));
    setServerPreview(null);
    setActiveId(null);
    setFlashEntityIds([]);
    setRemovedEntityIds([]);
    setManual([]);
    setBoxOverrides({});
    setEntityFills({});
    setResult(null);
    setPhase("review");
  };

  const upload = async (file: File) => {
    setPhase("processing");
    setError("");
    setResult(null);
    try {
      const nextCatalog =
        catalog ?? (await fetchTransformCatalog().catch(() => null));
      if (nextCatalog) setCatalog(nextCatalog);
      receive(
        await analyzeDocument(
          file,
          "GENERAL",
          analyzeModeForNormalScan(),
          {
            customTerms,
            documentLanguage: analyzeLanguagePayload(documentLanguage, locale),
          },
        ),
        nextCatalog,
      );
    } catch (cause) {
      setError(
        cause instanceof Error ? localizeMessage(cause.message) : String(cause),
      );
      setPhase("upload");
    }
  };

  const holdFile = (file: File) => {
    if (!isAcceptedUpload(file)) return;
    setPendingFile(file);
    setError("");
  };

  const startScan = () => {
    if (!pendingFile) return;
    void upload(pendingFile);
  };

  const changeProfile = async (next: PrivacyProfile) => {
    if (!analysis || next === profile) {
      setProfile(next);
      return;
    }
    setProfile(next);
    try {
      const updated = await updateJobProfile(analysis.job_id, next);
      setDecisions((current) =>
        mergeProfileDecisions(updated.entities, current, analysis.entities),
      );
      setCategoryDefaults((current) =>
        mergeCategoryDefaults(updated.entities, current, catalog, purposePreset),
      );
      setAnalysis(updated);
      setTokenOverrides({});
    } catch (cause) {
      setError(
        cause instanceof Error ? localizeMessage(cause.message) : String(cause),
      );
    }
  };

  const buildPayload = () => {
    if (!analysis) return null;
    const removed = new Set(removedEntityIds);
    return {
      decisions: analysis.entities.map((entity) => {
        if (removed.has(entity.id)) {
          return {
            entity_id: entity.id,
            action: "KEEP" as DecisionAction,
            strategy: "KEEP" as TransformationStrategy,
            source: "occurrence_override" as const,
          };
        }
        const action = decisions[entity.id] ?? "KEEP";
        const strategy =
          action === "KEEP"
            ? ("KEEP" as TransformationStrategy)
            : (entityStrategies[entity.id] ??
              categoryDefaults[entity.type] ??
              "REDACT");
        const related = relatedEntityIds(entity.id, analysis.entities);
        const source = !entityStrategies[entity.id]
          ? ("default" as const)
          : related.length > 1
              && related.some((id) => (
                (entityStrategies[id] ?? categoryDefaults[entity.type])
                !== strategy
              ))
            ? ("occurrence_override" as const)
            : ("user_override" as const);
        const rectangles = exportRectanglesForEntity(
          entity,
          analysis,
          boxOverrides,
        );
        const fill = entityFills[entity.id];
        const parameters = {
          ...(rectangles?.length ? { rectangles } : {}),
          ...(fill ? { fill } : {}),
        };
        return {
          entity_id: entity.id,
          action,
          strategy,
          source,
          ...(Object.keys(parameters).length ? { parameters } : {}),
        };
      }),
      categoryDefaults: Object.entries(categoryDefaults).map(
        ([category, strategy]) => ({
          category,
          strategy,
        }),
      ),
      manual: manual.filter((item) => !item.kept),
      outputFormat:
        analysis.document_kind === "TEXT"
          ? outputFormat
          : analysis.document_kind,
      locale: tagLanguage,
      initialsFontSize,
    };
  };

  useEffect(() => {
    if (!analysis || phase !== "review") return;
    const visible = analysisWithoutRemovedFindings(analysis, removedEntityIds);
    const local = previewTransformLocal(
      visible.text,
      visible.entities,
      decisions,
      categoryDefaults,
      entityStrategies,
      tagLanguage,
    );
    setServerPreview(local);

    const payload = buildPayload();
    if (!payload) return;
    const handle = window.setTimeout(() => {
      void previewJob(analysis.job_id, payload)
        .then((response) => {
          setServerPreview(response.text);
          if (response.placeholder_tokens) {
            setTokenOverrides(response.placeholder_tokens);
          }
        })
        .catch(() => {
          /* keep local preview */
        });
    }, 350);
    return () => window.clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    analysis,
    decisions,
    categoryDefaults,
    entityStrategies,
    manual,
    tagLanguage,
    phase,
    initialsFontSize,
    boxOverrides,
    entityFills,
    removedEntityIds,
  ]);

  const applyRedactions = async () => {
    if (!analysis) return;
    if (!canApplyRedactions(visibleDecisions, manual)) {
      setError(localizeMessage("NO_TRANSFORMATIONS_SELECTED"));
      return;
    }
    const payload = buildPayload();
    if (!payload) return;
    setPhase("validating");
    setError("");
    try {
      const response = await redactJob(analysis.job_id, payload);
      setResult(response);
      setPhase("export");
    } catch (cause) {
      setError(
        cause instanceof Error ? localizeMessage(cause.message) : String(cause),
      );
      setPhase("review");
    }
  };

  const requestApply = () => {
    void applyRedactions();
  };

  const reset = () => {
    if (analysis) void deleteJob(analysis.job_id);
    setAnalysis(null);
    setTokenOverrides({});
    setResult(null);
    setDecisions({});
    setCategoryDefaults({});
    setEntityStrategies({});
    setServerPreview(null);
    setManual([]);
    setBoxOverrides({});
    setEntityFills({});
    setProfile("GENERAL");
    setActiveId(null);
    setError("");
    setPendingFile(null);
    setRemovedEntityIds([]);
    setPurposePreset("ANONYMIZED");
    setPhase("upload");
  };

  const goToUpload = () => {
    reset();
    window.history.pushState(null, "", "#upload");
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  };

  const setDecision = (
    id: string,
    action: DecisionAction,
    scope: DecisionScope = "entity",
  ) => {
    if (!analysis || scope === "occurrence") {
      setDecisions((current) => ({ ...current, [id]: action }));
      return;
    }
    const ids = relatedEntityIds(id, analysis.entities);
    setDecisions((current) => ({
      ...current,
      ...Object.fromEntries(ids.map((entityId) => [entityId, action])),
    }));
  };

  const setBulk = (ids: string[], action: DecisionAction) => {
    const expanded = analysis ? expandRelatedIds(ids, analysis.entities) : ids;
    setDecisions((current) => ({
      ...current,
      ...Object.fromEntries(expanded.map((id) => [id, action])),
    }));
  };

  const visibleDecisions = useMemo(() => {
    if (removedEntityIds.length === 0) return decisions;
    const removed = new Set(removedEntityIds);
    const visible: Decisions = {};
    for (const [id, action] of Object.entries(decisions)) {
      if (!removed.has(id)) visible[id] = action;
    }
    return visible;
  }, [decisions, removedEntityIds]);

  const tally = useMemo(
    () => tallyDecisions(visibleDecisions, manual),
    [visibleDecisions, manual],
  );

  const processingSteps = [
    { key: "extract", label: t("processingSteps.extract") },
    { key: "structured", label: t("processingSteps.structured") },
    { key: "prepare", label: t("processingSteps.prepare") },
  ].map((step, index) => ({
    ...step,
    status: (index < processStep
      ? "done"
      : index === processStep
        ? "active"
        : "pending") as "done" | "active" | "pending",
  }));

  const validationSteps = [
    { key: "ids", label: t("validationSteps.ids") },
    { key: "emails", label: t("validationSteps.emails") },
    { key: "layer", label: t("validationSteps.layer") },
    { key: "contextual", label: t("validationSteps.contextual") },
  ].map((step, index) => ({
    ...step,
    status: (index < processStep
      ? "done"
      : index === processStep
        ? "active"
        : "pending") as "done" | "active" | "pending",
  }));

  const reviewAnalysis = useMemo(() => {
    if (!analysis) return null;
    const filtered = analysisWithoutRemovedFindings(analysis, removedEntityIds);
    if (!Object.keys(tokenOverrides).length) return filtered;
    return {
      ...filtered,
      entities: filtered.entities.map((entity) => {
        const token = tokenOverrides[entity.id];
        return token ? { ...entity, placeholder_token: token } : entity;
      }),
    };
  }, [analysis, tokenOverrides, removedEntityIds]);

  const applyMatch = async (
    entityIds: string[],
    action: "merge" | "reject",
  ) => {
    if (!analysis) return;
    try {
      const updated =
        action === "merge"
          ? await mergeEntityMatch(analysis.job_id, entityIds)
          : await rejectEntityMatch(analysis.job_id, entityIds);
      setAnalysis(updated);
      setTokenOverrides({});
    } catch (cause) {
      setError(
        cause instanceof Error ? localizeMessage(cause.message) : String(cause),
      );
    }
  };

  const applyReclassify = async (entityId: string, entityType: string) => {
    if (!analysis) return;
    const entityIds = relatedEntityIds(entityId, analysis.entities);
    try {
      const updated = await reclassifyEntities(
        analysis.job_id,
        entityIds,
        entityType,
      );
      setAnalysis(updated);
      setTokenOverrides({});
    } catch (cause) {
      setError(
        cause instanceof Error ? localizeMessage(cause.message) : String(cause),
      );
    }
  };

  const isWorkspace = phase === "review";
  const showWorkflow =
    phase === "processing" || phase === "validating" || phase === "export";

  return (
    <div className={`app-shell${phase === "upload" ? " landing" : ""}${isWorkspace ? " is-review" : ""}`}>
      <Header
        brand={t("brand")}
        language={i18n.language}
        githubUrl={githubUrl()}
        githubLabel={t("github")}
        languageLabel={t("language")}
        variant={isWorkspace ? "workspace" : "landing"}
        workspaceLabel={t("workspace.title")}
        backLabel={t("workspace.newDocument")}
        newDocumentLabel={t("workspace.newDocument")}
        primaryAction={
          isWorkspace
            ? {
                label: t("apply"),
                count: tally.redact,
                busy: false,
                busyLabel: t("validating"),
                disabled: tally.redact === 0,
                disabledHint: t("noApplyWithoutSelection"),
                onClick: requestApply,
              }
            : undefined
        }
        onReset={reset}
        onNewDocument={goToUpload}
        onLanguageChange={(language) => void switchLanguage(language)}
      >
        {showWorkflow && (
          <WorkflowProgress
            label={t("workflowLabel")}
            currentIndex={workflowIndex}
            steps={[
              { key: "upload", label: t("workflow.upload") },
              { key: "review", label: t("workflow.review") },
              { key: "output", label: t("workflow.output") },
            ]}
          />
        )}
      </Header>

      <main className="app-main">
        {phase === "upload" && (
          <UploadHero
            eyebrow={t("heroEyebrow")}
            titleRedacted={t("heroTitleRedacted")}
            titleLead={t("heroTitleLead")}
            titleTail={t("heroTitleTail")}
            titleMuted={t("heroTitleMuted")}
            subtitle={t("heroBody")}
            ctaLabel={t("heroCta")}
            openSourceTitle={t("openSource.title")}
            openSourceBody={t("openSource.body")}
            openSourceLinkLabel={t("openSource.link")}
            githubUrl={githubUrl()}
            uploadTitle={t("uploadTitle")}
            uploadBody={t("uploadBody")}
            dropTitle={t("dropHint")}
            browseLabel={t("browse")}
            limitsLabel={t("fileLimits", { mb: MAX_FILE_MB })}
            processing={false}
            privacyTitle={t("privacyTitle")}
            privacyBody={t("privacyBody")}
            privacyToggle={t("privacyToggle")}
            t={t}
            onUpload={holdFile}
            onStartScan={startScan}
            selectedFileName={pendingFile?.name}
            documentLanguage={documentLanguage}
            onDocumentLanguageChange={setDocumentLanguage}
          />
        )}

        {phase === "processing" && (
          <ProcessingStatus title={t("processing")} steps={processingSteps} />
        )}

        {phase === "review" && reviewAnalysis && (
          <ReviewWorkspace
            analysis={reviewAnalysis}
            decisions={decisions}
            categoryDefaults={categoryDefaults}
            entityStrategies={entityStrategies}
            catalog={catalog}
            previewText={serverPreview ?? reviewAnalysis.text}
            activeId={activeId}
            flashEntityIds={flashEntityIds}
            profile={profile}
            outputFormat={outputFormat}
            manual={manual}
            busy={false}
            language={tagLanguage}
            t={(key, options) => {
              if (key.startsWith("messages.")) {
                const code = key.slice("messages.".length);
                return localizeMessage(code);
              }
              return t(key, options);
            }}
            initialsFontSize={initialsFontSize}
            onInitialsFontSizeChange={setInitialsFontSize}
            onSelect={setActiveId}
            onDecision={setDecision}
            onBulk={setBulk}
            onProfileChange={(value) => void changeProfile(value)}
            onCategoryDefault={(type, strategy) => {
              const previous = categoryDefaults[type];
              setCategoryDefaults((current) => ({
                ...current,
                [type]: strategy,
              }));
              if (!analysis) return;
              const oldAction = previous === "KEEP" ? "KEEP" : "REDACT";
              const newAction = strategy === "KEEP" ? "KEEP" : "REDACT";
              setDecisions((current) => {
                const next = { ...current };
                for (const entity of analysis.entities) {
                  if (entity.type !== type) continue;
                  if (entityStrategies[entity.id]) continue;
                  if ((current[entity.id] ?? oldAction) === oldAction) {
                    next[entity.id] = newAction;
                  }
                }
                return next;
              });
            }}
            onEntityStrategy={(id, strategy, scope = "entity") => {
              const ids =
                scope === "occurrence" || !analysis
                  ? [id]
                  : relatedEntityIds(id, analysis.entities);
              setEntityStrategies((current) => ({
                ...current,
                ...Object.fromEntries(
                  ids.map((entityId) => [entityId, strategy]),
                ),
              }));
              const action = strategy === "KEEP" ? "KEEP" : "REDACT";
              setDecisions((current) => ({
                ...current,
                ...Object.fromEntries(
                  ids.map((entityId) => [entityId, action as DecisionAction]),
                ),
              }));
            }}
            onRestoreState={(snapshot) => {
              setDecisions(snapshot.decisions);
              setEntityStrategies(snapshot.entityStrategies);
              setCategoryDefaults(snapshot.categoryDefaults);
              setManual(snapshot.manual);
              setBoxOverrides(snapshot.boxOverrides ?? {});
              setEntityFills(snapshot.entityFills ?? {});
              setRemovedEntityIds(snapshot.removedEntityIds ?? []);
            }}
            removedEntityIds={removedEntityIds}
            onRemovedEntityIdsChange={setRemovedEntityIds}
            boxOverrides={boxOverrides}
            entityFills={entityFills}
            onBoxResize={(entityId, rectangles) => {
              setBoxOverrides((current) => ({
                ...current,
                [entityId]: rectangles,
              }));
            }}
            onEntityFill={(entityId, fill) => {
              setEntityFills((current) => ({
                ...current,
                [entityId]: fill,
              }));
            }}
            onOutputFormatChange={setOutputFormat}
            onManualChange={setManual}
            onMergeMatch={(entityIds) => applyMatch(entityIds, "merge")}
            onKeepSeparateMatch={(entityIds) => applyMatch(entityIds, "reject")}
            onReclassify={applyReclassify}
            onAddCustomTerm={(term) => {
              if (!analysis) {
                return Promise.reject(new Error("ANALYSIS_REQUIRED"));
              }
              const previousIds = analysis.entities.map((entity) => entity.id);
              return addCustomTerms(analysis.job_id, [term])
                .then((data) => {
                  const addedIds = customTermTargetIds(
                    data.entities,
                    term,
                    previousIds,
                  );
                  if (addedIds.length === 0) {
                    throw new Error("CUSTOM_TERM_NOT_ADDED");
                  }
                  const hide =
                    !term.strategy || term.strategy === "KEEP"
                      ? "KEEP"
                      : "REDACT";
                  const applied =
                    term.strategy && term.strategy !== "KEEP"
                      ? term.strategy
                      : "REDACT";
                  setCustomTerms((current) => [...current, term]);
                  setAnalysis(data);
                  setTokenOverrides({});
                  setDecisions((previous) => {
                    const next = {
                      ...seedDecisions(data.entities, purposePreset),
                      ...previous,
                    };
                    for (const id of addedIds) next[id] = hide;
                    return next;
                  });
                  setEntityStrategies((current) => {
                    if (hide === "KEEP") return current;
                    const next = { ...current };
                    for (const id of addedIds) next[id] = applied;
                    return next;
                  });
                  setActiveId(addedIds[0] ?? null);
                  setFlashEntityIds(addedIds);
                })
                .catch((cause) => {
                  if (
                    cause instanceof Error &&
                    cause.message === "CUSTOM_TERM_NOT_ADDED"
                  ) {
                    throw cause;
                  }
                  setError(
                    cause instanceof Error ? cause.message : String(cause),
                  );
                  throw cause;
                });
            }}
          />
        )}

        {phase === "validating" && (
          <ValidationProgress title={t("validating")} steps={validationSteps} />
        )}

        {phase === "export" && result && analysis && (
          <ExportResult
            result={result}
            countLabel={t("redactionApplied", { count: tally.redact })}
            downloadLabel={t("downloadDocument")}
            backLabel={t("backToWork")}
            readyTitle={t("exportReadyTitle")}
            failTitle={t("exportFailTitle")}
            failBody={t("exportFailBody")}
            warnTitle={t("exportWarnTitle")}
            warnBody={t("exportWarnBody")}
            onReset={() => setPhase("review")}
          />
        )}
      </main>

      {phase === "upload" && <UploadFooter />}

      {error && (
        <div className="toast" role="alert">
          <div>
            <strong>{t("error")}</strong>
            <p>{error}</p>
          </div>
          <button
            type="button"
            onClick={() => setError("")}
            aria-label={t("close")}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
