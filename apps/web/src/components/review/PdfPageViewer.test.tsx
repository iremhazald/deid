import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { Entity } from "../../state/types";
import {
  dropTinySiblingRects,
  expandInitialsCoverRect,
  fitPlaceholderCoverRect,
  initialsLabelInset,
  PdfPageViewer,
  peekOverlayIds,
  replacementCoverRects,
  stackedInitialsEntityIds,
  hydratePdfPageIndexes,
} from "./PdfPageViewer";

const iban: Entity = {
  id: "iban-1",
  text: "TR33 0006 1005 1978 6457 8413 26",
  type: "IBAN",
  start: 20,
  end: 52,
  page: 0,
  detector: "GLOBAL_IBAN",
  method: "DETERMINISTIC",
  validated: true,
  recommended: true,
  recommended_strategy: "REDACT",
};

const person: Entity = {
  id: "name-1",
  text: "Emine ELİTAŞ",
  type: "PERSON_NAME",
  start: 0,
  end: 12,
  page: 0,
  detector: "TR_ROLE_PERSON",
  method: "DETERMINISTIC",
  validated: true,
  recommended: true,
  recommended_strategy: "REDACT",
};

describe("hydratePdfPageIndexes", () => {
  it("loads only nearby pages around the current sheet", () => {
    expect(hydratePdfPageIndexes(1, 32)).toEqual([0, 1, 2]);
    expect(hydratePdfPageIndexes(18, 32)).toEqual([15, 16, 17, 18, 19]);
  });
});

describe("PdfPageViewer page hydration", () => {
  it("does not request every page image on first paint", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={8}
        entities={[person]}
        decisions={{}}
        categoryDefaults={{}}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="detections"
        tool="select"
        pageWidth={560}
        language="tr"
        initialPages={Array.from({ length: 8 }, (_, page) => ({
          page,
          width: 595,
          height: 842,
          spans: [],
        }))}
      />,
    );
    expect(html.match(/pdf-page-wrap/g)?.length).toBe(8);
    expect(html.match(/pdf-page-img/g)?.length).toBe(3);
    expect(html).toContain("/pages/0?scale=1.5");
    expect(html).not.toContain("/pages/7?scale=1.5");
  });
});

describe("overlapping overlay peek", () => {
  const numberBox = { x0: 80, y0: 120, x1: 160, y1: 136 };
  const esasBox = { x0: 154, y0: 118, x1: 210, y1: 138 };

  it("peeks every mask under the pointer when boxes overlap", () => {
    const items = [
      { id: "case-no", rect: numberBox },
      { id: "docket", rect: esasBox },
    ];
    expect(peekOverlayIds(items, 157, 128).sort()).toEqual(["case-no", "docket"]);
  });

  it("still peeks the covered mask when the pointer is only on the larger neighbor", () => {
    const items = [
      { id: "case-no", rect: numberBox },
      { id: "docket", rect: esasBox },
    ];
    expect(peekOverlayIds(items, 190, 128).sort()).toEqual(["case-no", "docket"]);
  });

  it("does not peek a distant mask", () => {
    const items = [
      { id: "case-no", rect: numberBox },
      { id: "date", rect: { x0: 80, y0: 160, x1: 160, y1: 176 } },
    ];
    expect(peekOverlayIds(items, 100, 128)).toEqual(["case-no"]);
  });
});

