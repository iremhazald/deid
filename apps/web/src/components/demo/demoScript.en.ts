/**
 * English landing-demo entities and scroll anchors.
 *
 * Tied to the synthetic Master Services Agreement in DemoContractDocument.
 * Repeated names share the same replacement by configuration only — this is
 * not the product merge engine.
 */

import type { DemoEntity } from './demoTypes'

export const EN_DEMO_DETECTIONS = {
  // Title / parties
  effectiveDate: { at: 1200, category: 'identifier', label: true },
  companyNorthstar: { at: 1600, category: 'company', label: true },
  northstarAddress: { at: 2000, category: 'address', label: true },
  companyBrightfield: { at: 2400, category: 'company' },
  brightfieldAddress: { at: 2800, category: 'address' },

  // Contacts
  emilyName: {
    at: 3400,
    category: 'person',
    label: true,
    method: 'placeholder',
    replacement: '[PERSON_1]',
    transformAt: 3400,
  },
  emilyEmail: {
    at: 3700,
    category: 'contact',
    method: 'partial',
    replacement: 'e***@example.com',
    transformAt: 6000,
  },
  emilyPhone: { at: 4000, category: 'contact' },
  danielName: {
    at: 4300,
    category: 'person',
    method: 'initials',
    replacement: 'D.B.',
    transformAt: 4700,
  },
  danielEmail: { at: 4600, category: 'contact' },
  danielPhone: { at: 4900, category: 'contact' },

  // Services / fees
  servicesUrl: { at: 5400, category: 'identifier' },
  servicesCompany: { at: 5700, category: 'company' },
  paymentCompany: { at: 6200, category: 'company' },
  iban: {
    at: 6500,
    category: 'financial',
    label: true,
    method: 'redact',
    replacement: '████████████████████████',
    transformAt: 2200,
  },

  // Notices
  noticeEmilyName: {
    at: 7600,
    category: 'person',
    method: 'placeholder',
    replacement: '[PERSON_1]',
    transformAt: 3400,
  },
  noticeAddress: { at: 8000, category: 'address' },
  noticeEmail: {
    at: 8400,
    category: 'contact',
    method: 'partial',
    replacement: 'e***@example.com',
    transformAt: 6000,
  },
  noticeDanielName: {
    at: 8800,
    category: 'person',
    method: 'initials',
    replacement: 'D.B.',
    transformAt: 4700,
  },

  // Signatures
  signatureEmily: {
    at: 9400,
    category: 'person',
    method: 'placeholder',
    replacement: '[PERSON_1]',
    transformAt: 3400,
  },
  signatureDaniel: {
    at: 9800,
    category: 'person',
    method: 'initials',
    replacement: 'D.B.',
    transformAt: 4700,
  },
} satisfies Record<string, DemoEntity>

export function enDemoScrollAnchor(elapsed: number): string {
  if (elapsed < 1850) return 'top'
  if (elapsed < 3000) return 'payment'
  if (elapsed < 4300) return 'contacts'
  if (elapsed < 5600) return 'signatures'
  return 'notices'
}
