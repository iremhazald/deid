import { useEffect, useId, useRef, useState } from "react";

const MENU_MAX_PX = 200;

type Props<T extends string> = {
  label: string;
  value: T;
  options: Array<{ value: T; label: string }>;
  disabled?: boolean;
  className?: string;
  onChange: (value: T) => void;
};

export function ChoiceSelect<T extends string>({
  label,
  value,
  options,
  disabled,
  className,
  onChange,
}: Props<T>) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{
    top: number;
    left: number;
    width: number;
  } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const menuId = useId();
  const current = options.find((item) => item.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onReposition = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.max(rect.width, 168);
      const left = Math.min(rect.left, window.innerWidth - width - 12);
      const menuHeight = Math.min(options.length * 34 + 12, MENU_MAX_PX);
      const below = rect.bottom + 6;
      const top =
        below + menuHeight > window.innerHeight - 12
          ? Math.max(12, rect.top - menuHeight - 6)
          : below;
      setPos({ top, left: Math.max(12, left), width });
    };
    onReposition();
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [open, options.length]);

  useEffect(() => {
    if (!open) return;
    const selected = menuRef.current?.querySelector<HTMLElement>(
      '[aria-selected="true"]',
    );
    selected?.scrollIntoView({ block: "nearest" });
  }, [open, value]);

  return (
    <div
      className={`choice-select custom-search-method${className ? ` ${className}` : ""}`}
      ref={rootRef}
      onClick={(event) => event.stopPropagation()}
    >
      <span id={`${menuId}-label`}>{label}</span>
      <button
        ref={buttonRef}
        type="button"
        className={`choice-select-trigger${open ? " is-open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-labelledby={`${menuId}-label`}
        aria-controls={menuId}
        disabled={disabled}
        onClick={() => setOpen((currentOpen) => !currentOpen)}
      >
        {current?.label ?? ""}
      </button>
      {open && pos && (
        <ul
          ref={menuRef}
          id={menuId}
          className="choice-select-menu"
          role="listbox"
          style={{ top: pos.top, left: pos.left, width: pos.width }}
        >
          {options.map((item) => (
            <li key={item.value} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={item.value === value}
                className={item.value === value ? "on" : ""}
                onClick={() => {
                  onChange(item.value);
                  setOpen(false);
                }}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