describe("PdfPageViewer preview hover reveal", () => {
  it("keeps original PDF glyphs visible under redaction hover instead of rewriting text", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={1}
        entities={[iban, person]}
        decisions={{}}
        categoryDefaults={{}}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="preview"
        tool="select"
        pageWidth={560}
        language="tr"
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "name-1",
                text: "Emine ELİTAŞ",
                type: "PERSON_NAME",
                rectangles: [
                  { x0: 80, y0: 200, x1: 120, y1: 214 },
                  { x0: 124, y0: 200, x1: 180, y1: 214 },
                ],
              },
              {
                entity_id: "iban-1",
                text: "TR33 0006 1005 1978 6457 8413 26",
                type: "IBAN",
                rectangles: [
                  { x0: 200, y0: 200, x1: 240, y1: 214 },
                  { x0: 244, y0: 200, x1: 430, y1: 214 },
                ],
              },
            ],
          },
        ]}
        onSelect={() => undefined}
        onPageInView={() => undefined}
        onDrawComplete={() => undefined}
      />,
    );
    expect(html).not.toContain("pdf-redact-reveal");
    expect(html).not.toContain('title="TR33 0006 1005 1978 6457 8413 26"');
    expect(html).toContain('aria-label="TR33 0006 1005 1978 6457 8413 26"');
    expect(html).toContain('aria-label="Emine ELİTAŞ"');
    expect(html).toContain("is-redact");
  });
});

describe("PdfPageViewer detection resize handles", () => {
  const pages = [
    {
      page: 0,
      width: 595,
      height: 842,
      spans: [
        {
          entity_id: "name-1",
          text: "Emine ELİTAŞ",
          type: "PERSON_NAME",
          rectangles: [{ x0: 80, y0: 200, x1: 180, y1: 214 }],
        },
      ],
    },
  ];

  const base = {
    jobId: "job",
    pageCount: 1,
    entities: [person],
    decisions: {},
    categoryDefaults: {},
    entityStrategies: {},
    manual: [],
    focusId: null,
    currentPage: 1,
    tool: "select" as const,
    pageWidth: 560,
    language: "tr",
    initialPages: pages,
    onSelect: () => undefined,
    onPageInView: () => undefined,
    onDrawComplete: () => undefined,
    onBoxResize: () => undefined,
  };

  it("shows resize handles only after the detection is selected", () => {
    const idle = renderToStaticMarkup(
      <PdfPageViewer {...base} activeId={null} viewMode="detections" />,
    );
    expect(idle).not.toContain("pdf-resize");

    const selected = renderToStaticMarkup(
      <PdfPageViewer {...base} activeId="name-1" viewMode="detections" />,
    );
    expect(selected).toContain("pdf-resize is-n");
    expect(selected).toContain("pdf-resize is-s");
    expect(selected).toContain("pdf-resize is-e");
    expect(selected).toContain("pdf-resize is-w");
    expect(selected).toContain("pdf-entity-frame");
    expect(selected).toContain("view-detections");
    expect(selected).not.toContain("is-cover-clip");
    expect(selected).toContain('data-entity-id="name-1"');
  });

  it("does not show resize handles in preview", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer {...base} activeId="name-1" viewMode="preview" />,
    );
    expect(html).not.toContain("pdf-resize");
  });

  it("keeps the resized mask visible in preview while the detection stays selected", () => {
    const resized = { x0: 70, y0: 190, x1: 220, y1: 236 };
    const html = renderToStaticMarkup(
      <PdfPageViewer
        {...base}
        activeId="name-1"
        viewMode="preview"
        boxOverrides={{ "name-1": [resized] }}
      />,
    );
    expect(html).toContain("is-redact");
    expect(html).toContain("is-active");
    expect(html).toContain("is-peekable");
    expect(html).not.toContain("pdf-peek-original");
    expect(html).toContain(`left:${(resized.x0 / 595) * 100}%`);
    expect(html).toContain(`width:${((resized.x1 - resized.x0) / 595) * 100}%`);
    expect(html).toContain(`height:${((resized.y1 - resized.y0) / 842) * 100}%`);
  });

  it("applies a selected redaction fill in preview", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        {...base}
        activeId="name-1"
        viewMode="preview"
        entityFills={{ "name-1": "#1e3a5f" }}
      />,
    );
    expect(html).toContain("is-redact");
    expect(html).toContain("--pdf-fill:#1e3a5f");
    expect(html).not.toContain("is-paper-redact");
  });

  it("covers sicil numbers with a white curtain in preview", () => {
    const sicil: Entity = {
      id: "sicil-1",
      text: "37690",
      type: "PROFESSIONAL_ID",
      start: 0,
      end: 5,
      page: 0,
      detector: "TR_JUDICIAL_ROSTER",
      method: "DETERMINISTIC",
      validated: true,
      recommended: true,
      recommended_strategy: "REDACT",
    };
    const html = renderToStaticMarkup(
      <PdfPageViewer
        {...base}
        entities={[sicil]}
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "sicil-1",
                text: "37690",
                type: "PROFESSIONAL_ID",
                rectangles: [{ x0: 80, y0: 200, x1: 140, y1: 214 }],
              },
            ],
          },
        ]}
        activeId={null}
        viewMode="preview"
      />,
    );
    expect(html).toContain("is-redact");
    expect(html).toContain("is-paper-redact");
    expect(html).toContain("--pdf-fill:#ffffff");
  });

  it("renders manual areas as detection frames", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        {...base}
        activeId={null}
        viewMode="detections"
        selectedManualId="manual-1"
        onManualBoxResize={() => undefined}
        manual={[
          {
            id: "manual-1",
            text: "[AREA 1-80-200]",
            page: 1,
            category: "OTHER_IDENTIFIER",
            rectangles: [{ x0: 80, y0: 200, x1: 180, y1: 214 }],
          },
        ]}
      />,
    );
    expect(html).toContain("pdf-entity-frame");
    expect(html).toContain("is-manual");
    expect(html).toContain("accent-id");
    expect(html).toContain("pdf-resize is-n");
    expect(html).not.toContain("dashed");
  });
});

