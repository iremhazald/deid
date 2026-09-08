import { useId, useState } from "react";

type Props = {
  title: string;
  body: string;
  toggleLabel: string;
};

export function PrivacyNotice({ title, body, toggleLabel }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <div className="privacy-notice">
      <button
        type="button"
        className="privacy-toggle"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <span>{toggleLabel}</span>
      </button>
      {open && (
        <div id={panelId} className="privacy-panel">
          {title ? <strong>{title}</strong> : null}
          <p>{body}</p>
        </div>
      )}
    </div>
  );
}
