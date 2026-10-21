import type { WorkspaceMode } from '../../state/workspaceMode'

const OPTIONS: WorkspaceMode[] = ['DOCUMENT', 'TEXT']

type Props = {
  value: WorkspaceMode | null
  t: (key: string, options?: Record<string, unknown>) => string
  onChange: (value: WorkspaceMode) => void
}

export function WorkspaceModeChooser({ value, t, onChange }: Props) {
  const move = (from: WorkspaceMode | null, delta: number) => {
    const current = from ? OPTIONS.indexOf(from) : 0
    const next = OPTIONS[(current + delta + OPTIONS.length) % OPTIONS.length]
    onChange(next)
  }

  return (
    <div className="workspace-choice">
      <p className="workspace-choice-label" id="workspace-choice-label">
        {t('workspaceChoice.question')}
      </p>
      <div
        className="workspace-choice-options"
        role="radiogroup"
        aria-labelledby="workspace-choice-label"
        onKeyDown={(event) => {
          if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
            event.preventDefault()
            move(value, 1)
          } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
            event.preventDefault()
            move(value, -1)
          }
        }}
      >
        {OPTIONS.map((option) => {
          const checked = value === option
          const label =
            option === 'DOCUMENT' ? t('workspaceChoice.pdf') : t('workspaceChoice.text')
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={checked}
              tabIndex={checked || (value === null && option === 'DOCUMENT') ? 0 : -1}
              className={checked ? 'on' : ''}
              onClick={() => onChange(option)}
            >
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