describe("PdfPageViewer initials preview cover", () => {
  const names: Entity[] = [
    { ...person, id: "n1", text: "Mehmet Demir" },
    { ...person, id: "n2", text: "Ahmet Bayram" },
    { ...person, id: "n3", text: "Tuğba Kaya" },
  ];

  it("left-aligns stacked initials and grows the cover for diacritics", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={1}
        entities={names}
        decisions={{}}
        categoryDefaults={{ PERSON_NAME: "INITIALS" }}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="preview"
        tool="select"
        pageWidth={560}
        language="tr"
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: names.map((item, index) => ({
              entity_id: item.id,
              text: item.text,
              type: "PERSON_NAME",
              rectangles: [
                {
                  x0: 140 + index,
                  y0: 100 + index * 16,
                  x1: 220 + index * 40,
                  y1: 114 + index * 16,
                },
              ],
            })),
          },
        ]}
        onSelect={() => undefined}
        onPageInView={() => undefined}
        onDrawComplete={() => undefined}
      />,
    );
    expect(html).toContain("is-initials");
    expect(html).toContain("is-cover-clip");
    expect(html).toContain("is-column-initials");
    expect(html).toContain("justify-content:flex-start");
    expect(html).toContain("text-align:left");
    expect(html).toContain("align-items:flex-end");
  });

  it("covers İ/Ğ marks in the line gap but stops at the previous line", () => {
    const origin = { x0: 100, y0: 100, x1: 180, y1: 114 };
    const dotted = expandInitialsCoverRect(origin, 595, 842, "İrem Öztürk");
    expect(dotted.y0).toBeLessThan(origin.y0 - 2);
    expect(dotted.y1).toBeGreaterThanOrEqual(origin.y1);
    const inset = initialsLabelInset(dotted, origin);
    expect(Number.parseFloat(inset.top)).toBeGreaterThan(10);
    const previous = { x0: 80, y0: 82, x1: 220, y1: 96 };
    const clipped = expandInitialsCoverRect(origin, 595, 842, "İrem Ğüneş", [
      previous,
    ]);
    expect(clipped.y0).toBeGreaterThanOrEqual(previous.y1);
    expect(clipped.y0).toBeLessThan(origin.y0);
  });

  it("pads initials covers sideways without eating the previous line", () => {
    const box = { x0: 100, y0: 100, x1: 180, y1: 114 };
    const plain = expandInitialsCoverRect(box, 595, 842, "Mehmet Demir");
    const umlaut = expandInitialsCoverRect(box, 595, 842, "Gülşen Özkan");
    const breve = expandInitialsCoverRect(box, 595, 842, "Tuğba Ğüneş");
    expect(plain.x0).toBeLessThan(box.x0);
    expect(plain.x1).toBeGreaterThan(box.x1);
    expect(plain.y0).toBeLessThan(box.y0);
    expect(umlaut.y0).toBeLessThan(box.y0 - 2);
    expect(breve.y0).toBeLessThan(box.y0 - 4);
    const previous = { x0: 80, y0: 82, x1: 220, y1: 96 };
    expect(
      expandInitialsCoverRect(box, 595, 842, "Tuğba Ğüneş", [previous]).y0,
    ).toBeGreaterThanOrEqual(previous.y1);
    const below = { x0: 100, y0: 118, x1: 200, y1: 130 };
    const band = expandInitialsCoverRect(box, 595, 842, "Gülşen Özkan", [below]);
    expect(band.y1).toBeGreaterThanOrEqual(box.y1);
    expect(band.y1).toBeLessThanOrEqual(below.y0);
    const overlap = expandInitialsCoverRect(box, 595, 842, "İsmail", [
      { x0: 100, y0: 108, x1: 200, y1: 122 },
    ]);
    expect(overlap.y1).toBeGreaterThanOrEqual(box.y1);
  });

  it("keeps placeholder covers from expanding into honorifics", () => {
    const box = { x0: 100, y0: 100, x1: 180, y1: 114 };
    const loose = expandInitialsCoverRect(box, 595, 842, "John Smith");
    const tight = expandInitialsCoverRect(box, 595, 842, "John Smith", [], true);
    expect(tight.x0).toBeGreaterThan(loose.x0);
    expect(box.x0 - tight.x0).toBeLessThanOrEqual(0.5);
  });

  it("does not treat a distant body name as part of the header column", () => {
    const found = stackedInitialsEntityIds([
      { id: "a", rect: { x0: 140, y0: 100, x1: 260, y1: 114 } },
      { id: "b", rect: { x0: 142, y0: 280, x1: 240, y1: 294 } },
    ]);
    expect([...found]).toEqual([]);
  });

  it("treats overlapping court-header rows as a column", () => {
    const found = stackedInitialsEntityIds([
      { id: "a", rect: { x0: 140, y0: 100, x1: 260, y1: 114 } },
      { id: "b", rect: { x0: 146, y0: 110, x1: 330, y1: 124 } },
    ]);
    expect([...found].sort()).toEqual(["a", "b"]);
  });
});

