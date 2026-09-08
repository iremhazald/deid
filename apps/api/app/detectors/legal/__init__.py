"""Deterministic legal-document structure parsers.

This package init stays import-light so ``registry`` can import
``legal.merge`` at module level without a circular import through
``legal.common`` → ``registry.PageText``.
"""

from __future__ import annotations

PARSER_NAMES = (
    "TR_JUDICIAL_ROSTER",
    "TR_LEGAL_PARTY",
    "TR_COUNSEL_BLOCK",
    "TR_ROLE_PERSON",
    "TR_PARENTAGE",
    "TR_BIRTH_INFO",
    "TR_ADDRESS_TOKENS",
    "TR_OWNERSHIP",
    "TR_STATEMENT",
    "TR_PHONE_CONTEXT",
    "TR_IP_PORT",
    "TR_COURT_GRAMMAR",
    "TR_ORG_AUTHORITY",
    "TR_COMPANY_SUFFIX",
    "TR_MENTIONED_PERSON",
    "TR_BANK_TX",
)
