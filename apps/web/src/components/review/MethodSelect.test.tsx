import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MethodSelect } from "./MethodSelect";

describe("MethodSelect", () => {
  it("renders an accessible combobox with title and example for each option", () => {
    const html = renderToStaticMarkup(
      <MethodSelect
        label="Bu tespitler nasıl gösterilsin?"
        value="PLACEHOLDER"
        options={[
          {
            value: "PLACEHOLDER",
            label: "Etiketle değiştir",
            example: "John Brown → [PERSON_1]",
          },
          {
            value: "REDACT",
            label: "Tamamen gizle",
            example: "John Brown → ██████████",
          },
          {
            value: "KEEP",
            label: "Belgede bırak",
            example: "John Brown → John Brown",
          },
        ]}
        onChange={() => undefined}
      />,
    );
    expect(html).toContain('role="combobox"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('role="listbox"');
    expect(html).toContain('role="option"');
    expect(html).toContain("Bu tespitler nasıl gösterilsin?");
    expect(html).toContain("Etiketle değiştir");
    expect(html).toContain("John Brown → [PERSON_1]");
    expect(html).toContain("Tamamen gizle");
    expect(html).toContain("Belgede bırak");
    expect(html).toContain("John Brown → [PERSON_1]");
    expect(html).not.toContain("method-select-preview");
  });
});
