import { useState } from 'react'

type Props = {
  title: string
  dialogTitle: string
  textLabel: string
  matchLabel: string
  matchAllLabel: string
  matchPageLabel: string
  matchHelp: string
  pageLabel: string
  addLabel: string
  cancelLabel: string
  text: string
  page: number
  maxPage: number
  matchAll: boolean
  items: Array<{ text: string; page: number }>
  onTextChange: (value: string) => void
  onPageChange: (value: number) => void
  onMatchAllChange: (value: boolean) => void
  onAdd: () => void
  onRemove: (index: number) => void
  removeLabel: string
}

export function ManualRedaction({
  title,
  dialogTitle,
  textLabel,
  matchLabel,
  matchAllLabel,
  matchPageLabel,
  matchHelp,
  pageLabel,
  addLabel,
  cancelLabel,
  text,
  page,
  maxPage,
  matchAll,
  items,
  onTextChange,
  onPageChange,
  onMatchAllChange,
  onAdd,
  onRemove,
  removeLabel,
}: Props) {
  const [open, setOpen] = useState(false)

  const add = () => {
    if (!text.trim()) return
    onAdd()
    setOpen(false)
  }

  return (
    <section className="manual-block">
      <button type="button" className="linkish" onClick={() => setOpen(true)}>
        {title}
      </button>
      {open && (
        <div className="manual-dialog" role="dialog" aria-label={dialogTitle}>
          <h3>{dialogTitle}</h3>
          <label className="manual-field">
            <span>{textLabel}</span>
            <input
              value={text}
              onChange={(event) => onTextChange(event.target.value)}
              aria-label={textLabel}
            />
          </label>
          <fieldset className="manual-matches">
            <legend>{matchLabel}</legend>
            <label>
              <input
                type="radio"
                name="manual-match"
                checked={matchAll}
                onChange={() => onMatchAllChange(true)}
              />
              {matchAllLabel}
            </label>
            <label>
              <input
                type="radio"
                name="manual-match"
                checked={!matchAll}
                onChange={() => onMatchAllChange(false)}
              />
              {matchPageLabel}
            </label>
            {!matchAll && maxPage > 1 && (
              <label className="manual-field">
                <span>{pageLabel}</span>
                <input
                  type="number"
                  min={1}
                  max={maxPage}
                  value={page}
                  aria-label={pageLabel}
                  onChange={(event) => onPageChange(Number(event.target.value))}
                />
              </label>
            )}
            <p className="panel-help">{matchHelp}</p>
          </fieldset>
          <div className="rewrite-actions">
            <button type="button" className="btn secondary" onClick={() => setOpen(false)}>
              {cancelLabel}
            </button>
            <button type="button" className="btn primary" onClick={add} disabled={!text.trim()}>
              {addLabel}
            </button>
          </div>
        </div>
      )}
      {items.length > 0 && (
        <ul className="manual-list">
          {items.map((item, index) => (
            <li key={`${item.text}-${index}`}>
              <span>{item.text} · {pageLabel} {item.page}</span>
              <button type="button" aria-label={removeLabel} onClick={() => onRemove(index)}>×</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
