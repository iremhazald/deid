import type { ReactNode } from "react";
import { categoryAccent } from "../../state/helpers";

type Props = {
  id: string;
  type: string;
  title: string;
  count: number;
  open: boolean;
  active?: boolean;
  manual?: boolean;
  methodLabel?: string;
  toolbar?: ReactNode;
  children: ReactNode;
  onToggle: () => void;
};

export function CategorySection({
  id,
  type,
  title,
  count,
  open,
  active = false,
  manual = false,
  methodLabel,
  toolbar,
  children,
  onToggle,
}: Props) {
  const accent = manual ? "accent-other" : categoryAccent(type);
  const panelId = `category-panel-${id}`;

  return (
    <li
      className={`category-item type-group${manual ? " family-block" : ""}${open ? " open" : ""}${active ? " has-active" : ""} ${accent}`}
    >
      <button
        type="button"
        className="category-toggle"
        aria-expanded={open}
        aria-controls={panelId}
        title={title}
        onClick={onToggle}
      >
        <span className="category-accent" aria-hidden="true" />
        <span className="category-glyph" aria-hidden="true">
          <CategoryGlyph kind={manual ? "manual" : accent} />
        </span>
        <span className="category-toggle-copy">
          <span className="category-toggle-title">{title}</span>
          {methodLabel ? (
            <span className="category-toggle-method">{methodLabel}</span>
          ) : null}
        </span>
        <span className="category-toggle-count">{count}</span>
        <span className="family-chevron" aria-hidden="true">
          <ChevronIcon />
        </span>
      </button>
      <div
        className="type-panel category-panel"
        id={panelId}
        hidden={!open}
        role="region"
        aria-label={title}
      >
        {toolbar}
        {children}
      </div>
    </li>
  );
}

function ChevronIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path
        d="M3 4.6 6 7.6l3-3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CategoryGlyph({ kind }: { kind: string }) {
  const common = {
    width: 14,
    height: 14,
    viewBox: "0 0 14 14",
    fill: "none" as const,
    "aria-hidden": true as const,
  };
  const stroke = {
    stroke: "currentColor",
    strokeWidth: 1.35,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  switch (kind) {
    case "manual":
      return (
        <svg {...common}>
          <path d="M8.4 2.4 11.6 5.6 5.2 12H2v-3.2L8.4 2.4Z" {...stroke} />
          <path d="M7.4 3.4 10.6 6.6" {...stroke} />
        </svg>
      );
    case "accent-person":
      return (
        <svg {...common}>
          <circle cx="7" cy="4.4" r="2.2" {...stroke} />
          <path d="M2.8 12c.4-2.4 1.9-3.6 4.2-3.6s3.8 1.2 4.2 3.6" {...stroke} />
        </svg>
      );
    case "accent-id":
      return (
        <svg {...common}>
          <rect x="1.6" y="3" width="10.8" height="8" rx="1.4" {...stroke} />
          <circle cx="5" cy="7" r="1.3" {...stroke} />
          <path d="M7.6 6.2h3.2M7.6 8.2h2.4" {...stroke} />
        </svg>
      );
    case "accent-address":
      return (
        <svg {...common}>
          <path d="M7 12.2s4.2-3.4 4.2-6.2A4.2 4.2 0 0 0 2.8 6c0 2.8 4.2 6.2 4.2 6.2Z" {...stroke} />
          <circle cx="7" cy="6" r="1.35" {...stroke} />
        </svg>
      );
    case "accent-contact":
      return (
        <svg {...common}>
          <rect x="2" y="3.2" width="10" height="7.6" rx="1.4" {...stroke} />
          <path d="M2.4 4.2 7 7.4l4.6-3.2" {...stroke} />
        </svg>
      );
    case "accent-finance":
      return (
        <svg {...common}>
          <rect x="1.8" y="3.4" width="10.4" height="7.2" rx="1.3" {...stroke} />
          <path d="M1.8 6h10.4" {...stroke} />
          <circle cx="7" cy="8.4" r="1.05" {...stroke} />
        </svg>
      );
    case "accent-sensitive":
      return (
        <svg {...common}>
          <path d="M7 1.8 11.6 3.6v3.4c0 2.8-2 4.6-4.6 5.4-2.6-.8-4.6-2.6-4.6-5.4V3.6L7 1.8Z" {...stroke} />
        </svg>
      );
    case "accent-legal":
      return (
        <svg {...common}>
          <path d="M3.2 2.6h7.6v9H4.4A1.2 1.2 0 0 1 3.2 10.4V2.6Z" {...stroke} />
          <path d="M5.2 5.4h3.6M5.2 7.4h3.6M5.2 9.4h2.2" {...stroke} />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <path d="M2.4 4.2h6.2l3 2.2v5.2H4.6L2.4 9.4V4.2Z" {...stroke} />
        </svg>
      );
  }
}
