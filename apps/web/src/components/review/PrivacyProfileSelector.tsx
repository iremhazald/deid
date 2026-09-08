import type { PrivacyProfile } from '../../state/types'

type Props = {
  label: string
  help: string
  value: PrivacyProfile
  options: Array<{ value: PrivacyProfile; label: string }>
  customHelp?: string
  onChange: (value: PrivacyProfile) => void
}

export function PrivacyProfileSelector({ label, help, value, options, customHelp, onChange }: Props) {
  const selected = options.find((option) => option.value === value)?.label ?? value
  return (
    <div className="profile-selector compact">
      <div className="profile-label-row">
        <label htmlFor="privacy-profile">{label}: {selected}</label>
        <span className="info-tip" tabIndex={0} title={help} aria-label={help}>
          i
        </span>
      </div>
      <select
        id="privacy-profile"
        value={value}
        onChange={(event) => onChange(event.target.value as PrivacyProfile)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      {value === 'CUSTOM' && customHelp && (
        <p className="panel-help">{customHelp}</p>
      )}
    </div>
  )
}
