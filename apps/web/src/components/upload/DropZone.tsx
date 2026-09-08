import { useState } from "react";
import { ACCEPTED_FILES, isAcceptedUpload } from "../../state/types";

type Props = {
  title: string;
  browseLabel: string;
  limitsLabel: string;
  selectedName?: string;
  disabled?: boolean;
  onUpload: (file: File) => void;
};

export function DropZone({
  title,
  browseLabel,
  limitsLabel,
  selectedName,
  disabled,
  onUpload,
}: Props) {
  const [dragging, setDragging] = useState(false);

  return (
    <label
      className={`dropzone${dragging ? " over" : ""}${disabled ? " disabled" : ""}${selectedName ? " has-file" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        const file = event.dataTransfer.files?.[0];
        if (file && !disabled && isAcceptedUpload(file)) onUpload(file);
      }}
    >
      <span className="dropzone-icon" aria-hidden="true">
        ↑
      </span>
      <strong>{selectedName ?? title}</strong>
      <span className="btn secondary dropzone-browse">{browseLabel}</span>
      <span className="dropzone-meta">{limitsLabel}</span>
      <input
        type="file"
        accept={ACCEPTED_FILES}
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file && isAcceptedUpload(file)) onUpload(file);
          event.target.value = "";
        }}
      />
    </label>
  );
}
