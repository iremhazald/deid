import { describe, expect, it } from "vitest";
import type { Entity } from "./types";
import { fragmentHost } from "./fragmentHost";

function entity(partial: Partial<Entity> & Pick<Entity, "id" | "text" | "start" | "end">): Entity {
  return {
    type: "LOCATION",
    page: 0,
    detector: "TEST",
    method: "DETERMINISTIC",
    validated: true,
    recommended: true,
    ...partial,
  };
}

describe("fragmentHost", () => {
  it("picks the tightest finding that contains the span", () => {
    const fragment = entity({ id: "sili", text: "Sili", start: 4, end: 8 });
    const court = entity({
      id: "court",
      text: "T.C. Silifke Ağır Ceza",
      type: "COURT_NAME",
      start: 0,
      end: 22,
    });
    const page = entity({ id: "page", text: "whole page line", start: 0, end: 40 });
    expect(fragmentHost(fragment, [fragment, page, court])?.id).toBe("court");
  });

  it("ignores a longer finding that does not overlap", () => {
    const fragment = entity({ id: "city", text: "Mersin", start: 40, end: 46 });
    const other = entity({ id: "addr", text: "Mersin Merkez", start: 0, end: 13 });
    expect(fragmentHost(fragment, [fragment, other])).toBeNull();
  });
});