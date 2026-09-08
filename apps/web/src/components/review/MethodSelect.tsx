import { useEffect, useId, useRef, useState } from "react";
import type { TransformationStrategy } from "../../state/types";

export type MethodOption = {
  value: TransformationStrategy;
  label: string;
  example: string;
};

type Props = {
  label: string;
  value: TransformationStrategy;
  options: MethodOption[];
  onChange: (value: TransformationStrategy) => void;
};

export function MethodSelect({ label, value, options, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const selectedIndex = Math.max(
    0,
    options.findIndex((item) => item.value === value),
  );
  const [activeIndex, setActiveIndex] = useState(selectedIndex);
  const [pos, setPos] = useState<{
    top?: number;
    bottom?: number;
    left: number;
    width: number;
  } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const labelId = useId();
  const listId = useId();
  const current = options[selectedIndex] ?? options[0];

  const close = () => setOpen(false);

  const selectAt = (index: number) => {
    const next = options[index];
    if (!next) return;
    onChange(next.value);
    close();
    buttonRef.current?.focus();
  };

  const move = (delta: number) => {
    setActiveIndex((currentIndex) => {
      if (options.length === 0) return 0;
      return (currentIndex + delta + options.length) % options.length;
    });
  };

  useEffect(() => {
    if (!open) {
      setActiveIndex(selectedIndex);
      setPos(null);
      return;
    }
    const place = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(Math.max(rect.width, 220), 320);
      const left = Math.min(
        Math.max(12, rect.left),
        window.innerWidth - width - 12,
      );
      const menuHeight = Math.min(options.length * 52 + 16, 280);
      const spaceBelow = window.innerHeight - rect.bottom;
      if (spaceBelow < menuHeight + 12) {
        setPos({
          bottom: window.innerHeight - rect.top + 6,
          left,
          width,
        });
      } else {
        setPos({ top: rect.bottom + 6, left, width });
      }
    };
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        buttonRef.current?.focus();
      }
    };
    place();
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, options.length, selectedIndex]);

  return (
    <div className="method-select" ref={rootRef}>
      <span className="method-select-label" id={labelId}>
        {label}
      </span>
      <button
        ref={buttonRef}
        type="button"
        className={`method-select-trigger${open ? " is-open" : ""}`}
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-labelledby={labelId}
        aria-activedescendant={
          open ? `${listId}-opt-${activeIndex}` : undefined
        }
        onClick={() => setOpen((currentOpen) => !currentOpen)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            if (!open) setOpen(true);
            else move(1);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            if (!open) {
              setOpen(true);
              setActiveIndex(options.length - 1);
            } else {
              move(-1);
            }
          } else if (event.key === "Home" && open) {
            event.preventDefault();
            setActiveIndex(0);
          } else if (event.key === "End" && open) {
            event.preventDefault();
            setActiveIndex(options.length - 1);
          } else if ((event.key === "Enter" || event.key === " ") && open) {
            event.preventDefault();
            selectAt(activeIndex);
          }
        }}
      >
        {current?.label ?? ""}
      </button>
      <ul
        id={listId}
        className="method-select-menu"
        role="listbox"
        aria-labelledby={labelId}
        hidden={!open}
        style={
          open && pos
            ? { top: pos.top, bottom: pos.bottom, left: pos.left, width: pos.width }
            : undefined
        }
      >
        {options.map((item, index) => (
          <li key={item.value} role="presentation">
            <button
              type="button"
              id={`${listId}-opt-${index}`}
              role="option"
              aria-selected={item.value === value}
              className={`${item.value === value ? "on" : ""}${index === activeIndex ? " is-active" : ""}`}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => selectAt(index)}
            >
              <strong>{item.label}</strong>
              {item.example ? <span>{item.example}</span> : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
