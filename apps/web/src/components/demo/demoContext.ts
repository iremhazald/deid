import { createContext } from 'react'
import type { DemoCategory, DemoLocale, DemoMethod } from './demoScript'

export type DemoContextValue = {
  elapsed: number
  locale: DemoLocale
  categoryLabels: Partial<Record<DemoCategory, string>>
  methodLabels: Record<DemoMethod, string>
}

export const DemoContext = createContext<DemoContextValue>({
  elapsed: 0,
  locale: 'tr',
  categoryLabels: {},
  methodLabels: {
    redact: '',
    placeholder: '',
    initials: '',
    partial: '',
  },
})