describe("PdfPageViewer court ordinal placeholder", () => {
  const court: Entity = {
    id: "court-1",
    text: "Mersin 9. Ağır Ceza Mahkemesi",
    type: "COURT_NAME",
    start: 10,
    end: 39,
    page: 0,
    detector: "TR_COURT_GRAMMAR",
    method: "DETERMINISTIC",
    validated: true,
    recommended: true,
    recommended_strategy: "PLACEHOLDER",
  };

  const courtBase = {
    jobId: "job",
    pageCount: 1,
    entities: [court],
    decisions: {},
    categoryDefaults: { COURT_NAME: "PLACEHOLDER" as const },
    entityStrategies: { "court-1": "PLACEHOLDER" as const },
    manual: [] as [],
    activeId: null,
    focusId: null,
    currentPage: 1,
    viewMode: "preview" as const,
    tool: "select" as const,
    pageWidth: 560,
    language: "tr",
    onSelect: () => undefined,
    onPageInView: () => undefined,
    onDrawComplete: () => undefined,
  };

  it("does not paint the court name onto leftover word boxes when the ordinal mask is missing", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        {...courtBase}
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "court-1",
                text: "Mersin 9. Ağır Ceza Mahkemesi",
                type: "COURT_NAME",
                rectangles: [{ x0: 180, y0: 200, x1: 220, y1: 214 }],
              },
            ],
          },
        ]}
      />,
    );
    expect(html).not.toContain("pdf-entity-label");
    expect(html).not.toContain("Mersin X");
    expect(html).not.toContain('data-entity-id="court-1"');
  });

  it("covers only the chamber number with an X label", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        {...courtBase}
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "court-1",
                text: "Mersin 9. Ağır Ceza Mahkemesi",
                type: "COURT_NAME",
                rectangles: [
                  { x0: 80, y0: 200, x1: 220, y1: 214 },
                  { x0: 180, y0: 200, x1: 220, y1: 214 },
                ],
                mask_rectangles: [{ x0: 120, y0: 200, x1: 138, y1: 214 }],
              },
            ],
          },
        ]}
      />,
    );
    expect(html).toContain('data-entity-id="court-1"');
    expect(html).toContain("is-placeholder");
    expect(html).toContain("pdf-entity-label");
    expect(html).toContain(">X<");
    expect(html).not.toContain("is-redact");
    expect(html).not.toContain("Mersin X");
  });

  it("sizes the chamber X to the ordinal box instead of a larger detected font", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        {...courtBase}
        entities={[{ ...court, attributes: { font_size: 28 } }]}
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "court-1",
                text: "Mersin 9. Ağır Ceza Mahkemesi",
                type: "COURT_NAME",
                rectangles: [{ x0: 80, y0: 200, x1: 280, y1: 214 }],
                mask_rectangles: [{ x0: 120, y0: 200, x1: 138, y1: 214 }],
              },
            ],
          },
        ]}
      />,
    );
    expect(html).toContain(">X<");
    expect(html).toMatch(/font-size:(9|10|11)\.\d+px/);
    expect(html).not.toMatch(/font-size:2[0-9]/);
    expect(html).toContain("align-items:center");
    expect(html).toContain("justify-content:center");
    expect(html).toContain("height:100%");
    expect(html).not.toContain("align-items:flex-end");
  });
});

