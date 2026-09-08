import type { PurposePreset } from '../../state/types'
import { PURPOSE_PRESETS } from '../../state/types'

type Props = {
  value: PurposePreset
  t: (key: string, options?: Record<string, unknown>) => string
  onChange: (value: PurposePreset) => void
}

export function PurposePresetSelector({ value, t, onChange }: Props) {
  const options = PURPOSE_PRESETS
  return (
    <div className="profile-selector compact purpose-preset">
      <div className="profile-label-row">
        <label htmlFor="purpose-preset">{t('preset.label')}</label>
        <span className="info-tip" tabIndex={0} title={t('preset.help')} aria-label={t('preset.help')}>
          i
        </span>
      </div>
      <select
        id="purpose-preset"
        value={value}
        onChange={(event) => onChange(event.target.value as PurposePreset)}
      >
        {options.map((item) => (
          <option key={item} value={item}>
            {t(`preset.${item}`)}
          </option>
        ))}
      </select>
      <p className="panel-help">{t(`preset.${value}Help`)}</p>
    </div>
  )
}
