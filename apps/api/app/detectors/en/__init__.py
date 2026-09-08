"""English-General deterministic legal-document pack.

Model-free. Does not load spaCy, Hugging Face, or any network client.
Legal roles are evidence, not identity tokens.
"""

from __future__ import annotations

from app.detectors.en.addresses import parse_addresses
from app.detectors.en.courts import parse_courts
from app.detectors.en.identifiers import parse_identifiers
from app.detectors.en.legal_references import parse_legal_references
from app.detectors.en.legal_roles import parse_legal_roles
from app.detectors.en.organisations import parse_organisations
from app.detectors.en.person_candidates import (
    parse_narrative_persons,
    parse_signature_persons,
    parse_titled_persons,
)
from app.detectors.en.structural import has_matter_heading, parse_structural
from app.detectors.registry import PageText
from app.domain.models import EntityCandidate

RULE_GROUPS = (
    "structural",
    "legal_roles",
    "legal_references",
    "person_candidates",
    "addresses",
    "identifiers",
    "courts",
    "organisations",
)


def detect_english_legal(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    found.extend(parse_structural(page))
    found.extend(parse_legal_roles(page))
    found.extend(parse_titled_persons(page))
    found.extend(parse_signature_persons(page))
    found.extend(parse_narrative_persons(page))
    found.extend(parse_legal_references(page))
    found.extend(parse_courts(page))
    found.extend(parse_organisations(page))
    found.extend(parse_addresses(page))
    found.extend(parse_identifiers(page))
    if has_matter_heading(page.text):
        for item in found:
            attrs = dict(item.attributes or {})
            evidence = list(attrs.get("evidence") or [])
            if not any(entry.get("code") == "en_matter_heading" for entry in evidence if isinstance(entry, dict)):
                evidence.append(
                    {"code": "en_matter_heading", "weight": 1, "source": "context"}
                )
            attrs["evidence"] = evidence
            attrs["en_matter_context"] = True
            item.attributes = attrs
    return found
