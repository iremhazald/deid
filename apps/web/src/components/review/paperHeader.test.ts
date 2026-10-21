import { describe, expect, it } from "vitest";
import type { Entity } from "../../state/types";
import { applyPaperHeaderMasks, paperHeaderRanges } from "./paperHeader";

function court(start: number, end: number, text: string): Entity {
  return {
    id: "court",
    text,
    type: "COURT_NAME",
    start,
    end,
    page: 0,
    detector: "TR_COURT_GRAMMAR",
    method: "DETERMINISTIC",
    validated: true,
    recommended: true,
    recommended_strategy: "PLACEHOLDER",
    attributes: { mask_scope: "header_line" },
  };
}

const header =
  "T.C. SİLİFKE 2. AĞIR CEZA MAHKEMESİ\nDuruşma Tarihi: 10/11/2025 Talimat No: 2025/203 Talimat\nBelirli gün ";

describe("paperHeaderRanges", () => {
  it("covers the court line and the following docket line", () => {
    const entity = court(0, "T.C. SİLİFKE 2. AĞIR CEZA MAHKEMESİ".length, "T.C. SİLİFKE 2. AĞIR CEZA MAHKEMESİ");
    const ranges = paperHeaderRanges(header, [entity]);
    expect(header.slice(ranges[0][0], ranges[0][1])).toBe(
      "T.C. SİLİFKE 2. AĞIR CEZA MAHKEMESİ\nDuruşma Tarihi: 10/11/2025 Talimat No: 2025/203 Talimat",
    );
  });

  it("leaves the body line outside the mask", () => {
    const entity = court(0, 10, header.slice(0, 10));
    const [, end] = paperHeaderRanges(header, [entity])[0];
    expect(header.slice(end)).toBe("\nBelirli gün ");
  });
});

describe("applyPaperHeaderMasks", () => {
  it("replaces the header strip in preview and keeps the body", () => {
    const name = "T.C. SİLİFKE 2. AĞIR CEZA MAHKEMESİ";
    const entity = court(0, name.length, name);
    const parts = [
      { text: header.slice(0, name.length), entity },
      { text: header.slice(name.length) },
    ];
    const masked = applyPaperHeaderMasks(parts, header, [entity], "preview");
    expect(masked[0]?.paperHeader).toBe(true);
    expect(masked[0]?.text.startsWith("T.C. SİLİFKE 2.")).toBe(true);
    expect(masked[0]?.text).not.toContain("Belirli gün");
    expect(masked.map((part) => part.text).join("")).toBe(header);
    expect(applyPaperHeaderMasks(parts, header, [entity], "detections")[0]?.paperHeader).toBeUndefined();
  });
});
