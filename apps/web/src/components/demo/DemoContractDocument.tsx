import type { Ref } from 'react'
import { RedactableDemoText } from './RedactableDemoText'
import type { EnDemoEntityId } from './demoScript'

type Props = {
  pageRef: Ref<HTMLDivElement>
}

function Text({ id, children }: { id: EnDemoEntityId; children: string }) {
  return <RedactableDemoText id={id}>{children}</RedactableDemoText>
}

/**
 * Synthetic English Master Services Agreement.
 *
 * Drafted to resemble a short commercial services contract for an in-house
 * legal / legal-operations audience. Every name, company, address, email,
 * telephone number, IBAN, date, URL and signature block is fictional
 * demonstration data invented for this landing-page animation. This is not a
 * real contract and is not based on any actual agreement.
 */
export function DemoContractDocument({ pageRef }: Props) {
  return (
    <div className="demo-page demo-contract" data-demo-document="contract" lang="en" ref={pageRef}>
      <div className="demo-watermark">SAMPLE DOCUMENT · SYNTHETIC CONTENT</div>

      <div className="demo-contract-head" data-anchor="top">
        <div className="demo-contract-title">MASTER SERVICES AGREEMENT</div>
        <div className="demo-contract-effective">
          Effective Date:{' '}
          <Text id="effectiveDate">14 March 2026</Text>
        </div>
      </div>

      <p className="demo-contract-recital">
        This Master Services Agreement is entered into as of{' '}
        <Text id="effectiveDate">14 March 2026</Text> (the “Effective Date”).
      </p>

      <div className="demo-contract-between">BETWEEN</div>

      <div className="demo-contract-parties" data-anchor="parties">
        <div className="demo-contract-party">
          <div className="demo-contract-party-name">
            <Text id="companyNorthstar">Northstar Analytics Ltd.</Text>
          </div>
          <div>
            <Text id="northstarAddress">42 King Street, London EC2V 8BB, United Kingdom</Text>
          </div>
        </div>
        <div className="demo-contract-and">and</div>
        <div className="demo-contract-party">
          <div className="demo-contract-party-name">
            <Text id="companyBrightfield">Brightfield Systems Inc.</Text>
          </div>
          <div>
            <Text id="brightfieldAddress">200 Market Street, San Francisco, CA 94105, United States</Text>
          </div>
        </div>
      </div>

      <p className="demo-contract-recital">The parties agree as follows:</p>

      <div className="demo-contract-section" data-anchor="contacts">
        CONTACTS
      </div>
      <div className="demo-contract-contacts">
        <div className="demo-contract-block">
          <div className="demo-contract-block-label">
            For <Text id="companyNorthstar">Northstar Analytics Ltd.</Text>
          </div>
          <div>
            <Text id="emilyName">Emily Carter</Text>
          </div>
          <div>General Counsel</div>
          <div>
            <Text id="emilyEmail">emily.carter@example.com</Text>
          </div>
          <div>
            <Text id="emilyPhone">+44 20 7946 0123</Text>
          </div>
        </div>
        <div className="demo-contract-block">
          <div className="demo-contract-block-label">
            For <Text id="companyBrightfield">Brightfield Systems Inc.</Text>
          </div>
          <div>
            <Text id="danielName">Daniel Brooks</Text>
          </div>
          <div>VP, Operations</div>
          <div>
            <Text id="danielEmail">daniel.brooks@example.com</Text>
          </div>
          <div>
            <Text id="danielPhone">+1 415 555 0184</Text>
          </div>
        </div>
      </div>

      <p className="demo-contract-clause">
        <span className="demo-contract-clause-title">1. Services. </span>
        <Text id="servicesCompany">Northstar Analytics Ltd.</Text> shall provide analytics and
        reporting services to Brightfield as described in the applicable statement of work and at{' '}
        <Text id="servicesUrl">https://services.northstar-analytics.example/msa</Text>. Northstar
        shall perform the services with reasonable skill and care.
      </p>

      <p className="demo-contract-clause" data-anchor="payment">
        <span className="demo-contract-clause-title">2. Fees and Payment. </span>
        Brightfield shall pay the fees set out in the applicable statement of work. Payments shall
        be made to:
      </p>
      <div className="demo-contract-payment">
        <div>
          Account Name: <Text id="paymentCompany">Northstar Analytics Ltd.</Text>
        </div>
        <div>
          IBAN: <Text id="iban">GB29 NWBK 6016 1331 9268 19</Text>
        </div>
      </div>
      <p className="demo-contract-clause">Invoices are payable within thirty (30) days of receipt.</p>

      <p className="demo-contract-clause">
        <span className="demo-contract-clause-title">3. Confidentiality. </span>
        Each party shall keep confidential the other party’s non-public information received in
        connection with this Agreement and shall not disclose it except as required by law or with
        prior written consent.
      </p>

      <p className="demo-contract-clause">
        <span className="demo-contract-clause-title">4. Data Protection. </span>
        Each party shall process personal data in connection with this Agreement only as necessary
        to perform its obligations, and in accordance with applicable data protection laws.
        Brightfield is the controller of any customer personal data provided to Northstar.
      </p>

      <p className="demo-contract-clause">
        <span className="demo-contract-clause-title">5. Term and Termination. </span>
        This Agreement commences on the Effective Date and continues until terminated. Either party
        may terminate this Agreement on thirty (30) days’ written notice, or immediately upon a
        material breach that remains unremedied for fifteen (15) days after notice.
      </p>

      <p className="demo-contract-clause" data-anchor="notices">
        <span className="demo-contract-clause-title">6. Notices. </span>
        Notices under this Agreement shall be sent to:
      </p>
      <div className="demo-contract-contacts">
        <div className="demo-contract-block">
          <div className="demo-contract-block-label">Notices to Northstar:</div>
          <div>
            <Text id="noticeEmilyName">Emily Carter</Text>
          </div>
          <div>
            <Text id="noticeAddress">42 King Street, London EC2V 8BB, United Kingdom</Text>
          </div>
          <div>
            <Text id="noticeEmail">emily.carter@example.com</Text>
          </div>
        </div>
        <div className="demo-contract-block">
          <div className="demo-contract-block-label">Notices to Brightfield:</div>
          <div>
            <Text id="noticeDanielName">Daniel Brooks</Text>
          </div>
          <div>200 Market Street, San Francisco, CA 94105, United States</div>
          <div>daniel.brooks@example.com</div>
        </div>
      </div>

      <p className="demo-contract-clause">
        <span className="demo-contract-clause-title">7. General. </span>
        This Agreement constitutes the entire agreement between the parties concerning its subject
        matter and is governed by the laws of England and Wales.
      </p>

      <p className="demo-contract-witness" data-anchor="signatures">
        IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.
      </p>

      <div className="demo-contract-sign">
        <div className="demo-contract-sign-party">
          <div className="demo-contract-block-label">For Northstar Analytics Ltd.</div>
          <div className="demo-contract-sign-line" />
          <div>
            <Text id="signatureEmily">Emily Carter</Text>
          </div>
          <div>General Counsel</div>
        </div>
        <div className="demo-contract-sign-party">
          <div className="demo-contract-block-label">For Brightfield Systems Inc.</div>
          <div className="demo-contract-sign-line" />
          <div>
            <Text id="signatureDaniel">Daniel Brooks</Text>
          </div>
          <div>VP, Operations</div>
        </div>
      </div>

      <div className="demo-page-foot">
        <span>1 / 2</span>
        <span className="demo-page-foot-note">
          This document contains fictional demonstration data.
        </span>
      </div>
    </div>
  )
}
