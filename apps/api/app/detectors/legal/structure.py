"""Deterministic legal-document structure parsers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.detectors.legal.address import parse_address_tokens
from app.detectors.legal.birth import parse_birth
from app.detectors.legal.counsel import parse_counsel
from app.detectors.legal.court import parse_courts
from app.detectors.legal.ip_port import parse_ip_port
from app.detectors.legal.mentioned import parse_mentioned
from app.detectors.legal.organisation import parse_companies, parse_organisations
from app.detectors.legal.ownership import parse_ownership
from app.detectors.legal.parentage import parse_parentage
from app.detectors.legal.party import parse_party_blocks
from app.detectors.legal.phone_context import parse_phone_context
from app.detectors.legal.role_person import parse_role_persons
from app.detectors.legal.roster import parse_roster
from app.detectors.legal.statement import parse_statements
from app.detectors.legal.transaction import parse_transactions
from app.domain.models import EntityCandidate

if TYPE_CHECKING:
    from app.detectors.registry import PageText


def detect_legal_structure(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    found.extend(parse_roster(page))
    found.extend(parse_party_blocks(page))
    found.extend(parse_counsel(page))
    found.extend(parse_role_persons(page))
    found.extend(parse_parentage(page))
    found.extend(parse_birth(page))
    found.extend(parse_address_tokens(page))
    found.extend(parse_ownership(page))
    found.extend(parse_statements(page))
    found.extend(parse_phone_context(page))
    found.extend(parse_ip_port(page))
    found.extend(parse_courts(page))
    found.extend(parse_organisations(page))
    found.extend(parse_companies(page))
    found.extend(parse_mentioned(page))
    found.extend(parse_transactions(page))
    return found
