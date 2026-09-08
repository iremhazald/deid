import type { DocumentLanguage, DocumentLanguageChoice } from '../../state/documentLanguage'
import { DOCUMENT_LANGUAGE_UI_OPTIONS } from '../../state/documentLanguage'

type Props = {
  value: DocumentLanguage
  t: (key: string, options?: Record<string, unknown>) => string
  onChange: (value: DocumentLanguageChoice) => void
}

export function DocumentLanguagePicker({ value, t, onChange }: Props) {
  const selected = DOCUMENT_LANGUAGE_UI_OPTIONS.includes(value as DocumentLanguageChoice)
    ? (value as DocumentLanguageChoice)
    : null

  const move = (from: DocumentLanguageChoice | null, delta: number) => {
    const options = DOCUMENT_LANGUAGE_UI_OPTIONS
    const current = from ? options.indexOf(from) : 0
    const next = options[(current + delta + options.length) % options.length]
    onChange(next)
  }

  return (
    <div className="document-language">
      <p className="document-language-label" id="document-language-label">
        {t('documentLanguage.label')}
      </p>
      <p className="document-language-help" id="document-language-help">
        {t('documentLanguage.help')}
      </p>
      <div
        className="document-language-options"
        role="radiogroup"
        aria-labelledby="document-language-label"
        aria-describedby="document-language-help"
        onKeyDown={(event) => {
          if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
            event.preventDefault()
            move(selected, 1)
          } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
            event.preventDefault()
            move(selected, -1)
          }
        }}
      >
        {DOCUMENT_LANGUAGE_UI_OPTIONS.map((option) => {
          const checked = selected === option
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={checked}
              tabIndex={checked || (selected === null && option === DOCUMENT_LANGUAGE_UI_OPTIONS[0]) ? 0 : -1}
              className={checked ? 'on' : ''}
              onClick={() => onChange(option)}
            >
              {t(`documentLanguage.${option}`)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
