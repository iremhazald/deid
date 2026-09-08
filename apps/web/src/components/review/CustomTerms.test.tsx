import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { CustomTerms } from "./CustomTerms";
import tr from "../../locales/tr.json";

const t = (key: string, options?: Record<string, unknown>) => {
  const parts = key.split(".");
  let current: unknown = tr;
  for (const part of parts) {
    if (typeof current !== "object" || current === null || !(part in current)) {
      return key;
    }
    current = (current as Record<string, unknown>)[part];
  }
  if (typeof current !== "string") return key;
  return current.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
    String(options?.[name] ?? ""),
  );
};

describe("CustomTerms", () => {
  it("embeds the phrase-search form used by the custom detection pane", () => {
    const html = renderToStaticMarkup(
      <CustomTerms
        embedded
        t={t}
        pageTexts={["Ayşe Demir mahkemeye başvurdu."]}
        onAdd={() => undefined}
      />,
    );
    expect(html).toContain(tr.workspace.customSearchLead);
    expect(html).toContain(tr.workspace.customSearchHint);
    expect(html).toContain(tr.workspace.customTermType);
    expect(html).toContain(tr.workspace.categoryMethod);
    expect(html).toContain(t("workspace.customSearchMask", { count: 0 }));
    expect(html).toContain(tr.workspace.customTermCategories.PERSON_NAME);
    expect(html).not.toContain("Sözlüğe de ekle");
    expect(html).not.toContain(tr.workspace.customSearchUnavailable);
  });

  it("keeps added custom-term records under the search form", () => {
    const html = renderToStaticMarkup(
      <CustomTerms
        embedded
        t={t}
        pageTexts={["Ayşe Demir mahkemeye başvurdu."]}
        history={[
          { value: "Ayşe Demir", category: "PERSON_NAME", count: 1 },
        ]}
        onAdd={() => undefined}
      />,
    );
    expect(html).toContain(tr.workspace.customSearchHistory);
    expect(html).toContain("Ayşe Demir");
    expect(html).toContain(tr.workspace.customTermCategories.PERSON_NAME);
  });
});
