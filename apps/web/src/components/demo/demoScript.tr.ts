/**
 * Turkish landing-demo entities and scroll anchors.
 *
 * Tied to the synthetic reasoned decision in DemoCourtDocument. Do not reuse
 * these IDs on the English contract demo.
 */

import type { DemoEntity } from './demoTypes'

export const TR_DEMO_DETECTIONS = {
  // Court identity
  courtCity: { at: 1400, category: 'court', label: true },
  courtName: { at: 1620, category: 'court' },

  // Case references
  caseFile: { at: 1880, category: 'case', label: true },
  caseDecision: { at: 2060, category: 'case' },
  caseProsecution: { at: 2240, category: 'case' },

  // Judicial personnel
  president: { at: 2500, category: 'person', label: true },
  memberOne: { at: 2680, category: 'person' },
  memberTwo: { at: 2860, category: 'person' },
  prosecutor: { at: 3040, category: 'person' },
  clerk: { at: 3220, category: 'person' },

  // Joining party
  partyName: { at: 4460, category: 'person' },
  partyParents: { at: 4640, category: 'person' },
  partyBirthDate: { at: 4820, category: 'identifier' },
  partyBirthPlace: { at: 4980, category: 'address' },
  partyAddress: { at: 5160, category: 'address', label: true },
  partyId: {
    at: 5400,
    category: 'identifier',
    label: true,
    method: 'redact',
    replacement: '███████████',
    transformAt: 2200,
  },
  partyPhone: {
    at: 5510,
    category: 'identifier',
    method: 'partial',
    replacement: '0532 *** ** 67',
    transformAt: 6000,
  },
  partyCounsel: { at: 5620, category: 'person' },
  accusedCounsel: { at: 5800, category: 'person' },

  // Defendant
  accusedName: { at: 6040, category: 'person' },
  accusedParents: { at: 6220, category: 'person' },
  accusedBirthDate: { at: 6400, category: 'identifier' },
  accusedAddress: { at: 6580, category: 'address' },
  accusedId: { at: 6780, category: 'identifier' },

  // İDDİA
  bodyCity: { at: 7960, category: 'court' },
  bodyDate: { at: 8060, category: 'identifier' },
  bodyCaseNo: { at: 8160, category: 'case' },
  bodyCaseNoTwo: { at: 8250, category: 'case' },
  bodyCaseNoThree: { at: 8340, category: 'case' },
  bodyAccusedOne: { at: 8460, category: 'person', label: true },
  bodyPartyOne: { at: 8570, category: 'person' },

  // SAVUNMA
  bodyAccusedTwo: { at: 8700, category: 'person' },
  bodyPartyTwo: { at: 8800, category: 'person' },
  bodyAddress: { at: 8900, category: 'address' },
  bodyCounsel: { at: 9000, category: 'person' },

  // KATILAN BEYANI
  bodyPartyThree: { at: 9110, category: 'person' },
  bodyAccusedThree: { at: 9210, category: 'person' },
  bodyAddressTwo: { at: 9310, category: 'address' },

  // TANIK BEYANI
  bodyWitnessOne: {
    at: 9420,
    category: 'person',
    label: true,
    method: 'placeholder',
    replacement: '[TANIK_1]',
    transformAt: 3400,
  },
  bodyAccusedFour: { at: 9520, category: 'person' },
  bodyPartyFour: { at: 9610, category: 'person' },

  // MÜTALAA
  bodyAccusedFive: { at: 9710, category: 'person' },

  // GEREKÇE
  bodyAccusedSix: { at: 9820, category: 'person' },
  bodyPartyFive: { at: 9900, category: 'person' },
  bodyWitnessTwo: { at: 9980, category: 'person' },
  bodyCaseNoFour: { at: 10060, category: 'case' },

  // HÜKÜM
  bodyAccusedSeven: { at: 10160, category: 'person' },
  bodyPartySix: { at: 10250, category: 'person' },
  bodyCounselTwo: {
    at: 10340,
    category: 'person',
    method: 'initials',
    replacement: 'Av. Ö.A.',
    transformAt: 4700,
  },
} satisfies Record<string, DemoEntity>

export function trDemoScrollAnchor(elapsed: number): string {
  if (elapsed < 1850) return 'top'
  if (elapsed < 3000) return 'parties'
  if (elapsed < 4300) return 'witness'
  if (elapsed < 5600) return 'ruling'
  return 'parties'
}