describe("PdfPageViewer KEEP overlay cleanup", () => {
  const tribunal: Entity = {
    id: "court-en",
    text: "EMPLOYMENT TRIBUNALS",
    type: "COURT_NAME",
    start: 0,
    end: 21,
    page: 0,
    detector: "EN_COURT",
    method: "DETERMINISTIC",
    validated: true,
    recommended: false,
    recommended_strategy: "KEEP",
  };
  const company: Entity = {
    id: "co-1",
    text: "Wechseln Limited",
    type: "COMPANY_NAME",
    start: 22,
    end: 38,
    page: 0,
    detector: "EN_COMPANY",
    method: "DETERMINISTIC",
    validated: true,
    recommended: false,
    recommended_strategy: "KEEP",
  };
  const personKeep: Entity = {
    id: "name-keep",
    text: "Lauren De Lacey",
    type: "PERSON_NAME",
    start: 39,
    end: 54,
    page: 0,
    detector: "EN_PARTY",
    method: "DETERMINISTIC",
    validated: true,
    recommended: true,
    recommended_strategy: "REDACT",
  };
  const qr: Entity = {
    id: "qr-1",
    text: "[QR]",
    type: "QR_CODE",
    start: 55,
    end: 59,
    page: 0,
    detector: "QR_CODE_VISUAL",
    method: "DETERMINISTIC",
    validated: true,
    recommended: true,
    recommended_strategy: "REDACT",
  };

  const pages = [
    {
      page: 0,
      width: 595,
      height: 842,
      spans: [
        {
          entity_id: "court-en",
          text: "EMPLOYMENT TRIBUNALS",
          type: "COURT_NAME",
          rectangles: [{ x0: 80, y0: 80, x1: 240, y1: 96 }],
        },
        {
          entity_id: "co-1",
          text: "Wechseln Limited",
          type: "COMPANY_NAME",
          rectangles: [{ x0: 80, y0: 110, x1: 200, y1: 124 }],
        },
        {
          entity_id: "name-keep",
          text: "Lauren De Lacey",
          type: "PERSON_NAME",
          rectangles: [{ x0: 80, y0: 140, x1: 190, y1: 154 }],
        },
        {
          entity_id: "qr-1",
          text: "[QR]",
          type: "QR_CODE",
          rectangles: [{ x0: 400, y0: 40, x1: 460, y1: 100 }],
        },
      ],
    },
  ];

  const base = {
    jobId: "job",
    pageCount: 1,
    entities: [tribunal, company, personKeep, qr],
    decisions: {
      "court-en": "KEEP" as const,
      "co-1": "KEEP" as const,
      "name-keep": "REDACT" as const,
      "qr-1": "REDACT" as const,
    },
    categoryDefaults: {
      COURT_NAME: "KEEP" as const,
      COMPANY_NAME: "KEEP" as const,
      PERSON_NAME: "REDACT" as const,
      QR_CODE: "REDACT" as const,
    },
    entityStrategies: {},
    manual: [] as [],
    activeId: null,
    focusId: null,
    currentPage: 1,
    viewMode: "detections" as const,
    tool: "select" as const,
    pageWidth: 560,
    language: "en",
    initialPages: pages,
    onSelect: () => undefined,
    onPageInView: () => undefined,
    onDrawComplete: () => undefined,
  };

  it("hides KEEP court and company overlays by default", () => {
    const html = renderToStaticMarkup(<PdfPageViewer {...base} />);
    expect(html).not.toContain('data-entity-id="court-en"');
    expect(html).not.toContain('data-entity-id="co-1"');
    expect(html).not.toContain('aria-label="EMPLOYMENT TRIBUNALS"');
    expect(html).not.toContain('aria-label="Wechseln Limited"');
    expect(html).toContain('data-entity-id="name-keep"');
    expect(html).toContain('aria-label="Lauren De Lacey"');
    expect(html).toContain('data-entity-id="qr-1"');
    expect(html).not.toContain("is-preserved");
  });

  it("renders KEEP overlays with a secondary style when preserved visibility is on", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer {...base} showPreserved />,
    );
    expect(html).toContain('data-entity-id="court-en"');
    expect(html).toContain('data-entity-id="co-1"');
    expect(html).toContain("is-preserved");
    expect(html).toContain('data-entity-id="name-keep"');
    expect(html).toContain('data-entity-id="qr-1"');
  });

  it("shows a KEEP finding with the normal overlay after a REDACT override", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        {...base}
        decisions={{ ...base.decisions, "court-en": "REDACT" }}
        entityStrategies={{ "court-en": "REDACT" }}
      />,
    );
    expect(html).toContain('data-entity-id="court-en"');
    expect(html).toContain("view-detections accent-person");
    expect(html).not.toContain("is-preserved");
    expect(html).not.toContain("is-kept");
  });
});

