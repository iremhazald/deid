export type ReviewPane = "detections" | "kept" | "custom";

type Tab = {
  id: ReviewPane;
  label: string;
  count?: number;
};

type Props = {
  pane: ReviewPane;
  tabs: Tab[];
  ariaLabel: string;
  onSelect: (pane: ReviewPane) => void;
};

export function ReviewPaneTabs({ pane, tabs, ariaLabel, onSelect }: Props) {
  return (
    <div className="review-panes" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab) => {
        const selected = pane === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`review-pane-${tab.id}`}
            aria-selected={selected}
            className={`review-pane${selected ? " on" : ""}`}
            onClick={() => onSelect(tab.id)}
          >
            <strong className="review-pane-label">{tab.label}</strong>
            {tab.count != null && (
              <span className="review-pane-count">{tab.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
