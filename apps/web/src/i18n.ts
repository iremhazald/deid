import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import tr from './locales/tr.json'

const initialLanguage = window.location.pathname === '/en' || window.location.pathname.startsWith('/en/')
  ? 'en'
  : 'tr'

void i18n.use(initReactI18next).init({
  resources: {
    tr: { translation: tr },
    en: { translation: en },
  },
  lng: initialLanguage,
  fallbackLng: 'tr',
  interpolation: { escapeValue: false },
})

document.documentElement.lang = initialLanguage

export default i18n