describe("PdfPageViewer PARTIAL_MASK preview", () => {
  const phone: Entity = {
    id: "phone-1",
    text: "0542 745 32 15",
    type: "PHONE_NUMBER",
    start: 40,
    end: 54,
    page: 0,
    detector: "TR_MOBILE_PHONE",
    method: "DETERMINISTIC",
    validated: true,
    recommended: true,
    recommended_strategy: "PARTIAL_MASK",
    attributes: { font_size: 11 },
  };

  it("covers the original glyphs with an opaque, source-sized partial mask", () => {
    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={1}
        entities={[phone]}
        decisions={{}}
        categoryDefaults={{ PHONE_NUMBER: "PARTIAL_MASK" }}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="preview"
        tool="select"
        pageWidth={560}
        language="tr"
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "phone-1",
                text: "0542 745 32 15",
                type: "PHONE_NUMBER",
                rectangles: [{ x0: 300, y0: 200, x1: 430, y1: 214 }],
              },
            ],
          },
        ]}
        onSelect={() => undefined}
        onPageInView={() => undefined}
        onDrawComplete={() => undefined}
      />,
    );
    expect(html).toContain("is-partial");
    expect(html).toContain("0542 *** ** 15");
    expect(html).toContain("background:#ffffff");
    expect(html).toContain("white-space:nowrap");
    expect(html).not.toContain("font-size:10px");
    expect(html).toMatch(/font-size:1[0-4]\.\d+px/);
  });

  it("drops leftover mapping crumbs instead of reprinting a tiny mask", () => {
    expect(
      dropTinySiblingRects([
        { x0: 10, y0: 200, x1: 28, y1: 214 },
        { x0: 320, y0: 200, x1: 430, y1: 214 },
      ]),
    ).toEqual([{ x0: 320, y0: 200, x1: 430, y1: 214 }]);

    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={1}
        entities={[phone]}
        decisions={{}}
        categoryDefaults={{ PHONE_NUMBER: "PARTIAL_MASK" }}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="preview"
        tool="select"
        pageWidth={560}
        language="tr"
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "phone-1",
                text: "0542 745 32 15",
                type: "PHONE_NUMBER",
                rectangles: [
                  { x0: 10, y0: 200, x1: 28, y1: 214 },
                  { x0: 320, y0: 200, x1: 430, y1: 214 },
                ],
              },
            ],
          },
        ]}
        onSelect={() => undefined}
        onPageInView={() => undefined}
        onDrawComplete={() => undefined}
      />,
    );
    expect(html.match(/data-entity-id="phone-1"/g)?.length).toBe(1);
    expect(html).toContain("is-partial");
    expect(html).toContain("0542 *** ** 15");
  });
});

