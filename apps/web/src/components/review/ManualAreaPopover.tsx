import { useState } from "react";
import type { ManualRect } from "../../state/types";
import {
  DEFAULT_TEXT_FONT,
  DEFAULT_TEXT_SIZE,
  DOCUMENT_FONTS,
  DOCUMENT_FONT_SIZES,
  REDACT_FILLS,
  TEXT_AREA_FILL,
  TEXT_BACKGROUNDS,
  TRANSPARENT_FILL,
  redactFillLabelKey,
} from "./documentFonts";

export { REDACT_FILLS };
export const TEXT_INKS = ["#ffffff", "#111318", "#1e3a5f", "#5c1f1f"] as const;

type Mode = "redact" | "text";

type Props = {
  page: number;
  rect: ManualRect;
  left?: number;
  top?: number;
  maxHeight?: number;
  initialMode?: Mode;
  t: (key: string, options?: Record<string, unknown>) => string;
  onConfirm: (payload: {
    replacement?: string;
    category?: string;
    fill: string;
    textColor?: string;
    font?: string;
    fontSize?: number;
  }) => void;
  onCancel: () => void;
};

export function ManualAreaPopover({
  page,
  left,
  top,
  maxHeight,
  initialMode = "redact",
  t,
  onConfirm,
  onCancel,
}: Props) {
  const mode = initialMode;
  const [label, setLabel] = useState("");
  const [category, setCategory] = useState("OTHER_IDENTIFIER");
  const [fill, setFill] = useState<string>(
    mode === "redact" ? REDACT_FILLS[0] : TEXT_AREA_FILL,
  );
  const [textColor, setTextColor] = useState<string>(
    mode === "text" ? TEXT_INKS[1] : TEXT_INKS[0],
  );
  const [font, setFont] = useState(DEFAULT_TEXT_FONT);
  const [fontSize, setFontSize] = useState(DEFAULT_TEXT_SIZE);
  const title =
    mode === "text" ? t("workspace.addTextTitle") : t("workspace.manualTitle");
  const lead =
    mode === "text" ? t("workspace.addTextHelp") : t("workspace.redactHelp");

  return (
    <div
      className={`manual-area-pop${left != null && top != null ? " is-anchored" : ""}`}
      role="dialog"
      aria-label={title}
      style={
        left != null && top != null
          ? { left, top, maxHeight: maxHeight ?? "min(72vh, calc(100vh - 24px))" }
          : undefined
      }
    >
      <header className="manual-area-head">
        <strong>{title}</strong>
        <p>{lead}</p>
        <span className="inspector-meta">
          {t("page")} {page}
        </span>
      </header>

      {mode === "redact" && (
        <fieldset className="color-field">
          <legend>{t("workspace.fillColor")}</legend>
          <ColorRow
            colors={REDACT_FILLS}
            value={fill}
            onChange={setFill}
            labelFor={(color) => t(redactFillLabelKey(color))}
          />
        </fieldset>
      )}

      {mode === "text" && (
        <>
          <div className="manual-type-row">
            <label className="manual-text-label">
              <span>{t("workspace.fontFamily")}</span>
              <select
                value={font}
                onChange={(event) => setFont(event.target.value)}
              >
                {DOCUMENT_FONTS.map((item) => (
                  <option
                    key={item.id}
                    value={item.id}
                    style={{ fontFamily: item.css }}
                  >
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="manual-text-label">
              <span>{t("workspace.fontSize")}</span>
              <select
                value={fontSize}
                onChange={(event) => setFontSize(Number(event.target.value))}
              >
                {DOCUMENT_FONT_SIZES.map((size) => (
                  <option key={size} value={size}>
                    {t("workspace.fontSizeUnit", { size })}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <fieldset className="color-field">
            <legend>{t("workspace.backgroundColor")}</legend>
            <ColorRow
              colors={TEXT_BACKGROUNDS}
              value={fill}
              onChange={setFill}
              clearLabel={t("workspace.transparentFill")}
            />
          </fieldset>
          <fieldset className="color-field">
            <legend>{t("workspace.textColor")}</legend>
            <ColorRow
              colors={TEXT_INKS}
              value={textColor}
              onChange={setTextColor}
            />
          </fieldset>
          <label className="manual-text-label">
            <span>{t("workspace.addedText")}</span>
            <input
              className="custom-text-input"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder={t("workspace.addedTextHint")}
              style={{
                fontFamily: DOCUMENT_FONTS.find((item) => item.id === font)
                  ?.css,
              }}
            />
          </label>
        </>
      )}

      <label className="manual-category">
        <span>{t("workspace.areaKind")}</span>
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          {[
            "PERSON_NAME",
            "NATIONAL_ID",
            "PHONE_NUMBER",
            "ADDRESS",
            "FILE_NUMBER",
            "QR_CODE",
            "OTHER_IDENTIFIER",
          ].map((type) => (
            <option key={type} value={type}>
              {t(`categories.${type}`, { defaultValue: type })}
            </option>
          ))}
        </select>
      </label>

      <div className="selection-popup-actions">
        <button
          type="button"
          className="btn primary"
          onClick={() =>
            onConfirm({
              replacement:
                mode === "text"
                  ? label.trim() || t("workspace.hiddenMark")
                  : undefined,
              category,
              fill,
              textColor: mode === "text" ? textColor : undefined,
              font: mode === "text" ? font : undefined,
              fontSize: mode === "text" ? fontSize : undefined,
            })
          }
        >
          {t("workspace.applyArea")}
        </button>
        <button type="button" className="btn ghost" onClick={onCancel}>
          {t("cancel")}
        </button>
      </div>
    </div>
  );
}

export function ColorRow({
  colors,
  value,
  onChange,
  clearLabel,
  labelFor,
}: {
  colors: readonly string[];
  value: string;
  onChange: (color: string) => void;
  clearLabel?: string;
  labelFor?: (color: string) => string;
}) {
  return (
    <div className="color-row" role="listbox">
      {colors.map((color) => {
        const clear = color === TRANSPARENT_FILL;
        return (
          <button
            key={color}
            type="button"
            role="option"
            aria-selected={value === color}
            aria-label={clear ? clearLabel : (labelFor?.(color) ?? color)}
            className={`color-swatch${clear ? " is-clear" : ""}${value === color ? " is-on" : ""}`}
            style={clear ? undefined : { background: color }}
            onClick={() => onChange(color)}
            title={clear ? clearLabel : (labelFor?.(color) ?? color)}
          >
            {clear ? <span className="color-swatch-ban" aria-hidden /> : null}
          </button>
        );
      })}
    </div>
  );
}
