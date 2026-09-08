"""IPv4 + port pair parser."""

from __future__ import annotations

import re

from app.detectors.legal.common import make_candidate, relation
from app.detectors.registry import IPV4, PageText, _valid_ipv4
from app.domain.models import EntityCandidate, EntityType

# PDF layers glue the label: "117Ip", "38048Port". Case is not reliable (Ip / IP / ip).
_PORT_WORD = r"(?i:portu\.?|port(?:\s+numara(?:s[ıi])?)?)"
_PAIR = re.compile(
    rf"(?P<ip>{IPV4.pattern})\s*(?i:ip)?\s*(?:ve|,)?\s*"
    rf"(?P<port>\d{{1,5}})\s*{_PORT_WORD}\b"
)
_STANDALONE_PORT = re.compile(
    rf"(?<!\d)(?P<port>\d{{1,5}})\s*{_PORT_WORD}\b"
    rf"|{_PORT_WORD}\s*(?:=|:)?\s*(?P<port2>\d{{1,5}})(?!\d)"
)


def parse_ip_port(page: PageText) -> list[EntityCandidate]:
    found: list[EntityCandidate] = []
    seen_ports: set[tuple[int, int]] = set()
    for match in _PAIR.finditer(page.text):
        ip_value = match.group("ip")
        port_value = int(match.group("port"))
        if not _valid_ipv4(ip_value) or not 1 <= port_value <= 65535:
            continue
        ip = make_candidate(
            page,
            text=ip_value,
            local_start=match.start("ip"),
            local_end=match.end("ip"),
            entity_type=EntityType.IP_ADDRESS,
            detector="TR_IP_PORT",
            reason="IP in an IP+port pair.",
            attributes={"relationship": "IP_PORT_PAIR"},
        )
        port = make_candidate(
            page,
            text=match.group("port"),
            local_start=match.start("port"),
            local_end=match.end("port"),
            entity_type=EntityType.PORT_NUMBER,
            detector="TR_IP_PORT",
            reason="Port in an IP+port pair.",
            attributes={"relationship": "IP_PORT_PAIR"},
        )
        seen_ports.add((port.start, port.end))
        found.extend(
            (
                ip.model_copy(
                    update={"relations": [relation("IP_PORT_PAIR", target=port)]}
                ),
                port.model_copy(
                    update={"relations": [relation("IP_PORT_PAIR", target=ip)]}
                ),
            )
        )
    for match in _STANDALONE_PORT.finditer(page.text):
        raw = match.group("port") or match.group("port2")
        if raw is None:
            continue
        port_value = int(raw)
        if not 1 <= port_value <= 65535:
            continue
        group = "port" if match.group("port") is not None else "port2"
        start = page.document_offset + match.start(group)
        end = page.document_offset + match.end(group)
        if (start, end) in seen_ports:
            continue
        found.append(
            make_candidate(
                page,
                text=raw,
                local_start=match.start(group),
                local_end=match.end(group),
                entity_type=EntityType.PORT_NUMBER,
                detector="TR_IP_PORT",
                reason="Port number glued to or followed by Port/portu.",
                attributes={"source": "standalone_port"},
            )
        )
    return found
