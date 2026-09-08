import { createInstance } from 'i18next'
import { initReactI18next, I18nextProvider } from 'react-i18next'
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import en from '../../locales/en.json'
import tr from '../../locales/tr.json'
import { DemoContext } from './demoContext'
import { DemoContractDocument } from './DemoContractDocument'
import { DemoCourtDocument } from './DemoCourtDocument'
import { RedactionDemo } from './RedactionDemo'
import { DEMO_STATIC_ELAPSED } from './demoScript'

const enLabels = {
  elapsed: DEMO_STATIC_ELAPSED,
  locale: 'en' as const,
  categoryLabels: {
    person: 'Person',
    identifier: 'Identifier',
    address: 'Address',
    contact: 'Contact',
    financial: 'Financial',
    company: 'Company',
  },
  methodLabels: {
    redact: 'Hide completely',
    placeholder: 'Replace with label',
    initials: 'Show initials',
    partial: 'Mask partially',
  },
}

function renderDemo(language: 'tr' | 'en') {
  const instance = createInstance()
  void instance.use(initReactI18next).init({
    lng: language,
    fallbackLng: 'tr',
    resources: {
      tr: { translation: tr },
      en: { translation: en },
    },
    interpolation: { escapeValue: false },
  })
  return {
    instance,
    html: renderToStaticMarkup(
      <I18nextProvider i18n={instance}>
        <RedactionDemo />
      </I18nextProvider>,
    ),
  }
}

function renderContract(elapsed = 0) {
  return renderToStaticMarkup(
    <DemoContext.Provider value={{ ...enLabels, elapsed }}>
      <DemoContractDocument pageRef={null} />
    </DemoContext.Provider>,
  )
}

function renderCourt() {
  return renderToStaticMarkup(
    <DemoContext.Provider
      value={{
        elapsed: 0,
        locale: 'tr',
        categoryLabels: {},
        methodLabels: enLabels.methodLabels,
      }}
    >
      <DemoCourtDocument pageRef={null} />
    </DemoContext.Provider>,
  )
}

describe('landing demo locale documents', () => {
  it('renders the Turkish court decision on the TR route', () => {
    const { html } = renderDemo('tr')
    expect(html).toContain('data-demo-document="court"')
    expect(html).toContain('GEREKÇELİ KARAR')
    expect(html).not.toContain('MASTER SERVICES AGREEMENT')
    expect(html).not.toContain('data-demo-document="contract"')
    expect(html).toContain('Kişi')
    expect(html).toContain('Mahkeme')
  })

  it('renders the English commercial agreement on the EN route', () => {
    const { html } = renderDemo('en')
    expect(html).toContain('data-demo-document="contract"')
    expect(html).toContain('MASTER SERVICES AGREEMENT')
    expect(html).not.toContain('GEREKÇELİ KARAR')
    expect(html).not.toContain('data-demo-document="court"')
    expect(html).not.toContain('T.C.')
    expect(html).not.toContain('DOSYA NO')
    expect(html).not.toContain('DAVACI')
    expect(html).not.toContain('SANIK')
    expect(html).not.toContain('HÜKÜM')
    expect(html).toContain('People')
    expect(html).toContain('Companies')
    expect(html).toContain('Financial')
    expect(html).toContain('Contact')
    expect(html).not.toContain('Case no')
    expect(html).not.toContain('Court')
  })

  it('switches documents cleanly from TR to EN and back', () => {
    const { instance } = renderDemo('tr')
    const trHtml = renderToStaticMarkup(
      <I18nextProvider i18n={instance}>
        <RedactionDemo />
      </I18nextProvider>,
    )
    expect(trHtml).toContain('GEREKÇELİ KARAR')

    void instance.changeLanguage('en')
    const enHtml = renderToStaticMarkup(
      <I18nextProvider i18n={instance}>
        <RedactionDemo />
      </I18nextProvider>,
    )
    expect(enHtml).toContain('MASTER SERVICES AGREEMENT')
    expect(enHtml).not.toContain('GEREKÇELİ KARAR')
    expect(enHtml).toContain('People')
    expect(enHtml).toContain('Companies')

    void instance.changeLanguage('tr')
    const backHtml = renderToStaticMarkup(
      <I18nextProvider i18n={instance}>
        <RedactionDemo />
      </I18nextProvider>,
    )
    expect(backHtml).toContain('GEREKÇELİ KARAR')
    expect(backHtml).not.toContain('MASTER SERVICES AGREEMENT')
    expect(backHtml).not.toContain('[PERSON_1]')
  })
})

describe('English contract document', () => {
  it('contains synthetic MSA content and no Turkish court labels', () => {
    const html = renderContract(0)
    expect(html).toContain('MASTER SERVICES AGREEMENT')
    expect(html).toContain('Emily Carter')
    expect(html).toContain('Daniel Brooks')
    expect(html).toContain('GB29 NWBK 6016 1331 9268 19')
    expect(html).toContain('emily.carter@example.com')
    expect(html).toContain('SAMPLE DOCUMENT · SYNTHETIC CONTENT')
    expect(html).toContain('This document contains fictional demonstration data.')
    expect(html).not.toContain('GEREKÇELİ KARAR')
    expect(html).not.toContain('[KİŞİ_1]')
  })

  it('applies the four English transformations in the completed state', () => {
    const html = renderContract(DEMO_STATIC_ELAPSED)
    expect(html).toContain('[PERSON_1]')
    expect(html).not.toContain('[KİŞİ_1]')
    expect(html).not.toContain('Emily Carter')
    expect(html).toContain('D.B.')
    expect(html).not.toContain('Daniel Brooks')
    expect(html).toContain('e***@example.com')
    expect(html).not.toContain('emily.carter@example.com')
    expect(html).toContain('████████████████████████')
    expect(html).not.toContain('GB29 NWBK 6016 1331 9268 19')
    expect(html).not.toContain('Role')
    expect(html).not.toContain('Keep in document')
  })

  it('keeps the Turkish court document intact', () => {
    const html = renderCourt()
    expect(html).toContain('GEREKÇELİ KARAR')
    expect(html).toContain('T.C.')
    expect(html).toContain('HÜKÜM')
    expect(html).not.toContain('MASTER SERVICES AGREEMENT')
  })
})
