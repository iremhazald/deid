"""Bank-transfer context: IBAN / person / amount / bank name."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate, relation
from app.detectors.legal.names import BARE_NAME_TOKEN, clipped_name_span
from app.detectors.legal.organisation import iter_bank_spans
from app.detectors.registry import IBAN, PageText, _fit_iban
from app.domain.models import EntityCandidate, EntityType

_CONTEXT = re.compile(
    r"(?:gönderildi|gonderildi|gönderdiğ|gonderdig|"
    r"transferi|EFT\s+edildi|havale\s+edildi|"
    r"para\s+yatırıldı|para\s+yatirildi|banka\s+hesabına|banka\s+hesabina|"
    r"IBAN\s+numara(?:sı|si)na|adına\s+kayıtlı|adina\s+kayitli)",
    re.IGNORECASE,
)
_NAME_GAP = r"[\s\u00a0\u00ad\u2000-\u200d\u202f]{0,40}"
_NAME_CHUNK = rf"{BARE_NAME_TOKEN}(?:{_NAME_GAP}{BARE_NAME_TOKEN}){{1,3}}"
_PERSON_NEAR = re.compile(
    rf"(?P<name>{_NAME_CHUNK})\s+(?i:adına|adina|hesabına|hesabina)"
)


def parse_transactions(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    if not _CONTEXT.search(page.text):
        return found
    seen: set[tuple[int, int, str]] = set()

    def add(candidate: EntityCandidate) -> None:
        key = (candidate.start, candidate.end, candidate.type.value)
        if key in seen:
            return
        seen.add(key)
        found.append(candidate)

    for match in IBAN.finditer(page.text):
        fitted = _fit_iban(match)
        if not fitted:
            continue
        value, start, end = fitted
        window_start = max(0, start - 80)
        window_end = min(len(page.text), end + 80)
        if not _CONTEXT.search(page.text[window_start:window_end]):
            continue
        iban = make_candidate(
            page,
            text=value,
            local_start=start,
            local_end=end,
            entity_type=EntityType.IBAN,
            detector="TR_BANK_TX",
            reason="IBAN in a transfer context.",
            attributes={"relationship": "TRANSACTION", "source": "transaction"},
        )
        iban_links = []
        nearby = page.text[window_start:window_end]
        person_match = _PERSON_NEAR.search(nearby)
        if person_match:
            clipped = clipped_name_span(
                person_match.group("name"),
                window_start + person_match.start("name"),
            )
            if clipped:
                name, local_start, local_end = clipped
                person = make_candidate(
                    page,
                    text=name,
                    local_start=local_start,
                    local_end=local_end,
                    entity_type=EntityType.PERSON_NAME,
                    detector="TR_BANK_TX",
                    reason="Person linked to a bank transfer.",
                    attributes={"relationship": "TRANSACTION", "source": "transaction"},
                    relations=[relation("ACCOUNT_HOLDER", target=iban)],
                )
                iban_links.append(relation("REGISTERED_TO", target=person))
                add(person)
        banks = [
            (bank_start, bank_end, label)
            for bank_start, bank_end, label in iter_bank_spans(page.text)
            if window_start <= bank_start < window_end
        ]
        if banks:
            bank_start, bank_end, label = min(banks, key=lambda item: abs(item[0] - start))
            bank = make_candidate(
                page,
                text=label,
                local_start=bank_start,
                local_end=bank_end,
                entity_type=EntityType.ORGANISATION,
                detector="TR_BANK_TX",
                reason="Bank name in a transfer context.",
                attributes={"org_kind": "BANK", "relationship": "TRANSACTION", "source": "transaction"},
            )
            iban_links.append(relation("BANK_OF", target=bank))
            add(bank)
        add(iban.model_copy(update={"relations": iban_links}))
    return found