describe("PdfPageViewer PLACEHOLDER preview", () => {
  it("covers the source span with an opaque source-sized placeholder", () => {
    const named: Entity = {
      ...person,
      recommended_strategy: "PLACEHOLDER",
      attributes: { font_size: 14 },
    };
    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={1}
        entities={[named]}
        decisions={{}}
        categoryDefaults={{ PERSON_NAME: "PLACEHOLDER" }}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="preview"
        tool="select"
        pageWidth={560}
        language="tr"
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "name-1",
                text: "Emine ELİTAŞ",
                type: "PERSON_NAME",
                rectangles: [{ x0: 80, y0: 200, x1: 180, y1: 214 }],
              },
            ],
          },
        ]}
        onSelect={() => undefined}
        onPageInView={() => undefined}
        onDrawComplete={() => undefined}
      />,
    );
    expect(html).toContain("is-placeholder");
    expect(html).toContain("[KİŞİ_1]");
    expect(html).toContain("background:#ffffff");
    expect(html).toContain("justify-content:center");
    expect(html).toContain("text-align:center");
    expect(html).toContain("align-items:center");
    expect(html).not.toContain("font-size:10px");
    expect(html).toMatch(/font-size:1[123]\.\d+px/);
  });

  it("numbers distinct people separately in the overlay", () => {
    const mehmet: Entity = {
      ...person,
      id: "name-mehmet",
      text: "Mehmet Yılmaz",
      start: 0,
      end: 13,
      recommended_strategy: "PLACEHOLDER",
    };
    const ayse: Entity = {
      ...person,
      id: "name-ayse",
      text: "Ayşe Demir",
      start: 20,
      end: 30,
      recommended_strategy: "PLACEHOLDER",
    };
    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={1}
        entities={[mehmet, ayse]}
        decisions={{}}
        categoryDefaults={{ PERSON_NAME: "PLACEHOLDER" }}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="preview"
        tool="select"
        pageWidth={560}
        language="tr"
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "name-mehmet",
                text: "Mehmet Yılmaz",
                type: "PERSON_NAME",
                rectangles: [{ x0: 80, y0: 200, x1: 180, y1: 214 }],
              },
              {
                entity_id: "name-ayse",
                text: "Ayşe Demir",
                type: "PERSON_NAME",
                rectangles: [{ x0: 200, y0: 200, x1: 280, y1: 214 }],
              },
            ],
          },
        ]}
        onSelect={() => undefined}
        onPageInView={() => undefined}
        onDrawComplete={() => undefined}
      />,
    );
    expect(html).toContain("[KİŞİ_1]");
    expect(html).toContain("[KİŞİ_2]");
  });

  it("uses English tags when the document language is English", () => {
    const named: Entity = {
      ...person,
      text: "John Smith",
      recommended_strategy: "PLACEHOLDER",
    };
    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={1}
        entities={[named]}
        decisions={{}}
        categoryDefaults={{ PERSON_NAME: "PLACEHOLDER" }}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="preview"
        tool="select"
        pageWidth={560}
        language="en"
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "name-1",
                text: "John Smith",
                type: "PERSON_NAME",
                rectangles: [{ x0: 80, y0: 200, x1: 180, y1: 214 }],
              },
            ],
          },
        ]}
        onSelect={() => undefined}
        onPageInView={() => undefined}
        onDrawComplete={() => undefined}
      />,
    );
    expect(html).toContain("[PERSON_1]");
    expect(html).not.toContain("[KİŞİ_1]");
  });

  it("covers each placeholder line separately instead of one column", () => {
    const covers = replacementCoverRects(
      [
        { x0: 100, y0: 200, x1: 160, y1: 214 },
        { x0: 100, y0: 230, x1: 155, y1: 244 },
      ],
      true,
    );
    expect(covers).toHaveLength(2);
    expect(covers[0].y1).toBeLessThan(covers[1].y0);
  });

  it("stops growing a placeholder cover before the next overlay", () => {
    const fitted = fitPlaceholderCoverRect(
      { x0: 80, y0: 200, x1: 96, y1: 214 },
      "[PERSON_8]",
      "Jo",
      11,
      595,
      [{ x0: 110, y0: 200, x1: 180, y1: 214 }],
    );
    expect(fitted.x0).toBe(80);
    expect(fitted.x1).toBeLessThanOrEqual(96);
  });

  it("does not expand a short name cover over following text", () => {
    const origin = { x0: 80, y0: 200, x1: 96, y1: 214 };
    const fitted = fitPlaceholderCoverRect(
      origin,
      "[PERSON_8]",
      "Jo",
      11,
      595,
    );
    expect(fitted.x0).toBe(origin.x0);
    expect(fitted.x1).toBeLessThanOrEqual(origin.x1);
    expect(fitted.y1 - fitted.y0).toBeLessThan(20);
  });

  it("clamps an exploded mapping instead of painting a column", () => {
    const fitted = fitPlaceholderCoverRect(
      { x0: 200, y0: 100, x1: 400, y1: 260 },
      "[PERSON_8]",
      "Jo",
      11,
      595,
    );
    expect(fitted.x1 - fitted.x0).toBeLessThan(80);
    expect(fitted.y1 - fitted.y0).toBeLessThan(25);
  });

  it("keeps the full numbered tag in the preview for a short name", () => {
    const named: Entity = {
      ...person,
      id: "name-jo",
      text: "Jo",
      recommended_strategy: "PLACEHOLDER",
      placeholder_token: "[PERSON_8]",
    };
    const html = renderToStaticMarkup(
      <PdfPageViewer
        jobId="job"
        pageCount={1}
        entities={[named]}
        decisions={{}}
        categoryDefaults={{ PERSON_NAME: "PLACEHOLDER" }}
        entityStrategies={{}}
        manual={[]}
        activeId={null}
        focusId={null}
        currentPage={1}
        viewMode="preview"
        tool="select"
        pageWidth={560}
        language="en"
        initialPages={[
          {
            page: 0,
            width: 595,
            height: 842,
            spans: [
              {
                entity_id: "name-jo",
                text: "Jo",
                type: "PERSON_NAME",
                rectangles: [{ x0: 80, y0: 200, x1: 96, y1: 214 }],
              },
            ],
          },
        ]}
        onSelect={() => undefined}
        onPageInView={() => undefined}
        onDrawComplete={() => undefined}
      />,
    );
    expect(html).toContain("[PERSON_8]");
    expect(html).toContain("is-cover-clip");
    expect(html).toContain("overflow:hidden");
  });
});
